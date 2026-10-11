"""In-memory A-share quotes. Swap this provider without touching the rule engine."""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.universe import STOCKS, StockMeta

HOLD_SECONDS = 90
HISTORY_MINUTES = 35


def money(value: float) -> float:
    return round(value + 1e-9, 2)


@dataclass(frozen=True)
class Candle:
    date: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    price: float
    prev_close: float
    open: float
    day_high: float
    day_low: float
    high_20d: float
    volume_ratio: float
    candles: tuple[Candle, ...]
    history: tuple[tuple[float, float], ...]
    source: str = "mock"
    stale: bool = False

    @property
    def day_change_pct(self) -> float:
        if self.prev_close <= 0:
            return 0.0
        return (self.price - self.prev_close) / self.prev_close * 100

    def window_change_pct(self, minutes: int) -> float:
        if not self.history:
            return 0.0
        now = self.history[-1][0]
        target = now - max(minutes, 1) * 60
        anchor = self.history[0][1]
        for ts, price in self.history:
            if ts <= target:
                anchor = price
            else:
                break
        if anchor <= 0:
            return 0.0
        return (self.price - anchor) / anchor * 100


@dataclass
class _State:
    code: str
    name: str
    base: float
    base_volume: float
    price: float
    prev_close: float
    open: float
    day_high: float
    day_low: float
    high_20d: float
    volume_ratio: float
    candles: list[Candle]
    history: deque[tuple[float, float]]
    hold_until: float
    pinned: bool = True


def _build_candles(code: str, base: float) -> tuple[list[Candle], float]:
    rng = random.Random(int(code))
    price = base * 0.9
    raw: list[tuple[float, float, float, float]] = []
    for _ in range(40):
        opened = price
        closed = max(0.5, opened * (1 + rng.uniform(-0.018, 0.021)))
        high = max(opened, closed) * (1 + rng.uniform(0.001, 0.01))
        low = min(opened, closed) * (1 - rng.uniform(0.001, 0.01))
        raw.append((opened, high, low, closed))
        price = closed
    factor = base / raw[-1][3]
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    start = today - timedelta(days=39)
    candles: list[Candle] = []
    for index, (opened, high, low, closed) in enumerate(raw):
        candles.append(
            Candle(
                date=(start + timedelta(days=index)).isoformat(),
                open=money(opened * factor),
                high=money(high * factor),
                low=money(low * factor),
                close=money(closed * factor),
            )
        )
    last = candles[-1]
    close = money(base)
    candles[-1] = Candle(
        date=last.date,
        open=last.open,
        high=money(max(last.high, close)),
        low=money(min(last.low, close)),
        close=close,
    )
    prior = candles[-21:-1]
    high_20d = max(item.high for item in prior)
    if high_20d <= close * 1.005:
        high_20d = money(close * 1.03)
    return candles, high_20d


