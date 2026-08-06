FROM python:3.12-slim AS base

WORKDIR /app

# src/ is on the path so imports like `from src.ai...` resolve correctly
ENV PYTHONPATH=/app

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

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---------------- Production ----------------

FROM base AS prod

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
