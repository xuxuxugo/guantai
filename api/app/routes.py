import asyncio
import re

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DISCLAIMER, settings
from app.db import get_db
from app.engine import STATUS_LABEL, board_status
from app.models import AlertEvent, User, WatchlistItem
from app.quotes import get_provider
from app.schemas import (
    AddWatchIn,
    AlertListOut,
    AlertOut,
    MarketOut,
    MetaOut,
    OkOut,
    PatchWatchIn,
    PatchWatchOut,
    RuleIn,
    RuleOut,
    SearchOut,
    ShockIn,
    ShockOut,
    StockOut,
    WatchlistOut,
    WatchWriteOut,
)
from app.services import (
    ShockError,
    build_watch_item,
    demo_user,
    get_or_create_rule,
    market_name,
    quote_source_name,
    rebase_catalog_ref,
    rule_payload,
    run_shock,
    session_label,
    session_open,
    signals_for,
    to_alert_dict,
    trigger_rows,
)
from app.universe import BY_CODE, search_stocks

router = APIRouter()
CODE_RE = re.compile(r"^\d{6}$")
STATUS_ORDER = {"risk": 0, "anomaly": 1, "observe": 2}


def current_user(db: Session = Depends(get_db)) -> User:
    user = demo_user(db)
    if user is None:
        raise HTTPException(status_code=500, detail="演示用户还没有准备好")
    return user


def known_code(code: str) -> str:
    cleaned = code.strip()
    if not CODE_RE.fullmatch(cleaned):
        raise HTTPException(status_code=404, detail="股票代码不对")
    if cleaned in BY_CODE:
        return cleaned
    provider = get_provider()
    ensure = getattr(provider, "ensure", None)
    if callable(ensure):
        try:
            ensure(cleaned)
            provider.get(cleaned)
            return cleaned
        except Exception as exc:
            raise HTTPException(status_code=404, detail="行情里没有这只股票") from exc
    raise HTTPException(status_code=404, detail="演示行情里没有这只股票")


@router.get("/api/meta", response_model=MetaOut)
def meta() -> MetaOut:
    return MetaOut(
        name="观澜",
        disclaimer=DISCLAIMER,
        demo_user="demo",
        scan_interval_seconds=settings.scan_interval_seconds,
        demo_auto_pulse=settings.demo_auto_pulse,
        trading_session_open=session_open(),
        market=market_name(),
        quote_source=quote_source_name(),
        offhours_scan_interval_seconds=settings.offhours_scan_interval_seconds,
        session_label=session_label(),
    )


@router.get("/api/market", response_model=MarketOut)
def market_overview() -> MarketOut:
    from app.market import get_market_board

    board = get_market_board()
    indices = board.snapshot()
    breadth = board.breadth()
    return MarketOut(
        indices=indices,
        breadth={
            "up": int(breadth.get("up") or 0),
            "down": int(breadth.get("down") or 0),
            "flat": int(breadth.get("flat") or 0),
            "total": int(breadth.get("total") or 0),
            "source": str(breadth.get("source") or ""),
            "stale": bool(breadth.get("stale")),
            "note": str(breadth.get("note") or ""),
        },
        quote_source=board.source,
        quote_stale=any(item["stale"] for item in indices),
        session_label=session_label(),
        disclaimer=DISCLAIMER,
    )


@router.get("/api/stocks/search", response_model=SearchOut)
def search(q: str = Query("", max_length=32), limit: int = Query(8, ge=1, le=20)) -> SearchOut:
    hits = [{"code": item.code, "name": item.name} for item in search_stocks(q, limit)]
    if len(hits) < limit:
        keyword = q.strip()
        if keyword:
            try:
                from app.insights import refresh_pool

                seen = {item["code"] for item in hits}
                for row in refresh_pool():
                    if row["code"] in seen:
                        continue
                    if row["code"].startswith(keyword) or keyword in row["name"]:
                        hits.append({"code": row["code"], "name": row["name"]})
                        seen.add(row["code"])
                    if len(hits) >= limit:
                        break
            except Exception:
                pass
    return SearchOut(items=hits[:limit])


