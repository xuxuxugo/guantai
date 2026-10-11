import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engine import (
    STATUS_LABEL,
    PositionView,
    QuoteView,
    RuleConfig,
    Signal,
    alerts_allowed,
    board_status,
    evaluate,
    explain,
    live_signal_text,
    within_trading_session,
)
from app.models import AlertEvent, AlertRule, QuoteSnapshot, User, WatchlistItem
from app.pulse import choose_pulse
from app.quotes import Quote, get_provider
from app.universe import BY_CODE

logger = logging.getLogger("guanlan")

DEDUPE_TTL = {"observe": 600, "anomaly": 240, "risk": 180}
KIND_KEYS = {
    "swing_up": {"swing_up", "swing_down", "swing_watch"},
    "swing_down": {"swing_up", "swing_down", "swing_watch"},
    "breakout": {"breakout_20d", "near_breakout_20d"},
    "volume": {"volume_spike", "volume_watch"},
    "stop": {"stop_loss", "stop_watch"},
}

_tick_index = 0
_last_poll = 0.0
_redis = None
_gate = threading.Lock()


class ShockError(ValueError):
    pass


def get_redis():
    global _redis
    if _redis is None:
        import redis

        from app.config import settings

        _redis = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
    return _redis


def check_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def demo_user(db: Session) -> User | None:
    return db.scalar(select(User).where(User.username == "demo"))


def rule_config(rule: AlertRule) -> RuleConfig:
    return RuleConfig(
        breakout_20d_enabled=rule.breakout_20d_enabled,
        swing_enabled=rule.swing_enabled,
        swing_window_minutes=rule.swing_window_minutes,
        swing_threshold_pct=rule.swing_threshold_pct,
        stop_loss_enabled=rule.stop_loss_enabled,
        volume_spike_enabled=rule.volume_spike_enabled,
        volume_ratio_threshold=rule.volume_ratio_threshold,
    )


def get_or_create_rule(db: Session, user: User) -> AlertRule:
    rule = db.scalar(select(AlertRule).where(AlertRule.user_id == user.id))
    if rule is not None:
        return rule
    now = datetime.now(timezone.utc)
    rule = AlertRule(
        user_id=user.id,
        breakout_20d_enabled=True,
        swing_enabled=True,
        swing_window_minutes=5,
        swing_threshold_pct=3,
        stop_loss_enabled=True,
        default_stop_loss_pct=8,
        volume_spike_enabled=True,
        volume_ratio_threshold=2.5,
        trading_hours_only=False,
        updated_at=now,
    )
    db.add(rule)
    db.flush()
    return rule


def quote_view(quote: Quote, window_minutes: int) -> QuoteView:
    return QuoteView(
        price=quote.price,
        high_20d=quote.high_20d,
        window_change_pct=quote.window_change_pct(window_minutes),
        volume_ratio=quote.volume_ratio,
    )


def position_view(item: WatchlistItem | None) -> PositionView | None:
    if item is None:
        return None
    return PositionView(ref_price=item.ref_price, stop_loss_pct=item.stop_loss_pct)


def signals_for(rule: AlertRule, item: WatchlistItem | None, quote: Quote) -> list[Signal]:
    return evaluate(quote_view(quote, rule.swing_window_minutes), rule_config(rule), position_view(item))


def trigger_rows(rule: AlertRule, item: WatchlistItem | None, quote: Quote):
    return explain(quote_view(quote, rule.swing_window_minutes), rule_config(rule), position_view(item))


def to_alert_dict(event: AlertEvent) -> dict:
    return {
        "id": event.id,
        "code": event.code,
        "name": event.name,
        "level": event.level,
        "level_label": STATUS_LABEL.get(event.level, event.level),
        "rule_key": event.rule_key,
        "title": event.title,
        "reason": event.reason,
        "price": round(event.price, 2),
        "change_pct": round(event.change_pct, 2),
        "created_at": event.created_at,
    }


def _claim(cache, user_id: int, code: str, rule_key: str, level: str, force: bool) -> bool:
    key = f"guanlan:dedupe:{user_id}:{code}:{rule_key}"
    if force:
        cache.delete(key)
    return bool(cache.set(key, "1", nx=True, ex=DEDUPE_TTL.get(level, 240)))


