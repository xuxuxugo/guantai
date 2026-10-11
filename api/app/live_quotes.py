"""Near-realtime A-share quotes from the public Tencent HTTP endpoints."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

from app.quotes import HISTORY_MINUTES, Candle, Quote, money
from app.tencent import Spot, fetch_klines, fetch_spot
from app.universe import STOCKS, StockMeta

logger = logging.getLogger("guanlan.quotes")

KLINE_REFRESH_SECONDS = 6 * 60 * 60
Fetcher = Callable[[list[str]], dict[str, Spot]]
KlineFetcher = Callable[[str], tuple[list[Candle], float]]


class _State:
    def __init__(self, meta: StockMeta, *, pinned: bool = True) -> None:
        self.code = meta.code
        self.name = meta.name
        self.price = meta.base_price
        self.prev_close = meta.base_price
        self.open = meta.base_price
        self.day_high = meta.base_price
        self.day_low = meta.base_price
        self.high_20d = 0.0
        self.volume_ratio = 0.0
        self.candles: list[Candle] = []
        self.history: deque[tuple[float, float]] = deque(maxlen=500)
        self.stale = True
        self.pinned = pinned


class TencentQuoteProvider:
    def __init__(
        self,
        stocks: tuple[StockMeta, ...] | None = None,
        fetcher: Fetcher | None = None,
        kline_fetcher: KlineFetcher | None = None,
        autofetch: bool = True,
    ) -> None:
        self._lock = threading.Lock()
        self._fetcher = fetcher or fetch_spot
        self._kline_fetcher = kline_fetcher or fetch_klines
        self._states = {meta.code: _State(meta) for meta in (stocks or STOCKS)}
        self._kline_at: dict[str, float] = {}
        self._kline_cursor = 0
        if autofetch:
            self.refresh()

    @property
    def source(self) -> str:
        return "tencent"

    def supports_shock(self) -> bool:
        return False

    def is_holding(self, code: str) -> bool:
        return False

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
            self._states[cleaned] = _State(StockMeta(cleaned, name or cleaned, 0.0), pinned=False)
        try:
            spots = self._fetcher([cleaned])
        except Exception as exc:
            with self._lock:
                self._states.pop(cleaned, None)
            raise KeyError(cleaned) from exc
        spot = spots.get(cleaned)
        if spot is None or spot.price <= 0:
            with self._lock:
                self._states.pop(cleaned, None)
            raise KeyError(cleaned)
        with self._lock:
            state = self._states.get(cleaned)
            if state is None:
                return
            state.name = spot.name or state.name
            state.price = money(spot.price)
            state.prev_close = money(spot.prev_close)
            state.open = money(spot.open)
            state.day_high = money(spot.day_high)
            state.day_low = money(spot.day_low)
            state.volume_ratio = round(spot.volume_ratio, 2)
            state.stale = False
            state.history.append((time.monotonic(), state.price))
            unpinned = [key for key, item in self._states.items() if not item.pinned]
            if len(unpinned) > 40:
                for key in unpinned[: len(unpinned) - 40]:
                    item = self._states.get(key)
                    if item is not None and not item.pinned:
                        self._states.pop(key, None)

    def pin(self, code: str) -> None:
        with self._lock:
            state = self._states.get(code)
            if state is not None:
                state.pinned = True

    def ensure_kline(self, code: str) -> None:
        with self._lock:
            state = self._states.get(code)
            if state is None or state.high_20d > 0:
                return
        self._store_kline(code)

    def refresh(self) -> None:
        with self._lock:
            codes = [code for code, state in self._states.items() if state.pinned]
        if not codes:
            return
        try:
            spots = self._fetcher(codes)
        except Exception:
            logger.warning("腾讯行情拉取失败，保留上次报价", exc_info=True)
            with self._lock:
                for state in self._states.values():
                    state.stale = True
            return
        now = time.monotonic()
        with self._lock:
            seen: set[str] = set()
            for code, spot in spots.items():
                state = self._states.get(code)
                if state is None:
                    continue
                seen.add(code)
                state.name = spot.name or state.name
                state.price = money(spot.price)
                state.prev_close = money(spot.prev_close)
                state.open = money(spot.open)
                state.day_high = money(spot.day_high)
                state.day_low = money(spot.day_low)
                state.volume_ratio = round(spot.volume_ratio, 2)
                state.stale = False
                state.history.append((now, state.price))
                cutoff = now - HISTORY_MINUTES * 60
                while len(state.history) > 2 and state.history[0][0] < cutoff:
                    state.history.popleft()
            for code, state in self._states.items():
                if code not in seen:
                    state.stale = True
        self._refresh_klines(codes)

    def _refresh_klines(self, codes: list[str]) -> None:
        now = time.monotonic()
        pending = [code for code in codes if now - self._kline_at.get(code, 0.0) >= KLINE_REFRESH_SECONDS]
        if not pending:
            return
        start = self._kline_cursor % len(pending)
        batch = [pending[(start + offset) % len(pending)] for offset in range(min(2, len(pending)))]
        self._kline_cursor += len(batch)
        for code in batch:
            self._store_kline(code)

    def _store_kline(self, code: str) -> None:
        try:
            candles, high_20d = self._kline_fetcher(code)
        except Exception:
            logger.warning("日 K 拉取失败 %s，20日高点沿用上次结果", code, exc_info=True)
            self._kline_at[code] = time.monotonic() - KLINE_REFRESH_SECONDS + 180
            return
        if high_20d <= 0:
            self._kline_at[code] = time.monotonic() - KLINE_REFRESH_SECONDS + 180
            return
        with self._lock:
            state = self._states.get(code)
            if state is None:
                return
            state.candles = list(candles)
            state.high_20d = high_20d
        self._kline_at[code] = time.monotonic()

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
            source=self.source,
            stale=state.stale,
        )
