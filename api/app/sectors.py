"""Industry labels for A-share codes (Eastmoney F10, cached)."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request

logger = logging.getLogger("guanlan.insights")

_lock = threading.Lock()
_cache: dict[str, str] = {}
_CACHE_TTL = 24 * 3600
_cached_at: dict[str, float] = {}


def em_symbol(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"SH{code}"
    if code.startswith(("4", "8")):
        return f"BJ{code}"
    return f"SZ{code}"


def shorten_industry(name: str) -> str:
    text = (name or "").strip()
    for suffix in ("行业", "板块", "产业"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
    return text or "其他"


def parse_company_survey(payload: dict) -> str:
    node = payload.get("jbzl") if isinstance(payload, dict) else None
    if not isinstance(node, dict):
        return ""
    return shorten_industry(str(node.get("sshy") or node.get("sszjhhy") or ""))


def fetch_industry(code: str, timeout: float = 2.5) -> str:
    url = (
        "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/"
        f"CompanySurveyAjax?code={em_symbol(code)}"
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://emweb.securities.eastmoney.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8-sig", errors="replace").strip()
    if not raw or raw[0] not in "{[":
        raise ValueError("industry payload is not json")
    return parse_company_survey(json.loads(raw))


def sector_for(code: str, fallback: str = "热门") -> str:
    now = time.monotonic()
    with _lock:
        cached = _cache.get(code)
        if cached and now - _cached_at.get(code, 0.0) < _CACHE_TTL:
            return cached
    try:
        industry = fetch_industry(code)
    except Exception:
        logger.warning("行业拉取失败 %s", code, exc_info=True)
        return fallback
    if not industry:
        return fallback
    with _lock:
        _cache[code] = industry
        _cached_at[code] = time.monotonic()
    return industry


def fill_sectors(rows: list[dict], *, known: dict[str, str] | None = None, budget: int = 20) -> list[dict]:
    """Attach sectors. Prefer known map, then cache, then fetch up to budget new codes."""
    known = known or {}
    remaining = budget
    out = []
    for row in rows:
        code = row["code"]
        sector = known.get(code) or ""
        if not sector:
            now = time.monotonic()
            with _lock:
                cached = _cache.get(code)
                if cached and now - _cached_at.get(code, 0.0) < _CACHE_TTL:
                    sector = cached
        if not sector and remaining > 0:
            sector = sector_for(code, fallback="")
            remaining -= 1
        if not sector:
            sector = "热门"
        out.append({**row, "sector": sector})
    return out
