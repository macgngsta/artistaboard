# Build context is the repository root.
#   docker build -t artistaboard .
FROM python:3.13-slim AS base

# ---------- build stage ----------
FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

RUN uv sync --frozen --no-dev

# ---------- runtime stage ----------
FROM base AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
COPY scenes/ scenes/
COPY fonts/ fonts/
COPY data/ data/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Run as a non-root user. /data is the mount point for the SQLite state volume,
# pre-created and owned so a named volume inherits writable ownership.
RUN useradd --system --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown -R app:app /app /data
USER app

# Shallow liveness check: the daemon exposes no port, so confirm the app imports
# and its settings load (catches broken images / missing deps), not deep readiness.
HEALTHCHECK --interval=1m --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import artistaboard; from artistaboard.config import get_settings; get_settings()"]

CMD ["python", "-m", "artistaboard", "run"]
