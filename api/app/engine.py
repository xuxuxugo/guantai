"""Quote rules for 观察 / 异动 / 风控.

Board colors describe risk, not A-share price direction. Price up/down stays red/green
in the UI; these levels only say how hard the rule was hit.
"""

from dataclasses import dataclass
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
STATUS_LABEL = {"observe": "观察", "anomaly": "异动", "risk": "风控"}


@dataclass(frozen=True)
class RuleConfig:
    breakout_20d_enabled: bool
    swing_enabled: bool
    swing_window_minutes: int
    swing_threshold_pct: float
    stop_loss_enabled: bool
    volume_spike_enabled: bool
    volume_ratio_threshold: float


@dataclass(frozen=True)
class QuoteView:
    price: float
    high_20d: float
    window_change_pct: float
    volume_ratio: float


@dataclass(frozen=True)
class PositionView:
    ref_price: float
    stop_loss_pct: float


@dataclass(frozen=True)
class Signal:
    level: str
    rule_key: str
    title: str
    reason: str


@dataclass(frozen=True)
class TriggerRow:
    rule_key: str
    title: str
    enabled: bool
    hit: bool
    level: str
    detail: str


def within_trading_session(now: datetime) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(SHANGHAI)
    if local.weekday() >= 5:
        return False
    current = local.timetz().replace(tzinfo=None)
    morning = time(9, 30) <= current <= time(11, 30)
    afternoon = time(13, 0) <= current <= time(15, 0)
    return morning or afternoon


def alerts_allowed(trading_hours_only: bool, now: datetime) -> bool:
    if not trading_hours_only:
        return True
    return within_trading_session(now)


def evaluate(quote: QuoteView, rule: RuleConfig, position: PositionView | None) -> list[Signal]:
    signals: list[Signal] = []

    if rule.breakout_20d_enabled and quote.high_20d > 0 and quote.price >= quote.high_20d:
        signals.append(
            Signal(
                level="anomaly",
                rule_key="breakout_20d",
                title="突破20日高点",
                reason=f"现价 {quote.price:.2f} 不低于近20日高点 {quote.high_20d:.2f}",
            )
        )
    elif rule.breakout_20d_enabled and quote.high_20d > 0:
        gap = (quote.high_20d - quote.price) / quote.high_20d * 100
        if 0 < gap <= 1:
            signals.append(
                Signal(
                    level="observe",
                    rule_key="near_breakout_20d",
                    title="接近20日高点",
                    reason=f"现价 {quote.price:.2f} 距近20日高点 {quote.high_20d:.2f} 还有 {gap:.2f}%",
                )
            )

    if rule.swing_enabled:
        move = quote.window_change_pct
        threshold = rule.swing_threshold_pct
        window = rule.swing_window_minutes
        if abs(move) >= threshold:
            direction = "上涨" if move > 0 else "下跌"
            signals.append(
                Signal(
                    level="anomaly",
                    rule_key="swing_up" if move > 0 else "swing_down",
                    title=f"{window}分钟{direction}超过{threshold:g}%",
                    reason=f"近{window}分钟{direction} {abs(move):.2f}%，阈值 {threshold:g}%",
                )
            )
        elif threshold > 0 and abs(move) >= threshold * 0.6:
            direction = "上涨" if move > 0 else "下跌"
            signals.append(
                Signal(
                    level="observe",
                    rule_key="swing_watch",
                    title=f"{window}分钟波动值得看一眼",
                    reason=f"近{window}分钟{direction} {abs(move):.2f}%，尚未达到 {threshold:g}% 阈值",
                )
            )

    if (
        rule.stop_loss_enabled
        and position is not None
        and position.ref_price > 0
        and position.stop_loss_pct > 0
    ):
        drop = (quote.price - position.ref_price) / position.ref_price * 100
        if drop <= -position.stop_loss_pct:
            signals.append(
                Signal(
                    level="risk",
                    rule_key="stop_loss",
                    title="触及止损",
                    reason=(
                        f"现价 {quote.price:.2f}，相对参考价 {position.ref_price:.2f} "
                        f"回撤 {abs(drop):.2f}%，止损线 {position.stop_loss_pct:g}%"
                    ),
                )
            )
        elif drop <= -position.stop_loss_pct * 0.7:
            signals.append(
                Signal(
                    level="observe",
                    rule_key="stop_watch",
                    title="接近止损",
                    reason=(
                        f"相对参考价 {position.ref_price:.2f} 回撤 {abs(drop):.2f}%，"
                        f"止损线 {position.stop_loss_pct:g}%"
                    ),
                )
            )

    if rule.volume_spike_enabled and quote.volume_ratio >= rule.volume_ratio_threshold:
        signals.append(
            Signal(
                level="anomaly",
                rule_key="volume_spike",
                title="量比突增",
                reason=f"量比 {quote.volume_ratio:.2f}，高于阈值 {rule.volume_ratio_threshold:g}",
            )
        )
    elif (
        rule.volume_spike_enabled
        and rule.volume_ratio_threshold > 0
        and quote.volume_ratio >= rule.volume_ratio_threshold * 0.75
    ):
        signals.append(
            Signal(
                level="observe",
                rule_key="volume_watch",
                title="量比抬升",
                reason=f"量比 {quote.volume_ratio:.2f}，接近阈值 {rule.volume_ratio_threshold:g}",
            )
        )

    return signals


