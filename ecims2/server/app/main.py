from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.db.database import init_db

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def request_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.request_size_limit_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    body = await request.body()
    if len(body) > settings.request_size_limit_bytes:
        raise HTTPException(status_code=413, detail="Payload too large")
    request._body = body
    return await call_next(request)


@app.middleware("http")
async def rate_limit_stub(request: Request, call_next):
    # Phase 1 stub. Replace with per-agent/IP token bucket in Phase 2.
    return await call_next(request)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database initialized and server started")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_prefix)
