"""Sina Market Center board for a larger A-share quote pool (no key)."""

from __future__ import annotations

import json
import logging
import urllib.request

from app.quotes import money

logger = logging.getLogger("guanlan.insights")

SINA_HQ_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page={page}&num={num}&sort=amount&asc=0&node=hs_a"
)


def _num(value) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_sina_hq(payload) -> list[dict]:
    if not isinstance(payload, list):
        return []
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if len(code) != 6 or not code.isdigit():
            continue
        price = money(_num(item.get("trade")))
        prev = money(_num(item.get("settlement")))
        if price <= 0:
            price = prev
        if price <= 0:
            continue
        # Sina mktcap / nmc are in 万元 → convert to 亿元 for the rest of the app.
        market_cap = round(_num(item.get("mktcap")) / 10000, 2)
        rows.append(
            {
                "code": code,
                "name": str(item.get("name") or code).strip(),
                "price": price,
                "prev_close": prev or price,
                "change_pct": round(_num(item.get("changepercent")), 2),
                "volume_ratio": 0.0,
                "turnover": float(round(max(_num(item.get("amount")), 0))),
                "market_cap": market_cap,
            }
        )
    return rows


def fetch_sina_hs_a(pages: int = 2, num: int = 50, timeout: float = 6.0) -> list[dict]:
    pages = max(1, min(pages, 4))
    num = max(10, min(num, 80))
    found: dict[str, dict] = {}
    for page in range(1, pages + 1):
        url = SINA_HQ_URL.format(page=page, num=num)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://vip.stock.finance.sina.com.cn/",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        for row in parse_sina_hq(payload):
            found[row["code"]] = row
    return list(found.values())
