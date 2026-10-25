"""Request tracing middleware.

Assigns a trace id to every request (honouring an inbound ``X-Request-ID`` if present),
makes it available to the logging layer, logs the request outcome with its duration, and
echoes the id back on the response so clients can quote it in support requests.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import get_logger, trace_id_var

logger = get_logger("app.request")

_HEADER = "X-Request-ID"
# Accept a client-supplied id only if it's a bounded, safe token — otherwise generate one.
# This prevents log injection (newlines in the header) and unbounded ids in structured logs.
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _trace_id_from(request: Request) -> str:
    inbound = request.headers.get(_HEADER)
    if inbound and _SAFE_ID.match(inbound):
        return inbound
    return uuid.uuid4().hex


class RequestTraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        trace_id = _trace_id_from(request)
        token = trace_id_var.set(trace_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            trace_id_var.reset(token)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[_HEADER] = trace_id
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
