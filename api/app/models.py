from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_watch_user_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(6))
    name: Mapped[str] = mapped_column(String(32))
    ref_price: Mapped[float] = mapped_column(Float)
    stop_loss_pct: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    breakout_20d_enabled: Mapped[bool] = mapped_column(default=True)
    swing_enabled: Mapped[bool] = mapped_column(default=True)
    swing_window_minutes: Mapped[int] = mapped_column(default=5)
    swing_threshold_pct: Mapped[float] = mapped_column(Float, default=3)
    stop_loss_enabled: Mapped[bool] = mapped_column(default=True)
    default_stop_loss_pct: Mapped[float] = mapped_column(Float, default=8)
    volume_spike_enabled: Mapped[bool] = mapped_column(default=True)
    volume_ratio_threshold: Mapped[float] = mapped_column(Float, default=2.5)
    trading_hours_only: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        CheckConstraint("level in ('observe', 'anomaly', 'risk')", name="ck_alert_level"),
        Index("ix_alerts_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code: Mapped[str] = mapped_column(String(6), index=True)
    name: Mapped[str] = mapped_column(String(32))
    level: Mapped[str] = mapped_column(String(16))
    rule_key: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(280))
    price: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuoteSnapshot(Base):
    __tablename__ = "quote_snapshots"
    __table_args__ = (Index("ix_quote_code_ts", "code", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(6))
    price: Mapped[float] = mapped_column(Float)
    prev_close: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float] = mapped_column(Float)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    volume_ratio: Mapped[float] = mapped_column(Float)
    high_20d: Mapped[float] = mapped_column(Float)
    window_change_pct: Mapped[float] = mapped_column(Float)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