class MockQuoteProvider:
    def __init__(self, stocks: tuple[StockMeta, ...] | None = None) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, _State] = {}
        now = time.monotonic()
        for meta in stocks or STOCKS:
            candles, high_20d = _build_candles(meta.code, meta.base_price)
            volume_rng = random.Random(int(meta.code) + 17)
            base_volume = round(volume_rng.uniform(0.9, 1.3), 2)
            price = candles[-1].close
            state = _State(
                code=meta.code,
                name=meta.name,
                base=price,
                base_volume=base_volume,
                price=price,
                prev_close=candles[-2].close,
                open=candles[-1].open,
                day_high=candles[-1].high,
                day_low=candles[-1].low,
                high_20d=high_20d,
                volume_ratio=base_volume,
                candles=candles,
                history=deque(maxlen=500),
                hold_until=0.0,
            )
            state.history.append((now, price))
            self._states[meta.code] = state

    @property
    def source(self) -> str:
        return "mock"

    def supports_shock(self) -> bool:
        return True

    def refresh(self) -> None:
        self.tick_all()

    def get(self, code: str) -> Quote:
        with self._lock:
            state = self._states.get(code)
            if state is None:
                raise KeyError(code)
            return self._to_quote(state)

    def ensure(self, code: str, name: str = "") -> None:
        cleaned = code.strip()
        with self._lock:
            if cleaned in self._states:
                return
            base = 10.0
            candles, high_20d = _build_candles(cleaned, base)
            now = time.monotonic()
            self._states[cleaned] = _State(
                code=cleaned,
                name=name or cleaned,
                base=base,
                base_volume=1.0,
                price=candles[-1].close,
                prev_close=candles[-2].close,
                open=candles[-1].open,
                day_high=candles[-1].high,
                day_low=candles[-1].low,
                high_20d=high_20d,
                volume_ratio=1.0,
                candles=candles,
                history=deque([(now, candles[-1].close)], maxlen=500),
                hold_until=0.0,
                pinned=False,
            )

    def pin(self, code: str) -> None:
        with self._lock:
            state = self._states.get(code)
            if state is not None:
                state.pinned = True

    def is_holding(self, code: str) -> bool:
        with self._lock:
            state = self._states.get(code)
            return state is not None and time.monotonic() < state.hold_until

    def tick_all(self) -> None:
        with self._lock:
            now = time.monotonic()
            for state in self._states.values():
                self._tick(state, now)

    def shock(
        self,
        code: str,
        *,
        pct: float | None = None,
        price: float | None = None,
        volume_ratio: float | None = None,
        breakout: bool = False,
        reset_window: bool = False,
    ) -> Quote:
        with self._lock:
            state = self._states.get(code)
            if state is None:
                raise KeyError(code)
            if breakout:
                state.price = money(max(0.01, state.high_20d * 1.006))
            elif price is not None:
                state.price = money(max(0.01, price))
            elif pct is not None:
                state.price = money(max(0.01, state.price * (1 + pct / 100.0)))
            if volume_ratio is not None:
                state.volume_ratio = round(max(0.1, volume_ratio), 2)
            now = time.monotonic()
            if reset_window:
                state.history.clear()
                state.history.append((now - 3600, state.price))
            state.history.append((now, state.price))
            state.hold_until = now + HOLD_SECONDS
            self._sync_candle(state)
            return self._to_quote(state)

    def _tick(self, state: _State, now: float) -> None:
        if now >= state.hold_until:
            state.price = money(state.price + (state.base - state.price) * 0.1)
            state.volume_ratio = round(
                max(0.1, state.volume_ratio + (state.base_volume - state.volume_ratio) * 0.2),
                2,
            )
            state.price = money(max(0.01, state.price * (1 + random.uniform(-0.0008, 0.0008))))
            self._sync_candle(state)
        state.history.append((now, state.price))
        cutoff = now - HISTORY_MINUTES * 60
        while len(state.history) > 2 and state.history[0][0] < cutoff:
            state.history.popleft()

    def _sync_candle(self, state: _State) -> None:
        current = state.candles[-1]
        state.candles[-1] = Candle(
            date=current.date,
            open=current.open,
            high=money(max(current.high, state.price)),
            low=money(min(current.low, state.price)),
            close=state.price,
        )
        state.day_high = money(max(state.day_high, state.price))
        state.day_low = money(min(state.day_low, state.price))

    def _to_quote(self, state: _State) -> Quote:
        return Quote(
            code=state.code,
            name=state.name,
            price=state.price,
            prev_close=state.prev_close,
            open=state.open,
            day_high=state.day_high,
            day_low=state.day_low,
            high_20d=state.high_20d,
            volume_ratio=state.volume_ratio,
            candles=tuple(state.candles),
            history=tuple(state.history),
        )


_provider: MockQuoteProvider | object | None = None


def get_provider():
    global _provider
    if _provider is None:
        from app.config import settings

        if settings.quote_source.strip().lower() == "mock":
            _provider = MockQuoteProvider()
        else:
            from app.live_quotes import TencentQuoteProvider

            _provider = TencentQuoteProvider()
    return _provider
