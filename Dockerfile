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

CMD ["python", "-m", "artistaboard", "run"]
