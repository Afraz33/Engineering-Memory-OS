.PHONY: install install-backend install-frontend backend frontend dev lint build

install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && pnpm install

backend:
	cd backend && uv run uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && pnpm dev

dev: backend frontend

lint:
	cd frontend && pnpm lint

build:
	cd frontend && pnpm build
