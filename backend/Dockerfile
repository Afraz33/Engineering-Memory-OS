FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONPATH=/app/src

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install dependencies first (better layer caching)
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

# Copy application
COPY . .

# ---------------- Development ----------------

FROM base AS dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------- Production ----------------

FROM base AS prod

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
