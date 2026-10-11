from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.engine import (
    PositionView,
    QuoteView,
    RuleConfig,
    alerts_allowed,
    board_status,
    evaluate,
    explain,
    within_trading_session,
)
from app.pulse import choose_pulse
from app.quotes import MockQuoteProvider
from app.universe import STOCKS, search_stocks


def rule(**overrides) -> RuleConfig:
    base = dict(
        breakout_20d_enabled=True,
        swing_enabled=True,
        swing_window_minutes=5,
        swing_threshold_pct=3,
        stop_loss_enabled=True,
        volume_spike_enabled=True,
        volume_ratio_threshold=2.5,
    )
    base.update(overrides)
    return RuleConfig(**base)


def test_quiet_market_stays_green():
    signals = evaluate(QuoteView(100, 120, 0.4, 1.1), rule(), PositionView(100, 8))
    assert signals == []
    assert board_status(signals) == "observe"


def test_breakout_and_soft_approach():
    hit = evaluate(QuoteView(100, 100, 0, 1), rule(), PositionView(100, 8))
    assert any(item.rule_key == "breakout_20d" and item.level == "anomaly" for item in hit)
    near = evaluate(QuoteView(99.2, 100, 0, 1), rule(), PositionView(100, 8))
    assert any(item.rule_key == "near_breakout_20d" and item.level == "observe" for item in near)
    assert board_status(near) == "observe"


def test_swing_threshold_and_soft_band():
    hard = evaluate(QuoteView(100, 130, -3.2, 1), rule(), PositionView(100, 8))
    assert any(item.rule_key == "swing_down" for item in hard)
    soft = evaluate(QuoteView(100, 130, 2.0, 1), rule(), PositionView(100, 8))
    assert board_status(soft) == "observe"
    assert any(item.rule_key == "swing_watch" for item in soft)


def test_volume_spike():
    signals = evaluate(QuoteView(100, 130, 0.2, 2.8), rule(), PositionView(100, 8))
    assert any(item.rule_key == "volume_spike" and item.level == "anomaly" for item in signals)


def test_stop_loss_beats_other_levels():
    signals = evaluate(QuoteView(90, 110, -1, 1), rule(), PositionView(100, 8))
    assert any(item.rule_key == "stop_loss" and item.level == "risk" for item in signals)
    assert board_status(signals) == "risk"


def test_near_stop_is_not_a_risk_light():
    signals = evaluate(QuoteView(93, 120, 0, 1), rule(), PositionView(100, 8))
    assert any(item.rule_key == "stop_watch" for item in signals)
    assert board_status(signals) == "observe"


def test_disabled_rules_emit_nothing():
    silent = rule(
        breakout_20d_enabled=False,
        swing_enabled=False,
        stop_loss_enabled=False,
        volume_spike_enabled=False,
    )
    signals = evaluate(QuoteView(200, 100, 9, 9), silent, PositionView(100, 1))
    assert signals == []


def test_explain_always_covers_four_rules():
    rows = explain(QuoteView(100, 120, 0.2, 1), rule(), None)
    assert [row.rule_key for row in rows] == ["breakout_20d", "swing", "stop_loss", "volume_spike"]
    assert rows[2].detail == "加入自选后才能按参考价计算止损"


def test_trading_hours_follow_shanghai_session():
    shanghai = ZoneInfo("Asia/Shanghai")
    assert within_trading_session(datetime(2026, 10, 9, 9, 30, tzinfo=shanghai))
    assert within_trading_session(datetime(2026, 10, 9, 11, 30, tzinfo=shanghai))
    assert not within_trading_session(datetime(2026, 10, 9, 11, 31, tzinfo=shanghai))
    assert not within_trading_session(datetime(2026, 10, 9, 12, 0, tzinfo=shanghai))
    assert within_trading_session(datetime(2026, 10, 9, 13, 0, tzinfo=shanghai))
    assert within_trading_session(datetime(2026, 10, 9, 15, 0, tzinfo=shanghai))
    assert not within_trading_session(datetime(2026, 10, 9, 15, 1, tzinfo=shanghai))
    assert not within_trading_session(datetime(2026, 10, 9, 9, 29, tzinfo=shanghai))
    assert not within_trading_session(datetime(2026, 10, 10, 10, 0, tzinfo=shanghai))
    assert within_trading_session(datetime(2026, 10, 9, 2, 0, tzinfo=timezone.utc))
    assert alerts_allowed(False, datetime(2026, 10, 10, 10, 0, tzinfo=shanghai))
    assert not alerts_allowed(True, datetime(2026, 10, 10, 10, 0, tzinfo=shanghai))


def test_search_ranks_code_before_name():
    assert [item.code for item in search_stocks("600")][0] == "600519"
    names = [item.name for item in search_stocks("平安")]
    assert names == ["平安银行", "中国平安"]
    assert search_stocks("") == []


def test_pulse_rotation_skips_quiet_ticks_and_held_names():
    assert choose_pulse(2, ["000001"], set()) is None
    assert choose_pulse(1, ["000001", "600519"], set()) == ("000001", "swing_up")
    assert choose_pulse(5, ["000001", "600519"], set()) == ("600519", "volume")
    assert choose_pulse(1, ["000001"], {"000001"}) is None


def test_mock_quotes_start_below_the_twenty_day_high():
    provider = MockQuoteProvider()
    for meta in STOCKS:
        quote = provider.get(meta.code)
        assert quote.price < quote.high_20d
        assert len(quote.candles) == 40


def test_shock_shapes():
    provider = MockQuoteProvider()
    before = provider.get("000001").price
    swung = provider.shock("000001", pct=3.6)
    assert swung.price > before
    assert swung.window_change_pct(5) >= 3.4

    broken = provider.shock("600519", breakout=True, reset_window=True)
    assert broken.price >= broken.high_20d
    assert abs(broken.window_change_pct(5)) < 0.2

    loud = provider.shock("600036", volume_ratio=3.4, reset_window=True)
    assert loud.volume_ratio == 3.4

    held = provider.shock("300750", pct=-3.6)
    provider.tick_all()
    assert provider.get("300750").price == held.price
