import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AlertEvent, AlertRule, User, WatchlistItem
from app.quotes import get_provider

logger = logging.getLogger("guanlan")

SEED_CODES = ("600519", "000001", "300750", "601318")


def seed(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return
    now = datetime.now(timezone.utc)
    user = User(username="demo", display_name="演示用户", created_at=now)
    db.add(user)
    db.flush()
    db.add(
        AlertRule(
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
    )
    provider = get_provider()
    for code in SEED_CODES:
        quote = provider.get(code)
        db.add(
            WatchlistItem(
                user_id=user.id,
                code=quote.code,
                name=quote.name,
                ref_price=quote.price,
                stop_loss_pct=8,
                created_at=now,
            )
        )
    history = [
        (
            170,
            "600519",
            "贵州茅台",
            "anomaly",
            "volume_spike",
            "量比突增",
            "量比 3.10，高于阈值 2.5",
            1436.50,
            0.82,
        ),
        (
            95,
            "000001",
            "平安银行",
            "observe",
            "swing_watch",
            "5分钟波动值得看一眼",
            "近5分钟上涨 2.10%，尚未达到 3% 阈值",
            11.78,
            0.51,
        ),
        (
            48,
            "300750",
            "宁德时代",
            "risk",
            "stop_loss",
            "触及止损",
            "现价 228.40，相对参考价 248.60 回撤 8.13%，止损线 8%",
            228.40,
            -4.20,
        ),
        (
            18,
            "601318",
            "中国平安",
            "anomaly",
            "breakout_20d",
            "突破20日高点",
            "现价 54.10 不低于近20日高点 53.80",
            54.10,
            1.62,
        ),
    ]
    for minutes_ago, code, name, level, rule_key, title, reason, price, change_pct in history:
        db.add(
            AlertEvent(
                user_id=user.id,
                code=code,
                name=name,
                level=level,
                rule_key=rule_key,
                title=title,
                reason=reason,
                price=price,
                change_pct=change_pct,
                created_at=now - timedelta(minutes=minutes_ago),
            )
        )
    db.commit()
    logger.info("已写入演示用户、自选和历史告警")
