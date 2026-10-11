from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Level = Literal["observe", "anomaly", "risk"]
ShockKind = Literal["swing_up", "swing_down", "breakout", "volume", "stop"]


class AlertOut(BaseModel):
    id: int
    code: str
    name: str
    level: Level
    level_label: str
    rule_key: str
    title: str
    reason: str
    price: float
    change_pct: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertListOut(BaseModel):
    events: list[AlertOut]
    disclaimer: str


class WatchItemOut(BaseModel):
    code: str
    name: str
    price: float
    prev_close: float
    change_pct: float
    volume_ratio: float
    status: Level
    status_label: str
    latest_signal: str
    stop_loss_pct: float
    ref_price: float
    stale: bool = False


class WatchlistOut(BaseModel):
    items: list[WatchItemOut]
    trading_hours_only: bool
    trading_session_open: bool
    disclaimer: str
    quote_source: str = "tencent"
    quote_stale: bool = False
    session_label: str = ""


class AddWatchIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)


class WatchWriteOut(BaseModel):
    code: str
    name: str


class PatchWatchIn(BaseModel):
    stop_loss_pct: float | None = Field(default=None, ge=0.5, le=40)
    reset_ref: bool = False


class PatchWatchOut(BaseModel):
    code: str
    stop_loss_pct: float
    ref_price: float


class RuleIn(BaseModel):
    breakout_20d_enabled: bool
    swing_enabled: bool
    swing_window_minutes: int = Field(ge=1, le=30)
    swing_threshold_pct: float = Field(ge=0.5, le=20)
    stop_loss_enabled: bool
    default_stop_loss_pct: float = Field(ge=0.5, le=40)
    volume_spike_enabled: bool
    volume_ratio_threshold: float = Field(ge=1.1, le=10)
    trading_hours_only: bool


class RuleOut(RuleIn):
    trading_session_open: bool


class CandleOut(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float


class TriggerOut(BaseModel):
    rule_key: str
    title: str
    enabled: bool
    hit: bool
    level: str
    detail: str


class StockOut(BaseModel):
    code: str
    name: str
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    change_pct: float
    volume_ratio: float
    high_20d: float
    in_watchlist: bool
    stop_loss_pct: float | None
    ref_price: float | None
    status: Level
    status_label: str
    triggers: list[TriggerOut]
    candles: list[CandleOut]
    disclaimer: str
    stale: bool = False
    quote_source: str = "tencent"
    session_label: str = ""


class SearchHit(BaseModel):
    code: str
    name: str


class SearchOut(BaseModel):
    items: list[SearchHit]


class ShockIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    kind: ShockKind


class ShockOut(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float
    alerts: list[AlertOut]
    note: str
    disclaimer: str


class MetaOut(BaseModel):
    name: str
    disclaimer: str
    demo_user: str
    scan_interval_seconds: int
    demo_auto_pulse: bool
    trading_session_open: bool
    market: str
    quote_source: str = "tencent"
    offhours_scan_interval_seconds: int = 60
    session_label: str = ""


class IndexOut(BaseModel):
    symbol: str
    code: str
    name: str
    price: float
    prev_close: float
    change_pct: float
    turnover: float
    stale: bool = False


class BreadthOut(BaseModel):
    up: int = 0
    down: int = 0
    flat: int = 0
    total: int = 0
    source: str = ""
    stale: bool = True
    note: str = ""


class MarketOut(BaseModel):
    indices: list[IndexOut]
    breadth: BreadthOut | None = None
    quote_source: str
    quote_stale: bool
    session_label: str
    disclaimer: str


class OkOut(BaseModel):
    ok: bool = True
