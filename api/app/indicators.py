"""Common technical indicators on daily or weekly closes."""

from __future__ import annotations


def _ema(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period")
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    alpha = 2 / (period + 1)
    prev = seed
    for index in range(period, len(values)):
        prev = values[index] * alpha + prev * (1 - alpha)
        out[index] = prev
    return out


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> list[dict]:
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    dif: list[float | None] = []
    for fast_value, slow_value in zip(ema_fast, ema_slow, strict=True):
        if fast_value is None or slow_value is None:
            dif.append(None)
        else:
            dif.append(fast_value - slow_value)
    ready = [value for value in dif if value is not None]
    dea_tail = _ema(ready, signal) if ready else []
    dea: list[float | None] = [None] * len(closes)
    cursor = 0
    for index, value in enumerate(dif):
        if value is None:
            continue
        dea[index] = dea_tail[cursor]
        cursor += 1
    rows = []
    for index, close in enumerate(closes):
        dif_value = dif[index]
        dea_value = dea[index]
        hist = None if dif_value is None or dea_value is None else (dif_value - dea_value) * 2
        rows.append(
            {
                "close": close,
                "dif": None if dif_value is None else round(dif_value, 4),
                "dea": None if dea_value is None else round(dea_value, 4),
                "hist": None if hist is None else round(hist, 4),
            }
        )
    return rows


def rsi(closes: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        delta = closes[index] - closes[index - 1]
        gains += max(delta, 0)
        losses += max(-delta, 0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for index in range(period + 1, len(closes)):
        delta = closes[index] - closes[index - 1]
        avg_gain = (avg_gain * (period - 1) + max(delta, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-delta, 0)) / period
        out[index] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return [None if value is None else round(value, 2) for value in out]


def kdj(highs: list[float], lows: list[float], closes: list[float], period: int = 9) -> list[dict]:
    rows = []
    k_prev = 50.0
    d_prev = 50.0
    for index, close in enumerate(closes):
        if index + 1 < period:
            rows.append({"k": None, "d": None, "j": None})
            continue
        window_high = max(highs[index + 1 - period : index + 1])
        window_low = min(lows[index + 1 - period : index + 1])
        span = window_high - window_low
        rsv = 50.0 if span <= 0 else (close - window_low) / span * 100
        k_prev = (2 * k_prev + rsv) / 3
        d_prev = (2 * d_prev + k_prev) / 3
        j_value = 3 * k_prev - 2 * d_prev
        rows.append({"k": round(k_prev, 2), "d": round(d_prev, 2), "j": round(j_value, 2)})
    return rows


def boll(closes: list[float], period: int = 20, width: float = 2.0) -> list[dict]:
    rows = []
    for index, close in enumerate(closes):
        if index + 1 < period:
            rows.append({"mid": None, "upper": None, "lower": None})
            continue
        window = closes[index + 1 - period : index + 1]
        mid = sum(window) / period
        var = sum((value - mid) ** 2 for value in window) / period
        std = var ** 0.5
        rows.append(
            {
                "mid": round(mid, 4),
                "upper": round(mid + width * std, 4),
                "lower": round(mid - width * std, 4),
            }
        )
    return rows


def composite_rating(dif: float | None, dea: float | None, rsi_value: float | None, k_value: float | None, d_value: float | None, close: float, mid: float | None) -> dict:
    score = 0
    reasons: list[str] = []
    if dif is not None and dea is not None:
        if dif >= dea:
            score += 1
            reasons.append("MACD DIF 不低于 DEA")
        else:
            score -= 1
            reasons.append("MACD DIF 低于 DEA")
    if rsi_value is not None:
        if rsi_value >= 55:
            score += 1
            reasons.append(f"RSI {rsi_value:.1f} 偏强")
        elif rsi_value <= 45:
            score -= 1
            reasons.append(f"RSI {rsi_value:.1f} 偏弱")
        else:
            reasons.append(f"RSI {rsi_value:.1f} 中性")
    if k_value is not None and d_value is not None:
        if k_value >= d_value:
            score += 1
            reasons.append("KDJ K 不低于 D")
        else:
            score -= 1
            reasons.append("KDJ K 低于 D")
    if mid is not None and mid > 0:
        if close >= mid:
            score += 1
            reasons.append("收盘价在布林中轨之上")
        else:
            score -= 1
            reasons.append("收盘价在布林中轨之下")
    if score >= 3:
        label = "偏多"
    elif score == 2:
        label = "中性偏多"
    elif score <= -3:
        label = "偏空"
    elif score == -2:
        label = "中性偏空"
    else:
        label = "中性"
    return {"label": label, "score": score, "reasons": reasons}