def persist_signals(
    db: Session,
    cache,
    user: User,
    quote: Quote,
    signals: list[Signal],
    *,
    force: bool,
) -> list[AlertEvent]:
    created: list[AlertEvent] = []
    now = datetime.now(timezone.utc)
    for signal in signals:
        if not _claim(cache, user.id, quote.code, signal.rule_key, signal.level, force):
            continue
        event = AlertEvent(
            user_id=user.id,
            code=quote.code,
            name=quote.name,
            level=signal.level,
            rule_key=signal.rule_key,
            title=signal.title,
            reason=signal.reason[:280],
            price=round(quote.price, 2),
            change_pct=round(quote.day_change_pct, 2),
            created_at=now,
        )
        db.add(event)
        created.append(event)
    if created:
        db.flush()
    return created


def publish_events(cache, events: list[AlertEvent]) -> None:
    for event in events:
        try:
            payload = to_alert_dict(event)
            created = payload["created_at"]
            if isinstance(created, datetime):
                payload["created_at"] = created.isoformat()
            cache.publish("guanlan:alerts", json.dumps(payload, ensure_ascii=False))
        except Exception:
            logger.exception("告警推送失败")


def poll_interval_seconds(*, source: str, session_open: bool, scan_interval: int, offhours_interval: int) -> int:
    chosen = scan_interval if source == "mock" or session_open else offhours_interval
    return max(3, int(chosen))


def rebase_catalog_ref(item, quote) -> bool:
    if getattr(quote, "stale", False) or getattr(quote, "source", "mock") == "mock":
        return False
    meta = BY_CODE.get(item.code)
    if meta is None:
        return False
    if abs(item.ref_price - meta.base_price) > 0.02:
        return False
    if abs(quote.price - meta.base_price) <= 0.02:
        return False
    previous = item.ref_price
    item.ref_price = round(quote.price, 2)
    logger.info("参考价从演示锚点 %.2f 调整为现价 %.2f %s", previous, item.ref_price, item.code)
    return True


def apply_shock(code: str, kind: str, item: WatchlistItem | None) -> Quote:
    provider = get_provider()
    if not provider.supports_shock():
        raise ShockError("当前使用腾讯行情，模拟冲击已关闭。把 QUOTE_SOURCE 设为 mock 可在本地回退。")
    if kind == "swing_up":
        return provider.shock(code, pct=3.6, reset_window=False)
    if kind == "swing_down":
        return provider.shock(code, pct=-3.6, reset_window=False)
    if kind == "breakout":
        return provider.shock(code, breakout=True, reset_window=True)
    if kind == "volume":
        return provider.shock(code, volume_ratio=3.4, reset_window=True)
    if kind == "stop":
        if item is None or item.ref_price <= 0:
            raise ShockError("先把这只股票加入自选，才能模拟止损")
        target = item.ref_price * (1 - (item.stop_loss_pct + 0.2) / 100)
        return provider.shock(code, price=target, reset_window=True)
    raise ShockError("不认识的模拟类型")


def shock_note(kind_signals: list[Signal]) -> str:
    if any(signal.level in {"risk", "anomaly"} for signal in kind_signals):
        return "模拟行情已更新，告警已写入告警流。观澜不会因此下单。"
    if kind_signals:
        return "行情已改写，目前只到观察级别，尚未越过你设置的异动或风控阈值。"
    return "行情已改写，但对应规则没有开启，所以没有新告警。"


def run_shock(db: Session, user: User, code: str, kind: str) -> tuple[Quote, list[AlertEvent], str]:
    with _gate:
        return _run_shock(db, user, code, kind)


def _run_shock(db: Session, user: User, code: str, kind: str) -> tuple[Quote, list[AlertEvent], str]:
    if code not in BY_CODE:
        raise ShockError("演示行情里没有这只股票")
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.code == code))
    rule = get_or_create_rule(db, user)
    quote = apply_shock(code, kind, item)
    matched = [signal for signal in signals_for(rule, item, quote) if signal.rule_key in KIND_KEYS[kind]]
    hard = [signal for signal in matched if signal.level in {"risk", "anomaly"}]
    chosen = hard or matched
    events = persist_signals(db, get_redis(), user, quote, chosen, force=True)
    _save_snapshot(db, quote, rule)
    db.commit()
    publish_events(get_redis(), events)
    return quote, events, shock_note(chosen)


def build_watch_item(rule: AlertRule, item: WatchlistItem, quote: Quote) -> dict:
    signals = signals_for(rule, item, quote)
    status = board_status(signals)
    return {
        "code": item.code,
        "name": item.name,
        "price": round(quote.price, 2),
        "prev_close": round(quote.prev_close, 2),
        "change_pct": round(quote.day_change_pct, 2),
        "volume_ratio": round(quote.volume_ratio, 2),
        "status": status,
        "status_label": STATUS_LABEL[status],
        "latest_signal": live_signal_text(signals) or "平稳",
        "stop_loss_pct": item.stop_loss_pct,
        "ref_price": round(item.ref_price, 2),
        "stale": quote.stale,
    }


