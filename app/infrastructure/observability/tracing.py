import logging

logger = logging.getLogger(__name__)


def configure_tracing(app) -> None:
    """
    Wires OpenTelemetry auto-instrumentation for FastAPI + SQLAlchemy, exporting
    traces via OTLP to the central OTel Collector (see NFR 8.2). No-ops cleanly
    if OTEL_EXPORTER_OTLP_ENDPOINT is not configured, so local dev doesn't require
    a collector to be running.
    """
    from app.config import settings

    if not settings.otel_exporter_otlp_endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set - tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        resource = Resource.create({"service.name": settings.app_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        logger.info("OpenTelemetry tracing enabled -> %s", settings.otel_exporter_otlp_endpoint)
    except Exception:
        logger.exception("Failed to configure OpenTelemetry tracing; continuing without it")