def board_status(signals: list[Signal]) -> str:
    levels = {signal.level for signal in signals}
    if "risk" in levels:
        return "risk"
    if "anomaly" in levels:
        return "anomaly"
    return "observe"


def live_signal_text(signals: list[Signal]) -> str | None:
    hard = [signal for signal in signals if signal.level in {"risk", "anomaly"}]
    if hard:
        hard.sort(key=lambda signal: 0 if signal.level == "risk" else 1)
        return "、".join(signal.title for signal in hard)
    soft = [signal for signal in signals if signal.level == "observe"]
    if soft:
        return soft[0].title
    return None


def explain(quote: QuoteView, rule: RuleConfig, position: PositionView | None) -> list[TriggerRow]:
    found = {signal.rule_key: signal for signal in evaluate(quote, rule, position)}
    rows: list[TriggerRow] = []

    if not rule.breakout_20d_enabled:
        rows.append(TriggerRow("breakout_20d", "突破20日高点", False, False, "none", "规则未开启"))
    elif "breakout_20d" in found:
        signal = found["breakout_20d"]
        rows.append(TriggerRow("breakout_20d", signal.title, True, True, signal.level, signal.reason))
    elif "near_breakout_20d" in found:
        signal = found["near_breakout_20d"]
        rows.append(TriggerRow("breakout_20d", "突破20日高点", True, False, "observe", signal.reason))
    else:
        if quote.high_20d <= 0:
            detail = "日 K 还没取到，先不判断是否突破"
        else:
            gap = (quote.high_20d - quote.price) / quote.high_20d * 100
            detail = f"现价 {quote.price:.2f}，近20日高点 {quote.high_20d:.2f}，距离 {gap:.2f}%"
        rows.append(
            TriggerRow(
                "breakout_20d",
                "突破20日高点",
                True,
                False,
                "none",
                detail,
            )
        )

    window = rule.swing_window_minutes
    threshold = rule.swing_threshold_pct
    swing_title = f"{window}分钟涨跌超过{threshold:g}%"
    hard_swing = found.get("swing_up") or found.get("swing_down")
    if not rule.swing_enabled:
        rows.append(TriggerRow("swing", swing_title, False, False, "none", "规则未开启"))
    elif hard_swing:
        rows.append(TriggerRow("swing", hard_swing.title, True, True, hard_swing.level, hard_swing.reason))
    elif "swing_watch" in found:
        rows.append(TriggerRow("swing", swing_title, True, False, "observe", found["swing_watch"].reason))
    else:
        move = quote.window_change_pct
        direction = "上涨" if move > 0 else "下跌" if move < 0 else "波动"
        rows.append(
            TriggerRow(
                "swing",
                swing_title,
                True,
                False,
                "none",
                f"近{window}分钟{direction} {abs(move):.2f}%，阈值 {threshold:g}%",
            )
        )

    if not rule.stop_loss_enabled:
        rows.append(TriggerRow("stop_loss", "止损提醒", False, False, "none", "规则未开启"))
    elif position is None:
        rows.append(TriggerRow("stop_loss", "止损提醒", True, False, "none", "加入自选后才能按参考价计算止损"))
    elif "stop_loss" in found:
        signal = found["stop_loss"]
        rows.append(TriggerRow("stop_loss", signal.title, True, True, signal.level, signal.reason))
    elif "stop_watch" in found:
        rows.append(TriggerRow("stop_loss", "止损提醒", True, False, "observe", found["stop_watch"].reason))
    else:
        drop = 0.0 if position.ref_price <= 0 else (quote.price - position.ref_price) / position.ref_price * 100
        rows.append(
            TriggerRow(
                "stop_loss",
                "止损提醒",
                True,
                False,
                "none",
                f"相对参考价 {position.ref_price:.2f} 变动 {drop:+.2f}%，止损线 {position.stop_loss_pct:g}%",
            )
        )

    if not rule.volume_spike_enabled:
        rows.append(TriggerRow("volume_spike", "量比突增", False, False, "none", "规则未开启"))
    elif "volume_spike" in found:
        signal = found["volume_spike"]
        rows.append(TriggerRow("volume_spike", signal.title, True, True, signal.level, signal.reason))
    elif "volume_watch" in found:
        rows.append(TriggerRow("volume_spike", "量比突增", True, False, "observe", found["volume_watch"].reason))
    else:
        rows.append(
            TriggerRow(
                "volume_spike",
                "量比突增",
                True,
                False,
                "none",
                f"量比 {quote.volume_ratio:.2f}，阈值 {rule.volume_ratio_threshold:g}",
            )
        )

    return rows
