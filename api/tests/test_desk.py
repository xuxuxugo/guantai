from pathlib import Path

from app.backtest import run_backtest
from app.extra_routes import router as extra_router
from app.indicators import boll, composite_rating, kdj, macd, rsi
from app.insights import calendar_events, parse_financial_payload, parse_sina_roll, parse_vix, screen_rows
from app.quotes import Candle
from app.routes import router


def test_menu_routes_are_registered():
    paths = {getattr(route, "path", "") for route in list(router.routes) + list(extra_router.routes)}
    for path in (
        "/api/market",
        "/api/pool",
        "/api/rankings",
        "/api/screen",
        "/api/digest",
        "/api/news",
        "/api/calendar",
        "/api/opportunities",
        "/api/datacenter",
        "/api/backtest",
        "/api/agent",
        "/api/stocks/{code}/technical",
        "/api/stocks/{code}/financials",
        "/api/watchlist",
        "/api/alerts",
        "/api/rules",
    ):
        assert path in paths


def test_rising_market_is_not_oversold():
    closes = [100 * (1.01 ** index) for index in range(80)]
    assert rsi(closes)[-1] > 70
    row = macd(closes)[-1]
    assert row["dif"] > row["dea"]
    bands = boll(closes)
    assert bands[-1]["upper"] > bands[-1]["mid"] > bands[-1]["lower"]
    kd = kdj(closes, [value - 1 for value in closes], closes)
    assert kd[-1]["k"] > 50
    rating = composite_rating(1, 0, 80, 70, 60, closes[-1], bands[-1]["mid"])
    assert rating["label"] in {"偏多", "中性偏多"}


def test_momentum_backtest_profits_on_a_rising_series():
    candles = [Candle(date=f"2026-01-{index:02d}", open=100 + index, high=101 + index, low=99 + index, close=100 + index) for index in range(1, 40)]
    result = run_backtest(candles, "momentum")
    assert result["equity"]
    assert result["total_return_pct"] > 0
    assert result["trade_count"] >= 1


def test_screen_filters_change_and_turnover():
    rows = [
        {"price": 10, "change_pct": 3, "volume_ratio": 2, "turnover": 5e8, "market_cap": 100},
        {"price": 10, "change_pct": -2, "volume_ratio": 0.5, "turnover": 1e8, "market_cap": 10},
        {"price": 0, "change_pct": 9, "volume_ratio": 9, "turnover": 9e8, "market_cap": 9},
    ]
    found = screen_rows(rows, min_change=1, min_volume_ratio=1, min_turnover=2e8, min_market_cap=50)
    assert len(found) == 1
    assert found[0]["change_pct"] == 3


def test_financial_and_news_parsers():
    reports = parse_financial_payload(
        {"data": [{"REPORT_DATE_NAME": "2026中报", "TOTALOPERATEREVE": 100, "PARENTNETPROFIT": 40, "EPSJB": 1.2, "ROEJQ": 10}]}
    )
    assert reports[0]["period"] == "2026中报"
    assert reports[0]["eps"] == 1.2
    items = parse_sina_roll({"result": {"data": [{"title": "测试快讯", "url": "https://example.com", "intro": "摘要", "media_name": "测试", "ctime": 1760000000}]}})
    assert items[0]["title"] == "测试快讯"
    assert items[0]["url"].startswith("https://")


def test_menu_pages_exist():
    root = Path(__file__).resolve().parents[2] / "web" / "app"
    for name in (
        "page.tsx",
        "watch/page.tsx",
        "alerts/page.tsx",
        "rules/page.tsx",
        "info/page.tsx",
        "technical/page.tsx",
        "financial/page.tsx",
        "quant/page.tsx",
        "agent/page.tsx",
        "screen/page.tsx",
        "digest/page.tsx",
        "overview/page.tsx",
        "data/page.tsx",
        "calendar/page.tsx",
        "news/page.tsx",
        "opportunities/page.tsx",
        "me/page.tsx",
        "stocks/[code]/page.tsx",
    ):
        assert (root / name).is_file(), name


def test_vix_parser_and_sample_calendar():
    parsed = parse_vix({"chart": {"result": [{"meta": {"regularMarketPrice": 18.2, "chartPreviousClose": 17.5}}]}})
    assert parsed["price"] == 18.2
    assert parsed["change_pct"] > 0
    calendar = calendar_events()
    assert calendar["events"]
    assert "示例" in calendar["source"] or calendar["source"] == "示例日程" or "东方财富" in calendar["source"]
    assert any(
        "示例" in str(item.get("importance", "")) or "已发布" in str(item.get("importance", ""))
        for item in calendar["events"]
    )
