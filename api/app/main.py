import logging
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionLocal, check_db, init_db
from app.extra_routes import router as extra_router
from app.routes import router
from app.seed import seed
from app.services import check_redis, safe_scan

logger = logging.getLogger("guanlan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        safe_scan,
        "interval",
        seconds=max(3, settings.scan_interval_seconds),
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(ZoneInfo("Asia/Shanghai")),
        id="quote-scan",
    )
    scheduler.start()
    logger.info(
        "观澜已启动，行情源 %s，交易时段每 %s 秒，非交易时段每 %s 秒",
        settings.quote_source,
        max(3, settings.scan_interval_seconds),
        max(3, settings.offhours_scan_interval_seconds),
    )

    def _warm_panels() -> None:
        try:
            from app.insights import refresh_pool
            from app.market import get_market_board

            refresh_pool(force=True)
            get_market_board().refresh()
        except Exception:
            logger.warning("启动预热失败", exc_info=True)

    import threading

    threading.Thread(target=_warm_panels, daemon=True).start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="观澜", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)
app.include_router(router)
app.include_router(extra_router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api") or request.url.path == "/health":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, __: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "有些数值超出了可设置范围，请检查阈值、止损和窗口。"},
    )


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("未处理错误")
    return JSONResponse(status_code=500, content={"detail": "服务暂时不可用"})


@app.get("/health")
def health():
    db_ok = check_db()
    redis_ok = check_redis()
    ok = db_ok and redis_ok
    return JSONResponse(status_code=200 if ok else 503, content={"ok": ok, "db": db_ok, "redis": redis_ok})