def _save_snapshot(db: Session, quote: Quote, rule: AlertRule) -> None:
    db.add(
        QuoteSnapshot(
            code=quote.code,
            price=round(quote.price, 2),
            prev_close=round(quote.prev_close, 2),
            change_pct=round(quote.day_change_pct, 2),
            open=round(quote.open, 2),
            high=round(quote.day_high, 2),
            low=round(quote.day_low, 2),
            volume_ratio=round(quote.volume_ratio, 2),
            high_20d=round(quote.high_20d, 2),
            window_change_pct=round(quote.window_change_pct(rule.swing_window_minutes), 2),
            ts=datetime.now(timezone.utc),
        )
    )


def scan_once() -> None:
    with _gate:
        _scan_once()


def _scan_once() -> None:
    global _tick_index, _last_poll
    from app.config import settings
    from app.db import SessionLocal

    provider = get_provider()
    interval = poll_interval_seconds(
        source=provider.source,
        session_open=within_trading_session(datetime.now(timezone.utc)),
        scan_interval=settings.scan_interval_seconds,
        offhours_interval=settings.offhours_scan_interval_seconds,
    )
    now_mono = time.monotonic()
    if _last_poll and now_mono - _last_poll < interval - 0.5:
        return
    _last_poll = now_mono
    _tick_index += 1
    provider.refresh()
    try:
        from app.market import get_market_board

        get_market_board().refresh()
    except Exception:
        logger.warning("大盘扫描失败，个股扫描继续", exc_info=True)
    db = SessionLocal()
    try:
        cache = get_redis()
        users = list(db.scalars(select(User)).all())
        pending: list[AlertEvent] = []
        now = datetime.now(timezone.utc)
        for user in users:
            rule = get_or_create_rule(db, user)
            items = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == user.id)).all())
            allow = alerts_allowed(rule.trading_hours_only, now)
            if settings.demo_auto_pulse and provider.supports_shock() and allow and items:
                held = {item.code for item in items if provider.is_holding(item.code)}
                choice = choose_pulse(_tick_index, [item.code for item in items], held)
                if choice:
                    code, kind = choice
                    item = next(row for row in items if row.code == code)
                    apply_shock(code, kind, item)
                    logger.info("演示脉冲 %s %s", code, kind)
            for item in items:
                ensure = getattr(provider, "ensure", None)
                if callable(ensure):
                    try:
                        ensure(item.code, item.name)
                    except Exception:
                        continue
                pin = getattr(provider, "pin", None)
                if callable(pin):
                    pin(item.code)
                try:
                    quote = provider.get(item.code)
                except KeyError:
                    continue
                if quote.stale:
                    continue
                rebase_catalog_ref(item, quote)
                quote = provider.get(item.code)
                _save_snapshot(db, quote, rule)
                if not allow:
                    continue
                pending.extend(persist_signals(db, cache, user, quote, signals_for(rule, item, quote), force=False))
        cutoff = now - timedelta(hours=6)
        db.execute(delete(QuoteSnapshot).where(QuoteSnapshot.ts < cutoff))
        db.commit()
        publish_events(cache, pending)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def safe_scan() -> None:
    try:
        scan_once()
    except Exception:
        logger.exception("行情扫描失败")


def session_open() -> bool:
    return within_trading_session(datetime.now(timezone.utc))


def quote_source_name() -> str:
    from app.config import settings

    return settings.quote_source.strip().lower() or "tencent"


def market_name() -> str:
    return "模拟行情" if quote_source_name() == "mock" else "腾讯行情"


def session_label() -> str:
    if session_open():
        return "交易中"
    if quote_source_name() == "mock":
        return "非交易时段"
    return "已收盘，显示最近成交价"


def rule_payload(rule: AlertRule) -> dict:
    return {
        "breakout_20d_enabled": rule.breakout_20d_enabled,
        "swing_enabled": rule.swing_enabled,
        "swing_window_minutes": rule.swing_window_minutes,
        "swing_threshold_pct": rule.swing_threshold_pct,
        "stop_loss_enabled": rule.stop_loss_enabled,
        "default_stop_loss_pct": rule.default_stop_loss_pct,
        "volume_spike_enabled": rule.volume_spike_enabled,
        "volume_ratio_threshold": rule.volume_ratio_threshold,
        "trading_hours_only": rule.trading_hours_only,
        "trading_session_open": session_open(),
    }
