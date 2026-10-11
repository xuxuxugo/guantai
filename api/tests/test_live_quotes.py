from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import make_engine
from app.engine import PositionView, QuoteView, explain
from app.models import Base, User
from app.services import ShockError, apply_shock, poll_interval_seconds, rebase_catalog_ref
from app.tencent import fetch_spot, parse_kline_payload, parse_tencent_payload, to_symbol
from app.live_quotes import Spot, TencentQuoteProvider
from app.universe import STOCKS, StockMeta


def _spot_line(symbol: str, fields: list[str]) -> str:
    return f'v_{symbol}="{"~".join(fields)}";'


def _fields(**values: str) -> list[str]:
    fields = [""] * 50
    fields[0] = "1"
    for key, value in values.items():
        fields[int(key)] = value
    return fields


FIXTURE = "\n".join(
    [
        _spot_line(
            "sh600519",
            _fields(
                **{
                    "1": "贵州茅台",
                    "2": "600519",
                    "3": "1263.00",
                    "4": "1255.79",
                    "5": "1255.42",
                    "30": "20261009161459",
                    "32": "0.57",
                    "33": "1282.00",
                    "34": "1255.42",
                    "49": "1.18",
                }
            ),
        ),
        _spot_line(
            "sz000001",
            _fields(
                **{
                    "1": "平安银行",
                    "2": "000001",
                    "3": "0.00",
                    "4": "11.78",
                    "5": "11.78",
                    "30": "20261009161500",
                    "32": "-1.61",
                    "33": "11.89",
                    "34": "11.58",
                    "49": "1.08",
                }
            ),
        ),
    ]
)


def test_symbol_prefixes():
    assert to_symbol("600519") == "sh600519"
    assert to_symbol("688981") == "sh688981"
    assert to_symbol("000001") == "sz000001"
    assert to_symbol("300750") == "sz300750"
    assert to_symbol("830799") == "bj830799"


def test_parse_tencent_spot_fixture():
    spots = parse_tencent_payload(FIXTURE)
    maotai = spots["600519"]
    assert maotai.name == "贵州茅台"
    assert maotai.price == 1263.00
    assert maotai.prev_close == 1255.79
    assert maotai.open == 1255.42
    assert maotai.day_high == 1282.00
    assert maotai.day_low == 1255.42
    assert maotai.volume_ratio == 1.18
    assert maotai.price != 1428.00
    bank = spots["000001"]
    assert bank.name == "平安银行"
    assert bank.price == 11.78
    assert bank.prev_close == 11.78


def test_parse_kline_excludes_latest_bar_from_twenty_day_high():
    rows = [[f"2026-01-{day:02d}", "10", "11", "12", "9", "100"] for day in range(1, 21)]
    rows.append(["2026-01-21", "11", "20", "30", "10", "100"])
    payload = {"data": {"sh600519": {"qfqday": rows}}}
    candles, high_20d = parse_kline_payload(payload, "sh600519")
    assert len(candles) == 21
    assert candles[-1].close == 20
    assert high_20d == 12


def test_failed_refresh_keeps_last_success_and_marks_stale():
    calls = {"n": 0}

    def fetcher(_codes: list[str]) -> dict[str, Spot]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise TimeoutError("timed out")
        return {
            "600519": Spot("600519", "贵州茅台", 1263.0, 1255.79, 1255.42, 1282.0, 1255.42, 1.18),
        }

    provider = TencentQuoteProvider(
        stocks=(StockMeta("600519", "贵州茅台", 1428.0),),
        fetcher=fetcher,
        kline_fetcher=lambda _code: ([], 0.0),
        autofetch=False,
    )
    provider.refresh()
    first = provider.get("600519")
    assert first.price == 1263.0
    assert first.stale is False
    assert first.source == "tencent"
    provider.refresh()
    second = provider.get("600519")
    assert second.price == 1263.0
    assert second.prev_close == 1255.79
    assert second.volume_ratio == 1.18
    assert second.stale is True


def test_shock_is_refused_while_tencent_is_the_source(monkeypatch):
    provider = TencentQuoteProvider(
        stocks=(STOCKS[0],),
        fetcher=lambda _codes: {},
        kline_fetcher=lambda _code: ([], 0.0),
        autofetch=False,
    )
    monkeypatch.setattr("app.services.get_provider", lambda: provider)
    with pytest.raises(ShockError, match="QUOTE_SOURCE"):
        apply_shock("600519", "swing_up", None)


def test_poll_interval_slows_down_outside_the_session():
    assert poll_interval_seconds(source="tencent", session_open=True, scan_interval=4, offhours_interval=60) == 4
    assert poll_interval_seconds(source="tencent", session_open=False, scan_interval=4, offhours_interval=60) == 60
    assert poll_interval_seconds(source="mock", session_open=False, scan_interval=4, offhours_interval=60) == 4


def test_catalog_ref_is_rebased_once_live_price_arrives():
    class Item:
        code = "600519"
        ref_price = 1263.0

    class Quote:
        source = "tencent"
        stale = False
        price = 1300.0

    item = Item()
    assert rebase_catalog_ref(item, Quote()) is True
    assert item.ref_price == 1300.0
    item.ref_price = 1200.0
    assert rebase_catalog_ref(item, Quote()) is False
    assert item.ref_price == 1200.0


def test_missing_daily_bars_do_not_look_like_a_breakout():
    rows = explain(QuoteView(1263, 0, 0, 1), _rule(), None)
    assert "日 K 还没取到" in rows[0].detail


def _rule():
    from app.engine import RuleConfig

    return RuleConfig(True, True, 5, 3, True, True, 2.5)


def test_sqlite_create_all(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/guanlan.db")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(username="demo", display_name="演示用户", created_at=datetime.now(timezone.utc)))
        db.commit()
        assert db.scalar(select(User.username)) == "demo"


def test_live_tencent_quotes_for_maotai_and_pingan():
    spots = fetch_spot(["600519", "000001"], timeout=8)
    maotai = spots["600519"]
    bank = spots["000001"]
    assert maotai.name == "贵州茅台"
    assert bank.name == "平安银行"
    assert maotai.price > 100
    assert bank.price > 1
    assert maotai.prev_close > 0
    assert bank.prev_close > 0
    assert maotai.volume_ratio > 0
    assert bank.volume_ratio > 0
    assert maotai.price != 1428.00
    assert abs(bank.price - 11.62) > 0.001 or bank.prev_close != 11.62