@router.get("/api/watchlist", response_model=WatchlistOut)
def list_watchlist(db: Session = Depends(get_db), user: User = Depends(current_user)) -> WatchlistOut:
    rule = get_or_create_rule(db, user)
    rows = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == user.id)).all())
    provider = get_provider()
    items = []
    for row in rows:
        try:
            quote = provider.get(row.code)
        except KeyError:
            continue
        rebase_catalog_ref(row, quote)
        items.append(build_watch_item(rule, row, quote))
    items.sort(key=lambda item: (STATUS_ORDER[item["status"]], item["code"]))
    db.commit()
    return WatchlistOut(
        items=items,
        trading_hours_only=rule.trading_hours_only,
        trading_session_open=session_open(),
        disclaimer=DISCLAIMER,
        quote_source=quote_source_name(),
        quote_stale=any(item["stale"] for item in items),
        session_label=session_label(),
    )


@router.post("/api/watchlist", response_model=WatchWriteOut, status_code=201)
def add_watch(body: AddWatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> WatchWriteOut:
    code = known_code(body.code)
    exists = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.code == code))
    if exists is not None:
        raise HTTPException(status_code=409, detail="这只股票已经在盯盘台里")
    provider = get_provider()
    pin = getattr(provider, "pin", None)
    if callable(pin):
        pin(code)
    quote = provider.get(code)
    name = BY_CODE[code].name if code in BY_CODE else quote.name
    rule = get_or_create_rule(db, user)
    db.add(
        WatchlistItem(
            user_id=user.id,
            code=code,
            name=name,
            ref_price=quote.price,
            stop_loss_pct=rule.default_stop_loss_pct,
        )
    )
    db.commit()
    return WatchWriteOut(code=code, name=name)


@router.patch("/api/watchlist/{code}", response_model=PatchWatchOut)
def patch_watch(
    code: str,
    body: PatchWatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> PatchWatchOut:
    cleaned = known_code(code)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.code == cleaned))
    if item is None:
        raise HTTPException(status_code=404, detail="盯盘台里没有这只股票")
    if body.stop_loss_pct is None and not body.reset_ref:
        raise HTTPException(status_code=400, detail="没有要更新的内容")
    if body.stop_loss_pct is not None:
        item.stop_loss_pct = body.stop_loss_pct
    if body.reset_ref:
        item.ref_price = get_provider().get(cleaned).price
    db.commit()
    return PatchWatchOut(code=item.code, stop_loss_pct=item.stop_loss_pct, ref_price=round(item.ref_price, 2))


@router.delete("/api/watchlist/{code}", response_model=OkOut)
def remove_watch(code: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> OkOut:
    cleaned = known_code(code)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.code == cleaned))
    if item is None:
        raise HTTPException(status_code=404, detail="盯盘台里没有这只股票")
    db.delete(item)
    db.commit()
    return OkOut()


@router.get("/api/rules", response_model=RuleOut)
def get_rules(db: Session = Depends(get_db), user: User = Depends(current_user)) -> RuleOut:
    rule = get_or_create_rule(db, user)
    db.commit()
    return RuleOut(**rule_payload(rule))


