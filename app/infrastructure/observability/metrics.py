from prometheus_fastapi_instrumentator import Instrumentator


def configure_metrics(app) -> None:
    """
    Exposes /metrics for Prometheus scraping. Instrumentator auto-tracks the RED
    metrics (Rate, Errors, Duration) for every endpoint, satisfying the SLI/SLO
    table (p95 latency, error rate) defined in the NFR section.
    """
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
