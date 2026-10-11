from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest import run_backtest
from app.config import DISCLAIMER
from app.db import get_db
from app.insights import (
    agent_report,
    calendar_events,
    financials_for,
    news_feed,
    pool_snapshot,
    rankings,
    screen_rows,
    technical_view,
    vix_quote,
)
from app.market import get_market_board
from app.models import User, WatchlistItem
from app.quotes import get_provider
from app.routes import current_user, known_code
from app.services import build_watch_item, get_or_create_rule, market_name, quote_source_name, session_label
from app.tencent import fetch_bars
from app.universe import BY_CODE

router = APIRouter()


def _pool():
    try:
        return pool_snapshot()
    except Exception:
        return {
            "rows": [],
            "sectors": [],
            "rankings": {"gainers": [], "losers": [], "turnover": []},
            "stale": True,
            "pool_size": 0,
            "note": "股票池暂时不可用。",
            "disclaimer": DISCLAIMER,
        }


@router.get("/api/pool")
def pool():
    return _pool()


@router.get("/api/rankings")
def board_rankings():
    snap = _pool()
    return {
        "rankings": snap["rankings"],
        "sectors": snap["sectors"],
        "stale": snap["stale"],
        "note": snap["note"],
        "disclaimer": DISCLAIMER,
    }


@router.get("/api/screen")
def screen(
    min_change: float | None = None,
    max_change: float | None = None,
    min_volume_ratio: float | None = Query(default=None, ge=0, le=50),
    min_turnover: float | None = Query(default=None, ge=0),
    min_market_cap: float | None = Query(default=None, ge=0),
):
    snap = _pool()
    rows = screen_rows(
        snap["rows"],
        min_change=min_change,
        max_change=max_change,
        min_volume_ratio=min_volume_ratio,
        min_turnover=min_turnover,
        min_market_cap=min_market_cap,
    )
    return {"rows": rows, "stale": snap["stale"], "pool_size": snap["pool_size"], "note": snap["note"], "disclaimer": DISCLAIMER}


@router.get("/api/stocks/{code}/technical")
def technical(code: str, period: str = "day", minute: int = Query(0, ge=0, le=1)):
    cleaned = known_code(code)
    if period not in {"day", "week"}:
        raise HTTPException(status_code=400, detail="period 只能是 day 或 week")
    return technical_view(cleaned, period, bool(minute))


@router.get("/api/stocks/{code}/financials")
def financials(code: str):
    cleaned = known_code(code)
    return financials_for(cleaned)


@router.get("/api/backtest")
def backtest(code: str, strategy: str = "momentum"):
    cleaned = known_code(code)
    if strategy not in {"momentum", "mean_reversion"}:
        raise HTTPException(status_code=400, detail="strategy 只能是 momentum 或 mean_reversion")
    try:
        candles = fetch_bars(cleaned, "day", 120)
    except Exception:
        candles = []
    result = run_backtest(candles, strategy)
    meta = BY_CODE.get(cleaned)
    return {"code": cleaned, "name": meta.name if meta else cleaned, **result, "disclaimer": DISCLAIMER}


@router.get("/api/agent")
def agent(code: str, question: str = Query("", max_length=200)):
    cleaned = known_code(code)
    return agent_report(cleaned, question)


@router.get("/api/digest")
def digest(db: Session = Depends(get_db), user: User = Depends(current_user)):
    snap = _pool()
    board = get_market_board().snapshot()
    rule = get_or_create_rule(db, user)
    provider = get_provider()
    watch = []
    rows = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == user.id)).all())
    for item in rows:
        try:
            quote = provider.get(item.code)
        except KeyError:
            continue
        built = build_watch_item(rule, item, quote)
        watch.append(
            {
                "code": built["code"],
                "name": built["name"],
                "price": built["price"],
                "change_pct": built["change_pct"],
                "status_label": built["status_label"],
                "latest_signal": built["latest_signal"],
            }
        )
    db.commit()
    return {
        "session_label": session_label(),
        "indices": board,
        "leaders": rankings(snap["rows"]),
        "watch": watch,
        "stale": snap["stale"],
        "note": "由指数、热门池榜单和自选规则扫描拼成，不是投研研报。",
        "disclaimer": DISCLAIMER,
    }


@router.get("/api/news")
def news(column: str = "headline"):
    if column not in {"headline", "stock"}:
        raise HTTPException(status_code=400, detail="column 只能是 headline 或 stock")
    return news_feed(column)


@router.get("/api/calendar")
def calendar():
    return calendar_events()


@router.get("/api/opportunities")
def opportunities(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rule = get_or_create_rule(db, user)
    provider = get_provider()
    signals = []
    rows = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == user.id)).all())
    for item in rows:
        try:
            quote = provider.get(item.code)
        except KeyError:
            continue
        built = build_watch_item(rule, item, quote)
        signals.append(
            {
                "code": built["code"],
                "name": built["name"],
                "status_label": built["status_label"],
                "latest_signal": built["latest_signal"],
                "change_pct": built["change_pct"],
            }
        )
    db.commit()
    return {
        "vix": vix_quote(),
        "signals": signals,
        "unavailable": [
            {"name": "KOL 观点", "note": "暂未接入。没有公开、稳定、免密钥的数据源。"},
            {"name": "暗池", "note": "暂未接入。这是专有数据，观澜不提供。"},
        ],
        "disclaimer": DISCLAIMER,
    }


@router.get("/api/datacenter")
def datacenter(db: Session = Depends(get_db), user: User = Depends(current_user)):
    snap = _pool()
    board = get_market_board().snapshot()
    provider = get_provider()
    watch = []
    rows = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == user.id)).all())
    for item in rows:
        try:
            quote = provider.get(item.code)
        except KeyError:
            continue
        watch.append(
            {
                "code": item.code,
                "name": quote.name,
                "price": round(quote.price, 2),
                "change_pct": round(quote.day_change_pct, 2),
                "volume_ratio": round(quote.volume_ratio, 2),
                "stale": quote.stale,
            }
        )
    return {
        "quote_source": quote_source_name(),
        "market_name": market_name(),
        "session_label": session_label(),
        "indices": board,
        "index_stale": any(item["stale"] for item in board),
        "pool": snap["rows"],
        "pool_stale": snap["stale"],
        "watchlist": watch,
        "note": "导出使用当前内存里的最近一次成功报价。",
        "disclaimer": DISCLAIMER,
    }