@router.put("/api/rules", response_model=RuleOut)
def put_rules(body: RuleIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> RuleOut:
    from datetime import datetime, timezone

    rule = get_or_create_rule(db, user)
    for field in (
        "breakout_20d_enabled",
        "swing_enabled",
        "swing_window_minutes",
        "swing_threshold_pct",
        "stop_loss_enabled",
        "default_stop_loss_pct",
        "volume_spike_enabled",
        "volume_ratio_threshold",
        "trading_hours_only",
    ):
        setattr(rule, field, getattr(body, field))
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    return RuleOut(**rule_payload(rule))


@router.get("/api/alerts", response_model=AlertListOut)
def list_alerts(
    level: str | None = None,
    limit: int = Query(80, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> AlertListOut:
    stmt = select(AlertEvent).where(AlertEvent.user_id == user.id)
    if level:
        if level not in STATUS_LABEL:
            raise HTTPException(status_code=400, detail="level 只能是 observe、anomaly 或 risk")
        stmt = stmt.where(AlertEvent.level == level)
    rows = db.scalars(stmt.order_by(AlertEvent.created_at.desc(), AlertEvent.id.desc()).limit(limit)).all()
    return AlertListOut(events=[AlertOut(**to_alert_dict(row)) for row in rows], disclaimer=DISCLAIMER)


@router.get("/api/alerts/stream")
async def alert_stream():
    async def events():
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe("guanlan:alerts")
        queue: asyncio.Queue = asyncio.Queue()

        async def reader() -> None:
            try:
                async for message in pubsub.listen():
                    await queue.put(message)
            except Exception:
                await queue.put(None)

        task = asyncio.create_task(reader())
        try:
            yield 'event: hello\ndata: {"ok": true}\n\n'
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                    continue
                if message is None:
                    break
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, str):
                    yield f"event: alert\ndata: {data}\n\n"
        finally:
            task.cancel()
            try:
                await pubsub.unsubscribe("guanlan:alerts")
                await pubsub.aclose()
            except Exception:
                pass
            await client.aclose()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/stocks/{code}", response_model=StockOut)
def stock_detail(code: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> StockOut:
    cleaned = known_code(code)
    provider = get_provider()
    quote = provider.get(cleaned)
    if quote.high_20d <= 0 and hasattr(provider, "ensure_kline"):
        provider.ensure_kline(cleaned)
        quote = provider.get(cleaned)
    rule = get_or_create_rule(db, user)
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.code == cleaned))
    if item is not None:
        rebase_catalog_ref(item, quote)
    signals = signals_for(rule, item, quote)
    status = board_status(signals)
    db.commit()
    return StockOut(
        code=quote.code,
        name=quote.name,
        price=round(quote.price, 2),
        prev_close=round(quote.prev_close, 2),
        open=round(quote.open, 2),
        high=round(quote.day_high, 2),
        low=round(quote.day_low, 2),
        change_pct=round(quote.day_change_pct, 2),
        volume_ratio=round(quote.volume_ratio, 2),
        high_20d=round(quote.high_20d, 2),
        in_watchlist=item is not None,
        stop_loss_pct=None if item is None else item.stop_loss_pct,
        ref_price=None if item is None else round(item.ref_price, 2),
        status=status,
        status_label=STATUS_LABEL[status],
        triggers=[
            {
                "rule_key": row.rule_key,
                "title": row.title,
                "enabled": row.enabled,
                "hit": row.hit,
                "level": row.level,
                "detail": row.detail,
            }
            for row in trigger_rows(rule, item, quote)
        ],
        candles=[
            {"date": candle.date, "open": candle.open, "high": candle.high, "low": candle.low, "close": candle.close}
            for candle in quote.candles
        ],
        disclaimer=DISCLAIMER,
        stale=quote.stale,
        quote_source=quote.source,
        session_label=session_label(),
    )


@router.post("/api/demo/shock", response_model=ShockOut)
def shock(body: ShockIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> ShockOut:
    try:
        quote, events, note = run_shock(db, user, body.code.strip(), body.kind)
    except ShockError as exc:
        message = str(exc)
        status = 404 if "没有这只股票" in message else 400
        raise HTTPException(status_code=status, detail=message) from exc
    return ShockOut(
        code=quote.code,
        name=quote.name,
        price=round(quote.price, 2),
        change_pct=round(quote.day_change_pct, 2),
        alerts=[AlertOut(**to_alert_dict(event)) for event in events],
        note=note,
        disclaimer=DISCLAIMER,
    )
