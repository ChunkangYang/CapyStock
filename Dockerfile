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

RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
