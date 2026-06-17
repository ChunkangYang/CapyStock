# syntax=docker/dockerfile:1.6
# CapyStock — multi-stage build
# Stage 1: build the SvelteKit/Vite frontend → static dist/
# Stage 2: python runtime serves FastAPI + mounts the static build at /

FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CAPYSTOCK_FRONTEND_DIR=/app/frontend/dist

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tzdata \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Tokyo

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY api/        ./api/
COPY capystock/  ./capystock/

COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# 把 git-tracked 的種子資料放進 image（watchlist / ledgers / universe / 快照等）。
# 56MB 的 data/cloud-cache 已由 .dockerignore 排除 — 開機後由「雲端同步」從 GitHub 拉，
# 避免 image 膨脹。data/cache（gitignored）也不在內，首次同步時建立。
COPY data/ ./data/
RUN mkdir -p /app/data/cache /app/data/cloud-cache

# PaaS（Render/Fly/Railway…）會注入 $PORT；本地未注入時回退 8000。
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT:-8000}/api/v1/health" || exit 1

# shell 形式才能展開 $PORT；--proxy-headers 讓反向代理後的 base_url 帶正確 https scheme
# （Google OAuth redirect_uri 需要 https）。
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
