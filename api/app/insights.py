"""Cached public-data panels: pool quotes, financials, news, calendar, VIX, agent."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from app.config import DISCLAIMER, settings
from app.indicators import boll, composite_rating, kdj, macd, rsi
from app.sectors import fill_sectors, sector_for
from app.sina_board import fetch_sina_hs_a
from app.tencent import fetch_bars, fetch_board, fetch_minute
from app.universe import BY_CODE, STOCKS

logger = logging.getLogger("guanlan.insights")

NEWS_COLUMNS = {
    "headline": {"label": "要闻", "pageid": "153", "lid": "2516"},
    "stock": {"label": "股市", "pageid": "155", "lid": "1686"},
}
FINANCE_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={em}"
NEWS_URL = "https://feed.mix.sina.com.cn/api/roll/get?pageid={pageid}&lid={lid}&num=15&page=1"
VIX_URL = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
MACRO_URL = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName={report}&columns=ALL&pageNumber=1&pageSize=1&sortTypes=-1"
    "&sortColumns=REPORT_DATE&source=WEB&client=WEB"
)

_lock = threading.Lock()
_pool_rows: list[dict] = []
_pool_at = 0.0
_pool_stale = True
_pool_note = "热门池不是全市场，只覆盖清单里的行业样本。"
_finance: dict[str, tuple[float, dict]] = {}
_news: dict[str, tuple[float, dict]] = {}
_vix: tuple[float, dict] | None = None
_calendar: tuple[float, dict] | None = None


def _get(url: str, timeout: float, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers=headers
        or {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _pool_ttl() -> float:
    from app.services import session_open

    if settings.quote_source.strip().lower() == "mock" or session_open():
        return max(3, settings.scan_interval_seconds)
    return max(3, settings.offhours_scan_interval_seconds)


def _mock_pool() -> list[dict]:
    rows = []
    for index, meta in enumerate(STOCKS):
        change = round(((index % 7) - 3) * 0.4, 2)
        price = round(meta.base_price * (1 + change / 100), 2)
        rows.append(
            {
                "code": meta.code,
                "name": meta.name,
                "sector": meta.sector,
                "price": price,
                "prev_close": meta.base_price,
                "change_pct": change,
                "volume_ratio": round(0.8 + (index % 5) * 0.3, 2),
                "turnover": float(1_000_000_000 + index * 100_000_000),
                "market_cap": round(meta.base_price * 10, 2),
                "stale": False,
            }
        )
    return rows


def _tencent_pool() -> list[dict]:
    spots = fetch_board([item.code for item in STOCKS])
    rows = []
    for meta in STOCKS:
        spot = spots.get(meta.code)
        if spot is None:
            rows.append(
                {
                    "code": meta.code,
                    "name": meta.name,
                    "sector": meta.sector,
                    "price": 0.0,
                    "prev_close": 0.0,
                    "change_pct": 0.0,
                    "volume_ratio": 0.0,
                    "turnover": 0.0,
                    "market_cap": 0.0,
                    "stale": True,
                }
            )
            continue
        rows.append(
            {
                "code": meta.code,
                "name": spot.name or meta.name,
                "sector": meta.sector,
                "price": spot.price,
                "prev_close": spot.prev_close,
                "change_pct": spot.change_pct,
                "volume_ratio": spot.volume_ratio,
                "turnover": spot.turnover,
                "market_cap": spot.market_cap,
                "stale": False,
            }
        )
    return rows


_sector_warm_busy = False


def _sina_pool() -> list[dict]:
    board = fetch_sina_hs_a(pages=2, num=50)
    if not board:
        raise ValueError("empty sina board")
    codes = [row["code"] for row in board]
    ratios: dict[str, float] = {}
    try:
        spots = fetch_board(codes)
        ratios = {code: spot.volume_ratio for code, spot in spots.items()}
    except Exception:
        logger.warning("量比补全失败，选股量比筛选可能偏弱", exc_info=True)
    known = {code: meta.sector for code, meta in BY_CODE.items()}
    rows = []
    for item in board:
        rows.append(
            {
                "code": item["code"],
                "name": item["name"],
                "sector": known.get(item["code"], ""),
                "price": item["price"],
                "prev_close": item["prev_close"],
                "change_pct": item["change_pct"],
                "volume_ratio": round(ratios.get(item["code"], item["volume_ratio"]), 2),
                "turnover": item["turnover"],
                "market_cap": item["market_cap"],
                "stale": False,
            }
        )
    # Cache-only on the request path. Network industry lookups run in the background.
    return fill_sectors(rows, known=known, budget=0)


def _warm_pool_sectors(codes: list[str]) -> None:
    global _sector_warm_busy, _pool_rows
    try:
        for code in codes:
            if code in BY_CODE:
                continue
            try:
                sector_for(code, fallback="")
            except Exception:
                continue
        with _lock:
            if not _pool_rows:
                return
            known = {code: meta.sector for code, meta in BY_CODE.items()}
            _pool_rows = fill_sectors(list(_pool_rows), known=known, budget=0)
    finally:
        _sector_warm_busy = False


def _schedule_sector_warm(codes: list[str]) -> None:
    global _sector_warm_busy
    if _sector_warm_busy or not codes:
        return
    _sector_warm_busy = True
    threading.Thread(target=_warm_pool_sectors, args=(list(codes),), daemon=True).start()


def refresh_pool(force: bool = False) -> list[dict]:
    global _pool_rows, _pool_at, _pool_stale, _pool_note
    now = time.monotonic()
    with _lock:
        if _pool_rows and not force and now - _pool_at < _pool_ttl():
            return list(_pool_rows)
    if settings.quote_source.strip().lower() == "mock":
        rows = _mock_pool()
        with _lock:
            _pool_rows = rows
            _pool_at = now
            _pool_stale = False
            _pool_note = "模拟热门池，覆盖清单样本。"
        return list(rows)
    rows: list[dict] = []
    note = ""
    try:
        rows = _sina_pool()
        note = f"按成交额取沪深 A 股约 {len(rows)} 只（新浪行情），不是全市场。量比尽量用腾讯补全，行业后台补全。"
    except Exception:
        logger.warning("新浪股票池拉取失败，回退腾讯样本池", exc_info=True)
        try:
            rows = _tencent_pool()
            note = "新浪榜暂不可用，已回退到腾讯样本池（约 30 只），不是全市场。"
        except Exception:
            logger.warning("腾讯样本池也失败，保留上次结果", exc_info=True)
            with _lock:
                _pool_stale = True
                _pool_at = now
                if _pool_note:
                    _pool_note = _pool_note
                return list(_pool_rows)
    with _lock:
        _pool_rows = rows
        _pool_at = time.monotonic()
        _pool_stale = any(row["stale"] for row in rows) or not rows
        _pool_note = note
    _schedule_sector_warm([row["code"] for row in rows])
    return list(rows)


def pool_snapshot() -> dict:
    rows = refresh_pool()
    priced = [row for row in rows if row["price"] > 0]
    sectors: dict[str, list[float]] = {}
    for row in priced:
        sectors.setdefault(row["sector"], []).append(row["change_pct"])
    sector_rows = [
        {
            "sector": name,
            "change_pct": round(sum(values) / len(values), 2),
            "count": len(values),
        }
        for name, values in sectors.items()
    ]
    sector_rows.sort(key=lambda item: item["change_pct"], reverse=True)
    return {
        "rows": rows,
        "sectors": sector_rows,
        "rankings": rankings(rows),
        "stale": _pool_stale or not priced,
        "pool_size": len(rows),
        "note": _pool_note,
        "disclaimer": DISCLAIMER,
    }


def rankings(rows: list[dict]) -> dict:
    priced = [row for row in rows if row["price"] > 0]
    return {
        "gainers": sorted(priced, key=lambda item: item["change_pct"], reverse=True)[:8],
        "losers": sorted(priced, key=lambda item: item["change_pct"])[:8],
        "turnover": sorted(priced, key=lambda item: item["turnover"], reverse=True)[:8],
    }


def screen_rows(
    rows: list[dict],
    *,
    min_change: float | None = None,
    max_change: float | None = None,
    min_volume_ratio: float | None = None,
    min_turnover: float | None = None,
    min_market_cap: float | None = None,
) -> list[dict]:
    found = []
    for row in rows:
        if row["price"] <= 0:
            continue
        if min_change is not None and row["change_pct"] < min_change:
            continue
        if max_change is not None and row["change_pct"] > max_change:
            continue
        if min_volume_ratio is not None and row["volume_ratio"] < min_volume_ratio:
            continue
        if min_turnover is not None and row["turnover"] < min_turnover:
            continue
        if min_market_cap is not None and row["market_cap"] < min_market_cap:
            continue
        found.append(row)
    return found


def _num(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_financial_payload(payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        revenue = _num(item.get("TOTALOPERATEREVE"))
        profit = _num(item.get("PARENTNETPROFIT"))
        rows.append(
            {
                "period": item.get("REPORT_DATE_NAME") or str(item.get("REPORT_DATE") or ""),
                "revenue": revenue,
                "profit": profit,
                "revenue_yoy": _num(item.get("TOTALOPERATEREVETZ")),
                "profit_yoy": _num(item.get("PARENTNETPROFITTZ")),
                "roe": _num(item.get("ROEJQ")),
                "gross_margin": _num(item.get("XSMLL")),
                "debt_ratio": _num(item.get("ZCFZL")),
                "eps": _num(item.get("EPSJB")),
                "bps": _num(item.get("BPS")),
            }
        )
    return [row for row in rows if row["period"]]


def em_symbol(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"SH{code}"
    if code.startswith(("4", "8")):
        return f"BJ{code}"
    return f"SZ{code}"


def financials_for(code: str) -> dict:
    cached = _finance.get(code)
    now = time.monotonic()
    if cached and now - cached[0] < 6 * 3600:
        return cached[1]
    meta = BY_CODE.get(code)
    name = meta.name if meta else code
    try:
        raw = _get(
            FINANCE_URL.format(em=em_symbol(code)),
            6,
            {"User-Agent": "Mozilla/5.0", "Referer": "https://emweb.securities.eastmoney.com/"},
        )
        payload = json.loads(raw.decode("utf-8-sig"))
        rows = parse_financial_payload(payload)[:6]
        body = {
            "code": code,
            "name": name,
            "rows": rows,
            "stale": False,
            "source": "东方财富主要指标",
            "note": "" if rows else "这份报表是空的。",
            "disclaimer": DISCLAIMER,
        }
    except Exception:
        logger.warning("财务指标拉取失败 %s", code, exc_info=True)
        previous = cached[1] if cached else None
        body = previous or {
            "code": code,
            "name": name,
            "rows": [],
            "stale": True,
            "source": "东方财富主要指标",
            "note": "财务接口暂时不可用。下面没有数字，不是这只股票没有财报。",
            "disclaimer": DISCLAIMER,
        }
        body = {**body, "stale": True}
    _finance[code] = (now, body)
    return body


def parse_sina_roll(payload: dict) -> list[dict]:
    data = ((payload.get("result") or {}).get("data")) or []
    items = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        published = ""
        ctime = item.get("ctime")
        try:
            if ctime:
                published = datetime.fromtimestamp(int(ctime), timezone(timedelta(hours=8))).strftime("%m-%d %H:%M")
        except (TypeError, ValueError, OSError):
            published = ""
        items.append(
            {
                "title": str(item.get("title")),
                "url": str(item.get("url") or ""),
                "summary": str(item.get("intro") or item.get("summary") or "").strip(),
                "source": str(item.get("media_name") or "新浪财经"),
                "published_at": published,
            }
        )
    return items


def news_feed(column: str) -> dict:
    spec = NEWS_COLUMNS.get(column) or NEWS_COLUMNS["headline"]
    column = column if column in NEWS_COLUMNS else "headline"
    cached = _news.get(column)
    now = time.monotonic()
    if cached and now - cached[0] < 60:
        return cached[1]
    try:
        raw = _get(NEWS_URL.format(pageid=spec["pageid"], lid=spec["lid"]), 6)
        items = parse_sina_roll(json.loads(raw.decode("utf-8", errors="replace")))
        body = {
            "column": column,
            "label": spec["label"],
            "columns": [{"id": key, "label": value["label"]} for key, value in NEWS_COLUMNS.items()],
            "items": items,
            "stale": False,
            "source": "新浪财经滚动",
            "note": "" if items else "这一栏暂时没有条目。",
            "disclaimer": DISCLAIMER,
        }
    except Exception:
        logger.warning("新闻拉取失败 %s", column, exc_info=True)
        previous = cached[1] if cached else None
        body = previous or {
            "column": column,
            "label": spec["label"],
            "columns": [{"id": key, "label": value["label"]} for key, value in NEWS_COLUMNS.items()],
            "items": [],
            "stale": True,
            "source": "新浪财经滚动",
            "note": "新闻源暂时没有回应，列表先空着。",
            "disclaimer": DISCLAIMER,
        }
        body = {**body, "stale": True}
    _news[column] = (now, body)
    return body


def _macro_row(report: str, title: str, formatter) -> dict | None:
    raw = _get(
        MACRO_URL.format(report=report),
        6,
        {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"},
    )
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    rows = ((payload.get("result") or {}).get("data")) or []
    if not rows:
        return None
    item = rows[0]
    report_date = str(item.get("REPORT_DATE") or "")[:10]
    period = str(item.get("TIME") or report_date)
    detail = formatter(item)
    return {
        "date": report_date,
        "region": "中国",
        "title": f"{title} · {period} · {detail}",
        "importance": "已发布",
    }


def _sample_upcoming() -> list[dict]:
    return [
        {"date": "2026-10-13", "region": "中国", "title": "9月 CPI / PPI 常规发布窗口", "importance": "示例"},
        {"date": "2026-10-15", "region": "美国", "title": "9月 CPI 常规发布窗口", "importance": "示例"},
        {"date": "2026-10-20", "region": "中国", "title": "10月 LPR 报价", "importance": "示例"},
        {"date": "2026-10-31", "region": "中国", "title": "10月官方制造业 PMI 常规发布窗口", "importance": "示例"},
        {"date": "2026-11-10", "region": "中国", "title": "10月 CPI / PPI 常规发布窗口", "importance": "示例"},
        {"date": "2026-11-15", "region": "中国", "title": "10月规模以上工业增加值、社零、固投", "importance": "示例"},
    ]


def calendar_events() -> dict:
    global _calendar
    now = time.monotonic()
    if _calendar and now - _calendar[0] < 3600:
        return _calendar[1]
    published: list[dict] = []
    try:
        for report, title, formatter in (
            ("RPT_ECONOMY_CPI", "CPI", lambda item: f"同比 {item.get('NATIONAL_SAME')}%"),
            ("RPT_ECONOMY_PPI", "PPI", lambda item: f"同比 {item.get('BASE_SAME')}%"),
            ("RPT_ECONOMY_PMI", "制造业 PMI", lambda item: f"读数 {item.get('MAKE_INDEX')}"),
            ("RPT_ECONOMY_GDP", "GDP", lambda item: f"累计同比 {item.get('SUM_SAME')}%"),
        ):
            try:
                row = _macro_row(report, title, formatter)
            except Exception:
                logger.warning("宏观数据拉取失败 %s", report, exc_info=True)
                row = None
            if row:
                published.append(row)
    except Exception:
        logger.warning("财经日历宏观块失败", exc_info=True)
    upcoming = _sample_upcoming()
    if published:
        body = {
            "source": "东方财富宏观数据 + 示例窗口",
            "stale": False,
            "note": "上方为已发布宏观数据（公开源）。下方「示例」是常规发布窗口，不是统计局实时日历。",
            "events": published + upcoming,
            "disclaimer": DISCLAIMER,
        }
    else:
        previous = _calendar[1] if _calendar else None
        body = previous or {
            "source": "示例日程",
            "stale": True,
            "note": "宏观数据接口暂时不可用。下面是常规发布窗口的示例，不是交易所或统计局的实时日历。",
            "events": upcoming,
            "disclaimer": DISCLAIMER,
        }
        body = {**body, "stale": True}
    _calendar = (now, body)
    return body


def parse_vix(payload: dict) -> dict:
    result = ((payload.get("chart") or {}).get("result") or [None])[0] or {}
    meta = result.get("meta") or {}
    price = _num(meta.get("regularMarketPrice")) or 0.0
    prev = _num(meta.get("chartPreviousClose")) or _num(meta.get("previousClose")) or 0.0
    change = 0.0 if prev <= 0 else (price - prev) / prev * 100
    return {"symbol": "^VIX", "name": "CBOE VIX", "price": round(price, 2), "prev_close": round(prev, 2), "change_pct": round(change, 2)}


def vix_quote() -> dict:
    global _vix
    now = time.monotonic()
    if _vix and now - _vix[0] < 300:
        return _vix[1]
    try:
        raw = _get(VIX_URL, 6, {"User-Agent": "Mozilla/5.0"})
        parsed = parse_vix(json.loads(raw.decode("utf-8")))
        body = {**parsed, "stale": parsed["price"] <= 0, "source": "Yahoo Finance", "note": ""}
    except Exception:
        logger.warning("VIX 拉取失败", exc_info=True)
        previous = _vix[1] if _vix else None
        body = previous or {
            "symbol": "^VIX",
            "name": "CBOE VIX",
            "price": 0.0,
            "prev_close": 0.0,
            "change_pct": 0.0,
            "stale": True,
            "source": "Yahoo Finance",
            "note": "VIX 暂时拉不到。",
        }
        body = {**body, "stale": True, "note": body.get("note") or "VIX 暂时拉不到，显示上次结果。"}
    _vix = (now, body)
    return body


def technical_view(code: str, period: str = "day", with_minute: bool = False) -> dict:
    meta = BY_CODE.get(code)
    name = meta.name if meta else code
    period = period if period in {"day", "week"} else "day"
    note = ""
    try:
        candles = fetch_bars(code, period, 120 if period == "day" else 80)
    except Exception:
        logger.warning("K 线拉取失败 %s %s", code, period, exc_info=True)
        candles = []
        note = "K 线暂时拉不到。"
    closes = [item.close for item in candles]
    highs = [item.high for item in candles]
    lows = [item.low for item in candles]
    macd_rows = macd(closes) if closes else []
    rsi_rows = rsi(closes) if closes else []
    kdj_rows = kdj(highs, lows, closes) if closes else []
    boll_rows = boll(closes) if closes else []
    rating = {"label": "暂无", "score": 0, "reasons": [note or "K 线还没到齐"]}
    if closes and macd_rows and rsi_rows and kdj_rows and boll_rows:
        rating = composite_rating(
            macd_rows[-1]["dif"],
            macd_rows[-1]["dea"],
            rsi_rows[-1],
            kdj_rows[-1]["k"],
            kdj_rows[-1]["d"],
            closes[-1],
            boll_rows[-1]["mid"],
        )
    minute = []
    minute_note = ""
    if with_minute:
        try:
            minute = fetch_minute(code)
        except Exception:
            logger.warning("分时拉取失败 %s", code, exc_info=True)
            minute_note = "分时暂时拉不到。"
    series = []
    for index, candle in enumerate(candles):
        series.append(
            {
                "date": candle.date,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "dif": macd_rows[index]["dif"] if macd_rows else None,
                "dea": macd_rows[index]["dea"] if macd_rows else None,
                "hist": macd_rows[index]["hist"] if macd_rows else None,
                "rsi": rsi_rows[index] if rsi_rows else None,
                "k": kdj_rows[index]["k"] if kdj_rows else None,
                "d": kdj_rows[index]["d"] if kdj_rows else None,
                "j": kdj_rows[index]["j"] if kdj_rows else None,
                "mid": boll_rows[index]["mid"] if boll_rows else None,
                "upper": boll_rows[index]["upper"] if boll_rows else None,
                "lower": boll_rows[index]["lower"] if boll_rows else None,
            }
        )
    latest = series[-1] if series else None
    return {
        "code": code,
        "name": name,
        "period": period,
        "series": series[-100:],
        "latest": latest,
        "rating": rating,
        "minute": minute[-240:],
        "minute_note": minute_note,
        "stale": not series,
        "note": note,
        "disclaimer": DISCLAIMER,
    }


def _demo_report(name: str, code: str, facts: str) -> dict:
    return {
        "demo": True,
        "source": "演示报告",
        "note": "没有配置 OPENAI_API_KEY，这是按行情和指标拼的结构化演示，不是模型生成。",
        "roles": [
            {"role": "基本面观察", "text": f"{name}（{code}）{facts} 财务表若为空，先不要把空表当成业绩变差。"},
            {"role": "技术面观察", "text": f"{facts} 评级只汇总 MACD、RSI、KDJ 和布林中轨，不预测下一根 K 线。"},
            {"role": "风控", "text": "观澜不下单。仓位、止损和消息面要自己看。仅供研究参考，不构成投资建议。"},
        ],
    }


def agent_report(code: str, question: str = "") -> dict:
    meta = BY_CODE.get(code)
    name = meta.name if meta else code
    tech = technical_view(code, "day", False)
    if tech.get("name") and tech["name"] != code:
        name = tech["name"]
    rating = tech["rating"]["label"]
    latest = tech["latest"] or {}
    price = latest.get("close")
    facts = f"最新收盘 {price if price else '未知'}，技术评级 {rating}。"
    if question.strip():
        facts += f" 用户补充：{question.strip()[:200]}"
    key = settings.openai_api_key.strip()
    if not key:
        body = _demo_report(name, code, facts)
    else:
        prompt = (
            "请用 JSON 输出三个角色的简短研究笔记，键为 roles，每项含 role 与 text。"
            "角色分别是基本面观察、技术面观察、风控。不要给买卖指令。"
            f"标的 {name} {code}。{facts}"
        )
        try:
            url = settings.openai_base_url.rstrip("/") + "/chat/completions"
            payload = json.dumps(
                {
                    "model": settings.openai_model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": "只输出 JSON。仅供研究，不构成投资建议。"},
                        {"role": "user", "content": prompt},
                    ],
                }
            ).encode()
            request = urllib.request.Request(
                url,
                data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = json.loads(response.read().decode())
            content = raw["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[: content.rfind("```")]
            parsed = json.loads(content)
            roles = parsed.get("roles") if isinstance(parsed, dict) else None
            if not isinstance(roles, list) or not roles:
                raise ValueError("empty roles")
            body = {"demo": False, "source": settings.openai_model, "note": "模型输出仅供研究参考，不构成投资建议。", "roles": roles}
        except Exception:
            logger.warning("AI 报告调用失败，回退演示稿 %s", code, exc_info=True)
            body = _demo_report(name, code, facts)
            body["note"] = "模型调用失败，已回退为结构化演示报告。"
    return {"code": code, "name": name, **body, "disclaimer": DISCLAIMER}
