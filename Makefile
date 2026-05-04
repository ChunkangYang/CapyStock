# CapyStock Makefile
# 在 Windows 上需透過 GNU Make（如 chocolatey: choco install make）

PY ?= python
PIP ?= pip
PORT ?= 8000

.PHONY: help dev test build run docker-build docker-run clean fe-build fe-dev be-test fe-test

help:
	@echo "CapyStock Make targets:"
	@echo "  make dev          - 開發模式：起 backend + frontend dev server"
	@echo "  make test         - 跑全部測試（pytest + frontend unit）"
	@echo "  make build        - 編譯 frontend 到 frontend/dist"
	@echo "  make run          - 起 production：build frontend + uvicorn 服務"
	@echo "  make docker-build - docker build ."
	@echo "  make docker-run   - docker compose up -d"
	@echo "  make clean        - 清除 build 產物"

dev:
	@echo "[capystock] 開發模式：請用兩個 terminal 分別跑"
	@echo "  terminal 1: uvicorn api.main:app --reload --port $(PORT)"
	@echo "  terminal 2: cd frontend && npm run dev"

be-test:
	$(PY) -m pytest tests/ -v

fe-test:
	cd frontend && npm run test:unit -- --run

test: be-test fe-test

fe-build:
	cd frontend && npm install && npm run build

build: fe-build

run: build
	uvicorn api.main:app --host 0.0.0.0 --port $(PORT)

docker-build:
	docker build -t capystock:latest .

docker-run:
	docker compose up -d

clean:
	rm -rf frontend/dist frontend/build
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
