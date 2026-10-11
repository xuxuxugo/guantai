"""A-share advance / decline counts from public quote APIs."""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger("guanlan.quotes")

BREADTH_PATH = (
    "/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001&fields=f104,f105,f106,f12,f14"
)
BREADTH_HOSTS = (
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
    "https://82.push2.eastmoney.com",
)
SINA_COUNT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCount?node=hs_a"
)
SINA_PAGE_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData?page={page}&num={num}&sort=changepercent&asc=0&node=hs_a"
)


def parse_breadth_payload(payload: dict) -> dict:
    rows = ((payload.get("data") or {}).get("diff")) or []
    up = down = flat = 0
    parts = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        item_up = int(item.get("f104") or 0)
        item_down = int(item.get("f105") or 0)
        item_flat = int(item.get("f106") or 0)
        up += item_up
        down += item_down
        flat += item_flat
        name = str(item.get("f14") or item.get("f12") or "")
        if name:
            parts.append({"name": name, "up": item_up, "down": item_down, "flat": item_flat})
    if up <= 0 and down <= 0 and flat <= 0:
        raise ValueError("empty breadth")
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "total": up + down + flat,
        "parts": parts,
        "source": "东方财富",
        "stale": False,
        "note": "沪深两市合计（上证指数与深证成指成分统计口径）。",
    }


def _sina_get(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://vip.stock.finance.sina.com.cn/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _sina_page(page: int, num: int, timeout: float) -> list[float]:
    raw = _sina_get(SINA_PAGE_URL.format(page=page, num=num), timeout)
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(payload, list):
        return []
    changes = []
    for item in payload:
        try:
            changes.append(float(item.get("changepercent")))
        except (TypeError, ValueError):
            continue
    return changes


def fetch_sina_breadth(timeout: float = 8.0, num: int = 80) -> dict:
    """Whole hs_a advance/decline via sorted change% binary search."""
    total = int(json.loads(_sina_get(SINA_COUNT_URL, timeout).decode("utf-8", errors="replace")))
    if total <= 0:
        raise ValueError("empty sina market")
    pages = max(1, (total + num - 1) // num)
    lo, hi = 1, pages
    first_non_up = pages + 1
    while lo <= hi:
        mid = (lo + hi) // 2
        changes = _sina_page(mid, num, timeout)
        if not changes:
            raise ValueError("empty sina page")
        if all(value > 0 for value in changes):
            lo = mid + 1
        else:
            first_non_up = mid
            hi = mid - 1
    if first_non_up > pages:
        return {
            "up": total,
            "down": 0,
            "flat": 0,
            "total": total,
            "parts": [],
            "source": "新浪行情中心",
            "stale": False,
            "note": "沪深 A 股全市场（按涨跌幅排序统计）。",
        }
    changes = _sina_page(first_non_up, num, timeout)
    idx = next((index for index, value in enumerate(changes) if value <= 0), len(changes))
    up = (first_non_up - 1) * num + idx
    flat = 0
    page = first_non_up
    start = idx
    while page <= pages:
        rows = changes if page == first_non_up else _sina_page(page, num, timeout)
        for value in rows[start:]:
            if value < 0:
                down = total - up - flat
                return {
                    "up": up,
                    "down": down,
                    "flat": flat,
                    "total": total,
                    "parts": [],
                    "source": "新浪行情中心",
                    "stale": False,
                    "note": "沪深 A 股全市场（按涨跌幅排序统计）。",
                }
            if value == 0:
                flat += 1
        page += 1
        start = 0
    down = total - up - flat
    return {
        "up": up,
        "down": max(down, 0),
        "flat": flat,
        "total": total,
        "parts": [],
        "source": "新浪行情中心",
        "stale": False,
        "note": "沪深 A 股全市场（按涨跌幅排序统计）。",
    }


def fetch_eastmoney_breadth(timeout: float = 6.0) -> dict:
    last_error: Exception | None = None
    for host in BREADTH_HOSTS:
        try:
            request = urllib.request.Request(
                host + BREADTH_PATH,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return parse_breadth_payload(payload)
        except Exception as exc:  # noqa: BLE001 - try next host
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    raise RuntimeError("breadth unavailable")


def fetch_breadth(timeout: float = 6.0) -> dict:
    try:
        return fetch_eastmoney_breadth(timeout=timeout)
    except Exception:
        logger.warning("东方财富涨跌家数失败，改用新浪全市场统计", exc_info=True)
        return fetch_sina_breadth(timeout=max(timeout, 8.0))


def empty_breadth(*, stale: bool = True, note: str = "") -> dict:
    return {
        "up": 0,
        "down": 0,
        "flat": 0,
        "total": 0,
        "parts": [],
        "source": "东方财富",
        "stale": stale,
        "note": note or "涨跌家数暂时不可用。",
    }


def breadth_from_rows(rows: list[dict]) -> dict:
    """Fallback counts from an already-fetched quote pool (not whole market)."""
    up = down = flat = 0
    for row in rows:
        if float(row.get("price") or 0) <= 0:
            continue
        change = float(row.get("change_pct") or 0)
        if change > 0:
            up += 1
        elif change < 0:
            down += 1
        else:
            flat += 1
    total = up + down + flat
    if total <= 0:
        raise ValueError("empty pool breadth")
    return {
        "up": up,
        "down": down,
        "flat": flat,
        "total": total,
        "parts": [],
        "source": "样本池估算",
        "stale": False,
        "note": f"全市场涨跌家数暂不可用，改用当前选股池 {total} 只估算，不是沪深全市场。",
    }
