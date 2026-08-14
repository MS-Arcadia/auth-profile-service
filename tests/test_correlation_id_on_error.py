"""The correlation id survives an unhandled exception.

`register_exception_handlers`'s catch-all `Exception` handler logs "Unhandled exception on
%s %s" — and Starlette pulls any handler registered for `Exception` (or 500) out of the
normal middleware chain into `ServerErrorMiddleware`, which sits *outside every user
middleware*. `CorrelationIdMiddleware` used to be added *before* `configure_metrics()`'s own
`@app.middleware("http")` instrumentation, and Starlette's `add_middleware()` prepends — so
the middleware added *later* ends up *outer*. That put metrics outside correlation.

`BaseHTTPMiddleware` (what both of these are) runs everything inside it in a separate
`anyio` task; on an exception it captures it in a plain variable and re-raises it back in
the *parent* task, not the task where it originated. Since `set_correlation_id()` ran inside
`CorrelationIdMiddleware`'s own task — itself a *child* task spawned by the outer metrics
middleware's `call_next()` — that assignment was invisible once the exception hopped back
out into metrics' own (parent) task, and stayed invisible all the way to
`ServerErrorMiddleware`, where the actual logging happens.

`CorrelationIdFilter` writes `record.correlation_id` at `Handler.filter()` time, which is
synchronous with whatever task is current when the log call happens — so proving this needs
a handler that applies that same filter and inspects the record *then*, not `caplog`'s raw
records after the fact (its own handler never had the filter attached, and even if it did,
`TestClient` runs the ASGI app through a separate portal task, so nothing evaluated from the
test's own context afterwards would reflect what that request actually saw).

Built as a minimal app from the same three pieces `app/main.py` wires together —
`CorrelationIdMiddleware`, `register_exception_handlers`, `configure_metrics` — rather than
the real app, which needs a database before it can start.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import register_exception_handlers
from app.core.middleware import CORRELATION_HEADER, CorrelationIdMiddleware
from app.infrastructure.observability.logging_config import CorrelationIdFilter
from app.infrastructure.observability.metrics import configure_metrics


class _CapturingHandler(logging.Handler):
    """Applies the real `CorrelationIdFilter` at emit time, in whatever task is current —
    exactly what the production handler does — and keeps the resulting records."""

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(CorrelationIdFilter())
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def captured():
    handler = _CapturingHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        root.removeHandler(handler)


def _build_app(*, middleware_last: bool) -> FastAPI:
    """`middleware_last=True` reproduces `app/main.py`'s current (fixed) registration
    order; `False` reproduces the order that shipped the bug, for the negative case."""
    app = FastAPI()

    def add_correlation() -> None:
        app.add_middleware(CorrelationIdMiddleware)

    if not middleware_last:
        add_correlation()

    register_exception_handlers(app)
    configure_metrics(app, service="test-service")

    if middleware_last:
        add_correlation()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("deliberate failure for the test")

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "fine"}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(middleware_last=True), raise_server_exceptions=False)


def test_the_error_log_line_carries_the_same_id(client: TestClient, captured: _CapturingHandler):
    sent = "test-correlation-xyz789"
    client.get("/boom", headers={CORRELATION_HEADER: sent})

    errors = [r for r in captured.records if r.levelno >= logging.ERROR]
    assert errors, "the unhandled-exception handler must log something"
    logged_ids = {getattr(r, "correlation_id", None) for r in errors}
    assert sent in logged_ids, (
        f"none of the error log records carried the request's correlation id "
        f"(saw {logged_ids!r}) — CorrelationIdMiddleware must be the outermost middleware"
    )


def test_a_successful_request_still_gets_its_id_back(client: TestClient):
    sent = "test-correlation-ok"
    response = client.get("/ok", headers={CORRELATION_HEADER: sent})

    assert response.status_code == 200
    assert response.headers[CORRELATION_HEADER] == sent


def test_the_old_registration_order_reproduces_the_bug(captured: _CapturingHandler):
    """Pins the actual failure mode down: with the middleware added *before* metrics
    (the order this shipped with), the id is lost. If this test ever starts failing, the
    bug it documents is a regression risk again even though `client` above still passes."""
    broken_client = TestClient(_build_app(middleware_last=False), raise_server_exceptions=False)

    broken_client.get("/boom", headers={CORRELATION_HEADER: "should-be-lost"})

    errors = [r for r in captured.records if r.levelno >= logging.ERROR]
    assert errors
    logged_ids = {getattr(r, "correlation_id", None) for r in errors}
    assert "should-be-lost" not in logged_ids
