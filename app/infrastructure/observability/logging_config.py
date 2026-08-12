import logging
import sys

from pythonjsonlogger import jsonlogger

from app.config import settings
from app.core.context import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


def configure_logging() -> None:
    """
    All logs are Structured JSON with standard fields (service, level, message,
    correlation_id) so they can be shipped to Loki / any centralized log backend
    without per-service parsing rules (Maintainability NFR).
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level.upper())

    # Quiet noisy third-party loggers a bit
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if not settings.sql_echo else logging.INFO)

    # uvicorn installs its own handlers and does not propagate, so everything
    # above missed it: its lines went out as plain text next to this service's
    # JSON. Clearing the handlers and letting them propagate puts uvicorn's
    # startup and error output through the same formatter.
    #
    # uvicorn.access is silenced outright rather than reformatted. It is written
    # by the protocol layer after the ASGI app has returned, which is outside the
    # scope of the correlation id, so it can never carry one — and
    # CorrelationIdMiddleware now emits an access line that can.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
