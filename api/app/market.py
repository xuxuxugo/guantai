"""Shanghai, Shenzhen and ChiNext index board. Same cadence as the quote scan."""

from __future__ import annotations

import logging
import threading

from app.breadth import breadth_from_rows, empty_breadth, fetch_breadth
from app.quotes import money
from app.tencent import INDEX_SYMBOLS, IndexSpot, fetch_indices

logger = logging.getLogger("guanlan.quotes")

INDEXES: tuple[tuple[str, str, str], ...] = (
    ("sh000001", "000001", "上证指数"),
    ("sz399001", "399001", "深证成指"),
    ("sz399006", "399006", "创业板指"),
)


class _Row:
    def __init__(self, symbol: str, code: str, name: str) -> None:
        self.symbol = symbol
        self.code = code
        self.name = name
        self.price = 0.0
        self.prev_close = 0.0
        self.change_pct = 0.0
        self.turnover = 0.0
        self.stale = True


class MarketBoard:
    def __init__(self, fetcher=None, breadth_fetcher=None, source: str = "tencent", autofetch: bool = True) -> None:
        self._lock = threading.Lock()
        self._rows = {symbol: _Row(symbol, code, name) for symbol, code, name in INDEXES}
        self._fetcher = fetcher or (lambda: fetch_indices(list(INDEX_SYMBOLS)))
        self._breadth_fetcher = breadth_fetcher or fetch_breadth
        self._breadth = empty_breadth(note="涨跌家数还没取到。")
        self._breadth_at = 0.0
        self._breadth_busy = False
        self.source = source
        if autofetch:
            self.refresh()

    def refresh(self, *, breadth: bool = True) -> None:
        import time

        try:
            spots = self._fetcher()
        except Exception:
            logger.warning("大盘行情拉取失败，保留上次指数", exc_info=True)
            with self._lock:
                for row in self._rows.values():
                    row.stale = True
        else:
            with self._lock:
                seen: set[str] = set()
                for symbol, spot in spots.items():
                    row = self._rows.get(symbol)
                    if row is None or not isinstance(spot, IndexSpot):
                        continue
                    seen.add(symbol)
                    row.name = spot.name or row.name
                    row.code = spot.code or row.code
                    row.price = money(spot.price)
                    row.prev_close = money(spot.prev_close)
                    row.change_pct = round(spot.change_pct, 2)
                    row.turnover = float(spot.turnover)
                    row.stale = False
                for symbol, row in self._rows.items():
                    if symbol not in seen:
                        row.stale = True

        if not breadth:
            return

        if self.source == "mock":
            with self._lock:
                self._breadth = {
                    "up": 2100,
                    "down": 1800,
                    "flat": 120,
                    "total": 4020,
                    "parts": [],
                    "source": "mock",
                    "stale": False,
                    "note": "模拟涨跌家数。",
                }
                self._breadth_at = time.monotonic()
            return

        # Full-market breadth may take several HTTP hops; never block the quote scan.
        now = time.monotonic()
        if self._breadth_at and now - self._breadth_at < 90 and self._breadth.get("total", 0) > 0:
            return
        if self._breadth_busy:
            return
        self._breadth_busy = True
        threading.Thread(target=self._refresh_breadth, daemon=True).start()

    def _refresh_breadth(self) -> None:
        import time

        now = time.monotonic()
        try:
            try:
                breadth = self._breadth_fetcher()
            except Exception:
                logger.warning("涨跌家数拉取失败，尝试样本池估算", exc_info=True)
                from app.insights import refresh_pool

                breadth = breadth_from_rows(refresh_pool())
            with self._lock:
                self._breadth = breadth
                self._breadth_at = time.monotonic()
        except Exception:
            logger.warning("样本池涨跌家数也不可用，保留上次结果", exc_info=True)
            with self._lock:
                note = self._breadth.get("note") or "涨跌家数延迟，显示上次结果。"
                if self._breadth.get("total", 0) > 0 and "延迟" not in note:
                    note = f"{note} 涨跌家数延迟，显示上次结果。"
                self._breadth = {**self._breadth, "stale": True, "note": note}
                self._breadth_at = now
        finally:
            self._breadth_busy = False

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "symbol": row.symbol,
                    "code": row.code,
                    "name": row.name,
                    "price": row.price,
                    "prev_close": row.prev_close,
                    "change_pct": row.change_pct,
                    "turnover": row.turnover,
                    "stale": row.stale,
                }
                for row in self._rows.values()
            ]

    def breadth(self) -> dict:
        with self._lock:
            return dict(self._breadth)


def mock_indices() -> dict[str, IndexSpot]:
    return {
        "sh000001": IndexSpot("sh000001", "000001", "上证指数", 3000.0, 2980.0, 0.67, 450_000_000_000),
        "sz399001": IndexSpot("sz399001", "399001", "深证成指", 10000.0, 9950.0, 0.50, 520_000_000_000),
        "sz399006": IndexSpot("sz399006", "399006", "创业板指", 2000.0, 1988.0, 0.60, 210_000_000_000),
    }


_board: MarketBoard | None = None
_board_lock = threading.Lock()


def get_market_board() -> MarketBoard:
    global _board
    if _board is not None:
        return _board
    with _board_lock:
        if _board is None:
            from app.config import settings

            if settings.quote_source.strip().lower() == "mock":
                _board = MarketBoard(fetcher=mock_indices, source="mock")
            else:
                _board = MarketBoard()
    return _board
