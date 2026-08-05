.PHONY: install install-backend install-frontend backend frontend dev lint build

install: install-backend install-frontend

install-backend:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev: backend frontend

lint:
	cd frontend && npm run lint

build:
	cd frontend && npm run build
