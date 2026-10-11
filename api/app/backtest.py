"""Two close-to-close research backtests. No fees, no shorting, no orders."""

from __future__ import annotations


def run_backtest(candles: list, strategy: str) -> dict:
    if strategy not in {"momentum", "mean_reversion"}:
        raise ValueError("未知策略")
    closes = [float(item.close) for item in candles]
    dates = [str(item.date) for item in candles]
    lookback = 10
    title = "动量" if strategy == "momentum" else "高抛低吸"
    if len(closes) < lookback + 5:
        return {
            "strategy": strategy,
            "title": title,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "trade_count": 0,
            "equity": [],
            "trades": [],
            "note": "K 线不足，没有做回测。",
        }
    position = 0
    entry = 0.0
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    curve = []
    trades = []
    wins = 0
    closed = 0
    for index in range(lookback, len(closes) - 1):
        price = closes[index]
        nxt = closes[index + 1]
        if strategy == "momentum":
            want = 1 if price > closes[index - lookback] else 0
        else:
            window = closes[index - lookback + 1 : index + 1]
            average = sum(window) / len(window)
            if position == 0 and price < average * 0.98:
                want = 1
            elif position == 1 and price > average * 1.02:
                want = 0
            else:
                want = position
        if want != position:
            if want == 1:
                trades.append({"date": dates[index], "side": "买入", "price": round(price, 2), "pnl_pct": None})
                entry = price
            else:
                pnl = 0.0 if entry <= 0 else (price - entry) / entry * 100
                trades.append({"date": dates[index], "side": "卖出", "price": round(price, 2), "pnl_pct": round(pnl, 2)})
                closed += 1
                if pnl > 0:
                    wins += 1
                entry = 0.0
            position = want
        if position == 1 and price > 0:
            equity *= nxt / price
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100)
        curve.append({"date": dates[index + 1], "equity": round(equity, 4)})
    return {
        "strategy": strategy,
        "title": title,
        "total_return_pct": round((equity - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round((wins / closed * 100) if closed else 0.0, 2),
        "trade_count": len(trades),
        "equity": curve,
        "trades": trades[-40:],
        "note": "用前复权日 K 收盘价模拟，不计手续费和滑点，不会下单。仅供研究参考，不构成投资建议。",
    }
