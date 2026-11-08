# QuantumFintek API — multi-stage, non-root runtime

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY packages/quant-core /build/packages/quant-core
COPY packages/ai-intel /build/packages/ai-intel
COPY packages/security /build/packages/security
COPY packages/zos-bridge /build/packages/zos-bridge

RUN pip install --no-cache-dir --prefix=/install \
    -e /build/packages/quant-core \
    -e /build/packages/ai-intel \
    -e /build/packages/security \
    -e /build/packages/zos-bridge

COPY apps/api/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r /build/requirements.txt

FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 qf \
    && useradd --system --uid 10001 --gid qf --home /app --shell /usr/sbin/nologin qf

WORKDIR /app

COPY --from=builder /install /usr/local
COPY apps/api/app /app/apps/api/app
COPY apps/api/alembic /app/apps/api/alembic
COPY apps/api/alembic.ini /app/apps/api/alembic.ini

ENV PYTHONPATH=/app/apps/api \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER qf

EXPOSE 8000

# Production default: no reload. Override for local dev if needed.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
