from app.breadth import breadth_from_rows, parse_breadth_payload
from app.sectors import parse_company_survey, shorten_industry
from app.market import MarketBoard
from app.sina_board import parse_sina_hq
from app.tencent import IndexSpot, fetch_indices, parse_index_payload


def _line(symbol: str, fields: list[str]) -> str:
    return f'v_{symbol}="{"~".join(fields)}";'


def _fields(**values: str) -> list[str]:
    fields = [""] * 60
    fields[0] = "1"
    for key, value in values.items():
        fields[int(key)] = value
    return fields


FIXTURE = "\n".join(
    [
        _line(
            "sh000001",
            _fields(**{"1": "上证指数", "2": "000001", "3": "3813.79", "4": "3811.90", "32": "0.05", "57": "88856119.8264"}),
        ),
        _line(
            "sz399001",
            _fields(**{"1": "深证成指", "2": "399001", "3": "12641.86", "4": "12620.90", "32": "0.17", "57": "101199421.6302"}),
        ),
        _line(
            "sz399006",
            _fields(**{"1": "创业板指", "2": "399006", "3": "3043.33", "4": "3036.66", "32": "0.22", "37": "49204540"}),
        ),
    ]
)


def test_parse_three_index_prices_and_turnover():
    parsed = parse_index_payload(FIXTURE)
    shanghai = parsed["sh000001"]
    assert shanghai.name == "上证指数"
    assert shanghai.price == 3813.79
    assert shanghai.change_pct == 0.05
    assert shanghai.turnover == 888561198264
    shenzhen = parsed["sz399001"]
    assert shenzhen.name == "深证成指"
    assert shenzhen.price == 12641.86
    assert shenzhen.turnover == 1011994216302
    chinext = parsed["sz399006"]
    assert chinext.name == "创业板指"
    assert chinext.price == 3043.33
    assert chinext.turnover == 492045400000


def test_failed_index_refresh_keeps_last_prices():
    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        if calls["n"] > 1:
            raise TimeoutError("timed out")
        return parse_index_payload(FIXTURE)

    board = MarketBoard(fetcher=fetcher, autofetch=False)
    board.refresh()
    first = {item["symbol"]: item for item in board.snapshot()}
    assert first["sh000001"]["price"] == 3813.79
    assert first["sh000001"]["stale"] is False
    board.refresh()
    second = {item["symbol"]: item for item in board.snapshot()}
    assert second["sh000001"]["price"] == 3813.79
    assert second["sz399001"]["price"] == 12641.86
    assert second["sz399006"]["price"] == 3043.33
    assert all(item["stale"] for item in second.values())


def test_parse_breadth_sums_shanghai_and_shenzhen():
    payload = {
        "data": {
            "diff": [
                {"f12": "000001", "f14": "上证指数", "f104": 1341, "f105": 956, "f106": 60},
                {"f12": "399001", "f14": "深证成指", "f104": 1698, "f105": 1166, "f106": 66},
            ]
        }
    }
    breadth = parse_breadth_payload(payload)
    assert breadth["up"] == 3039
    assert breadth["down"] == 2122
    assert breadth["flat"] == 126
    assert breadth["total"] == 3039 + 2122 + 126
    assert breadth["stale"] is False


def test_failed_breadth_falls_back_or_keeps_last():
    calls = {"n": 0}

    def fetcher():
        return parse_index_payload(FIXTURE)

    def breadth_fetcher():
        calls["n"] += 1
        if calls["n"] > 1:
            raise TimeoutError("timed out")
        return parse_breadth_payload(
            {"data": {"diff": [{"f14": "上证指数", "f104": 10, "f105": 20, "f106": 1}]}}
        )

    board = MarketBoard(fetcher=fetcher, breadth_fetcher=breadth_fetcher, autofetch=False)
    board.refresh(breadth=False)
    board._refresh_breadth()
    first = board.breadth()
    assert first["up"] == 10
    assert first["stale"] is False
    board._breadth_at = 0.0
    board._refresh_breadth()
    second = board.breadth()
    assert second["total"] > 0
    assert second["up"] >= 0
    # Either sample-pool fallback, Sina whole-market, or previous Eastmoney snapshot.
    assert second["source"] in {"样本池估算", "东方财富", "新浪行情中心"}


def test_shorten_and_parse_industry():
    assert shorten_industry("通讯行业") == "通讯"
    assert parse_company_survey({"jbzl": {"sshy": "银行行业", "sszjhhy": "金融业"}}) == "银行"


def test_breadth_from_pool_rows():
    breadth = breadth_from_rows(
        [
            {"price": 10, "change_pct": 1},
            {"price": 10, "change_pct": -1},
            {"price": 10, "change_pct": 0},
            {"price": 0, "change_pct": 9},
        ]
    )
    assert breadth["up"] == 1
    assert breadth["down"] == 1
    assert breadth["flat"] == 1
    assert breadth["source"] == "样本池估算"


def test_parse_sina_hq_converts_market_cap_to_yi():
    rows = parse_sina_hq(
        [
            {
                "code": "300308",
                "name": "中际旭创",
                "trade": "100",
                "settlement": "99",
                "changepercent": 1.01,
                "amount": 1_000_000_000,
                "mktcap": 200000,
            }
        ]
    )
    assert rows[0]["code"] == "300308"
    assert rows[0]["market_cap"] == 20.0
    assert rows[0]["turnover"] == 1_000_000_000


def test_live_three_indices_have_prices():
    spots = fetch_indices(timeout=8)
    expected = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
    }
    assert set(expected) <= set(spots)
    for symbol, name in expected.items():
        spot = spots[symbol]
        assert isinstance(spot, IndexSpot)
        assert spot.name == name
        assert spot.price > 100
        assert spot.prev_close > 0
        assert spot.turnover > 0


def test_live_breadth_has_counts():
    from app.breadth import fetch_breadth, fetch_sina_breadth

    try:
        breadth = fetch_breadth(timeout=10)
    except Exception:
        try:
            breadth = fetch_sina_breadth(timeout=12)
        except Exception as exc:
            import pytest

            pytest.skip(f"breadth source unavailable: {exc}")
    assert breadth["up"] > 0
    assert breadth["down"] > 0
    assert breadth["total"] == breadth["up"] + breadth["down"] + breadth["flat"]
    assert breadth["source"] in {"东方财富", "新浪行情中心"}
