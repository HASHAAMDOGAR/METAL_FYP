"""Cross-cutting middleware: request IDs, structured logging, rate limiting (spec §8.4, §8.5).

The rate limiter is an in-process token bucket keyed by client IP — deliberately
simple, no Redis (spec constraint). For multi-worker deployments, enforce heavier
limits at the gateway/reverse-proxy layer.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.time()
        request.state.request_id = request_id
        response = await call_next(request)
        elapsed_ms = round((time.time() - start) * 1000, 1)
        response.headers["x-request-id"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window counter per client IP."""

    def __init__(self, app, limit_per_minute: int):
        super().__init__(app)
        self.limit = limit_per_minute
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    async def dispatch(self, request: Request, call_next):
        # Skip docs/health to avoid noise.
        if request.url.path in ("/healthz", "/readyz", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        cur_window, count = self._windows[client]
        if cur_window != window:
            self._windows[client] = (window, 1)
        else:
            if count >= self.limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": {
                            "code": "rate_limited",
                            "message": "Too many requests; slow down.",
                        }
                    },
                )
            self._windows[client] = (window, count + 1)
        return await call_next(request)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(RequestContextMiddleware)
