"""Public Tencent A-share HTTP quotes. No API key.

Spot quotes come from https://qt.gtimg.cn/q=sh600519,sz000001 and are GBK.
Daily qfq bars come from the ifzq fqkline endpoint and are UTF-8 JSON.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

from app.quotes import Candle, money

SPOT_URL = "https://qt.gtimg.cn/q="
KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
INDEX_SYMBOLS = ("sh000001", "sz399001", "sz399006")
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://gu.qq.com/",
}


@dataclass(frozen=True)
class Spot:
    code: str
    name: str
    price: float
    prev_close: float
    open: float
    day_high: float
    day_low: float
    volume_ratio: float


def to_symbol(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sz{code}"


def _num(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_tencent_payload(text: str) -> dict[str, Spot]:
    found: dict[str, Spot] = {}
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if "=" not in chunk or "~" not in chunk:
            continue
        body = chunk.split("=", 1)[1].strip().strip('"')
        fields = body.split("~")
        if len(fields) < 50:
            continue
        code = fields[2].strip()
        if len(code) != 6 or not code.isdigit():
            continue
        price = _num(fields[3])
        prev_close = _num(fields[4])
        if price <= 0:
            price = prev_close
        if price <= 0 or prev_close <= 0:
            continue
        found[code] = Spot(
            code=code,
            name=fields[1].strip() or code,
            price=money(price),
            prev_close=money(prev_close),
            open=money(_num(fields[5]) or price),
            day_high=money(_num(fields[33]) or price),
            day_low=money(_num(fields[34]) or price),
            volume_ratio=round(_num(fields[49]), 2),
        )
    return found


def parse_kline_payload(payload: dict, symbol: str) -> tuple[list[Candle], float]:
    node = (payload.get("data") or {}).get(symbol) or {}
    rows = node.get("qfqday") or node.get("day") or []
    candles: list[Candle] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        candles.append(
            Candle(
                date=str(row[0]),
                open=money(_num(str(row[1]))),
                high=money(_num(str(row[3]))),
                low=money(_num(str(row[4]))),
                close=money(_num(str(row[2]))),
            )
        )
    if len(candles) < 2:
        return candles, 0.0
    window = candles[-21:-1] if len(candles) > 21 else candles[:-1]
    return candles, money(max(item.high for item in window))


def _read(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


@dataclass(frozen=True)
class IndexSpot:
    symbol: str
    code: str
    name: str
    price: float
    prev_close: float
    change_pct: float
    turnover: float


def parse_index_payload(text: str) -> dict[str, IndexSpot]:
    found: dict[str, IndexSpot] = {}
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if "=" not in chunk or "~" not in chunk:
            continue
        left, right = chunk.split("=", 1)
        symbol = left.strip()
        if symbol.startswith("v_"):
            symbol = symbol[2:]
        if not symbol.startswith(("sh", "sz", "bj")):
            continue
        fields = right.strip().strip('"').split("~")
        if len(fields) < 35:
            continue
        code = fields[2].strip()
        if len(code) != 6 or not code.isdigit():
            continue
        price = _num(fields[3])
        prev_close = _num(fields[4])
        if price <= 0:
            price = prev_close
        if price <= 0 or prev_close <= 0:
            continue
        change_pct = _num(fields[32]) if len(fields) > 32 and fields[32] != "" else (price - prev_close) / prev_close * 100
        turnover_wan = _num(fields[57]) if len(fields) > 57 and fields[57] != "" else 0.0
        if turnover_wan <= 0 and len(fields) > 37:
            turnover_wan = _num(fields[37])
        found[symbol] = IndexSpot(
            symbol=symbol,
            code=code,
            name=fields[1].strip() or code,
            price=money(price),
            prev_close=money(prev_close),
            change_pct=round(change_pct, 2),
            turnover=float(round(turnover_wan * 10000)),
        )
    return found


def fetch_indices(symbols: list[str] | None = None, timeout: float = 3.0) -> dict[str, IndexSpot]:
    chosen = [symbol for symbol in (symbols or list(INDEX_SYMBOLS)) if symbol]
    if not chosen:
        return {}
    raw = _read(SPOT_URL + ",".join(chosen), timeout)
    return parse_index_payload(raw.decode("gbk", errors="replace"))


def fetch_spot(codes: list[str], timeout: float = 3.0) -> dict[str, Spot]:
    symbols = [to_symbol(code) for code in codes if code]
    if not symbols:
        return {}
    raw = _read(SPOT_URL + ",".join(symbols), timeout)
    return parse_tencent_payload(raw.decode("gbk", errors="replace"))


@dataclass(frozen=True)
class BoardSpot:
    code: str
    name: str
    price: float
    prev_close: float
    change_pct: float
    volume_ratio: float
    turnover: float
    market_cap: float


def parse_board_payload(text: str) -> dict[str, BoardSpot]:
    found: dict[str, BoardSpot] = {}
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if "=" not in chunk or "~" not in chunk:
            continue
        body = chunk.split("=", 1)[1].strip().strip('"')
        fields = body.split("~")
        if len(fields) < 50:
            continue
        code = fields[2].strip()
        if len(code) != 6 or not code.isdigit():
            continue
        price = _num(fields[3])
        prev_close = _num(fields[4])
        if price <= 0:
            price = prev_close
        if price <= 0:
            continue
        change_pct = _num(fields[32]) if fields[32] != "" else ((price - prev_close) / prev_close * 100 if prev_close else 0)
        turnover_wan = _num(fields[57]) if len(fields) > 57 and fields[57] != "" else _num(fields[37])
        found[code] = BoardSpot(
            code=code,
            name=fields[1].strip() or code,
            price=money(price),
            prev_close=money(prev_close or price),
            change_pct=round(change_pct, 2),
            volume_ratio=round(_num(fields[49]), 2),
            turnover=float(round(max(turnover_wan, 0) * 10000)),
            market_cap=round(_num(fields[45]), 2),
        )
    return found


def fetch_board(codes: list[str], timeout: float = 4.0) -> dict[str, BoardSpot]:
    symbols = [to_symbol(code) for code in codes if code]
    if not symbols:
        return {}
    raw = _read(SPOT_URL + ",".join(symbols), timeout)
    return parse_board_payload(raw.decode("gbk", errors="replace"))


def fetch_bars(code: str, period: str = "day", count: int = 80, timeout: float = 4.0) -> list[Candle]:
    if period not in {"day", "week"}:
        raise ValueError("period")
    symbol = to_symbol(code)
    raw = _read(f"{KLINE_URL}?param={symbol},{period},,,{count},qfq", timeout)
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    node = (payload.get("data") or {}).get(symbol) or {}
    rows = node.get(f"qfq{period}") or node.get(period) or []
    candles: list[Candle] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        candles.append(
            Candle(
                date=str(row[0]),
                open=money(_num(str(row[1]))),
                high=money(_num(str(row[3]))),
                low=money(_num(str(row[4]))),
                close=money(_num(str(row[2]))),
            )
        )
    return candles


def fetch_minute(code: str, timeout: float = 4.0) -> list[dict]:
    symbol = to_symbol(code)
    raw = _read(f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}", timeout)
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    rows = (((payload.get("data") or {}).get(symbol) or {}).get("data") or {}).get("data") or []
    points = []
    for row in rows:
        parts = str(row).split()
        if len(parts) < 2:
            continue
        price = _num(parts[1])
        if price <= 0:
            continue
        points.append({"time": parts[0], "price": money(price)})
    return points


def fetch_klines(code: str, timeout: float = 3.0) -> tuple[list[Candle], float]:
    symbol = to_symbol(code)
    raw = _read(f"{KLINE_URL}?param={symbol},day,,,40,qfq", timeout)
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    return parse_kline_payload(payload, symbol)
