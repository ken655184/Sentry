# ── Base ──────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 系統依賴:hiredis 需要 gcc;aiosqlite 不需要額外套件
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Deps ──────────────────────────────────────────────────────────────────
FROM base AS deps

COPY pyproject.toml .
# 用 pip install -e . 讓 app package 可 import
RUN pip install -e ".[dev]" 2>/dev/null || pip install -e .

# ── App ───────────────────────────────────────────────────────────────────
FROM deps AS app

COPY . .

# data 目錄掛出去讓 SQLite 持久化
RUN mkdir -p /app/data

# FastAPI:uvicorn
# Celery worker / beat 由 docker-compose command 覆蓋
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
