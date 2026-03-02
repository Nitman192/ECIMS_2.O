from __future__ import annotations

from contextvars import ContextVar

REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")
