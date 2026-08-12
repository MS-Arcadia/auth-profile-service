"""RED metrics, named the way the rest of the platform names them.

This used to be `prometheus_fastapi_instrumentator`, which works but publishes
under its own names (`http_requests_total`, `http_request_duration_seconds`).
Every other Python service on the platform exports `arcadia_http_requests_total`
with a `service` label, and the shared Grafana dashboards and alert rules select
on exactly that — so this service was instrumented and still invisible on every
cross-service panel.

The labels match the other services deliberately, down to using the route
*template* rather than the concrete path: labelling by path would mint a new
time series per user id and eventually take Prometheus down.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

requests_total = Counter(
    "arcadia_http_requests_total",
    "HTTP requests handled.",
    ["service", "method", "route", "status"],
)
request_duration = Histogram(
    "arcadia_http_request_duration_seconds",
    "How long HTTP requests took.",
    ["service", "method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def configure_metrics(app: FastAPI, *, service: str) -> None:
    """Instrument every request and expose /metrics."""

    @app.middleware("http")
    async def _observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        route = request.scope.get("route")
        route_label = getattr(route, "path", request.url.path)

        requests_total.labels(
            service, request.method, route_label, str(response.status_code)
        ).inc()
        request_duration.labels(service, request.method, route_label).observe(elapsed)
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
