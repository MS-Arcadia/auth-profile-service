FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG VERSION=local
ENV SERVICE_VERSION=$VERSION

COPY app ./app

RUN useradd --create-home appuser
USER appuser

# 8085, following the platform's numbering: wallet 8080 … media 8084.
EXPOSE 8085

# Probes readiness, not liveness. `/livez` deliberately checks nothing, so a container that had
# lost its database would keep reporting healthy — and conflating the two is how a brief database
# blip restarts every replica and turns a short outage into a long one.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8085/readyz > /dev/null || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8085"]
