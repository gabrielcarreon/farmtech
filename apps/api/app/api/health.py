from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.redis import get_redis
from app.sentiment.client import AIClient

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "crop-intelligence-api", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/health/database")
def health_database() -> JSONResponse:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        return JSONResponse({"status": "unavailable", "detail": str(exc)}, status_code=503)


@router.get("/health/redis")
def health_redis() -> JSONResponse:
    try:
        client = get_redis()
        client.ping()
        return JSONResponse({"status": "ok"})
    except RedisError as exc:
        return JSONResponse({"status": "unavailable", "detail": str(exc)}, status_code=503)


@router.get("/health/ai")
def health_ai() -> JSONResponse:
    if AIClient().is_healthy():
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "unavailable"}, status_code=503)


def rate_limit_middleware_factory():
    from app.core.config import get_settings

    settings = get_settings()

    async def middleware(request: Request, call_next):
        if request.url.path.startswith("/api"):
            try:
                client = get_redis()
                host = request.client.host if request.client else "unknown"
                bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
                key = f"rate:{host}:{bucket}"
                count = client.incr(key)
                if count == 1:
                    client.expire(key, 70)
                if count > settings.rate_limit_per_minute:
                    return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
            except RedisError:
                pass
        return await call_next(request)

    return middleware
