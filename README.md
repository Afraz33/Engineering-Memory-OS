# Engineering-Memory-OS

Base repo: React (Vite + TypeScript) frontend and FastAPI backend.

## Structure

```
backend/   FastAPI app (app/main.py) with /api/health
frontend/  Vite + React + TypeScript app
```

## Setup

Requirements: Node 22+ (use `nvm use 22`), Python 3.10+.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend runs at http://localhost:8000 (docs at http://localhost:8000/docs).

### Frontend

```bash
nvm use 22
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173. The Vite dev server proxies
`/api/*` requests to the backend on port 8000, so the health check at
`/api/health` works without CORS issues in dev.

### Verify

Open http://localhost:5173 — the page should show both frontend and
backend as **up**.

## Makefile shortcuts

```bash
make install        # set up both backend venv and frontend deps
make backend        # run backend (uvicorn, reload, port 8000)
make frontend       # run frontend (Vite dev server)
make lint           # lint frontend
make build          # typecheck + build frontend
```
