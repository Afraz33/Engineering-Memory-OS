# Setup Guide: Docker & Database

## Quick Start (Dev)

```bash
# Start all containers (Backend, Frontend, CockroachDB, Redis)
docker compose -f docker-compose-dev.yaml up --build -d

# Initialize database schema
docker compose -f docker-compose-dev.yaml exec backend uv run python -m db.init_db
```

## Quick Start (Prod)

```bash
docker compose -f docker-compose-prod.yaml up --build -d
```

---

## Service Endpoints & Ports

- **Frontend**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000` (Docs: `http://localhost:8000/docs`)
- **CockroachDB**: Port `26257` (UI: `http://localhost:8080`)
- **Redis**: Port `6379`

---

## Beekeeper Studio Connection

- **Connection Type**: PostgreSQL
- **Host**: `localhost`
- **Port**: `26257`
- **User**: `root`
- **Password**: *(leave blank)*
- **Database**: `engineering_memory`
- **SSL Mode**: `disable`

**Connection String:**
```text
postgresql://root@localhost:26257/engineering_memory?sslmode=disable
```

---

## DB Init / Schema Commands

```bash
# Run inside container
docker compose -f docker-compose-dev.yaml exec backend uv run python -m db.init_db

# Run locally (backend folder)
uv run init-db
```

---

## Local Ollama Setup

To run LLM & Embeddings locally with Ollama (standalone container):

```bash
# 1. Start separate Ollama container
docker run -d --name ollama-local -p 11434:11434 -v ollama-data:/root/.ollama ollama/ollama:latest

# 2. Pull models
docker exec ollama-local ollama pull qwen2.5:0.5b
docker exec ollama-local ollama pull granite-embedding:30m

# 3. Configure backend (.env)
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:0.5b
OLLAMA_EMBEDDING_MODEL=granite-embedding:30m
```
