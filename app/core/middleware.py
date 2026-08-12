import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.context import set_correlation_id

CORRELATION_HEADER = "X-Correlation-Id"

logger = logging.getLogger(__name__)

# Kubernetes probes these several times a minute and they say nothing about the
# platform; logging them buries the requests that matter.
_QUIET_PATHS = frozenset({"/livez", "/readyz", "/healthz", "/metrics"})


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        set_correlation_id(correlation_id)

        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        response.headers[CORRELATION_HEADER] = correlation_id

        # One access line per request, emitted here rather than by uvicorn.
        # uvicorn's own access log is plain text and is written by the protocol
        # layer after the ASGI app has returned — outside the scope of the
        # correlation id — so it could never carry one. This service was the only
        # one on the platform whose requests appeared in the log stream as
        # unstructured lines with nothing to trace them by.
        #
        # The path is logged, the query string is not: a query can carry an email
        # or a reset token, and an access log is the least protected place here.
        if request.url.path not in _QUIET_PATHS:
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 2),
                },
            )
        return response
