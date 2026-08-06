# Engineering Memory OS - Setup Guide

## Overview

This backend provides an AI-powered memory system with:
- **Multiple LLM provider support** (Ollama local, OpenAI, Gemini - extensible)
- **Session-based memory** (conversation history per user/session)
- **Working memory** (in-RAM, later backed by Redis/Postgres)
- **Orchestrator** that coordinates providers + memory
- **FastAPI REST API** for chat interactions

## Quick Start with Docker

### 1. Start Ollama + Backend

```bash
# Start both services
docker compose up -d

# Check logs
docker compose logs -f
```

### 2. Pull Models (First Time Only)

```bash
# Run the setup script
./setup_ollama.sh

# Or manually:
docker exec engineering-memory-ollama ollama pull qwen3.5:0.8b
docker exec engineering-memory-ollama ollama pull granite-embedding:30m
```

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/api/health

# Start a conversation
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "message": "Hello! What'\''s your name?"}'

# Continue the conversation (remembers context)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "user-123", "message": "What did I just ask you?"}'

# Get session history
curl http://localhost:8000/api/sessions/user-123/history

# List all active sessions
curl http://localhost:8000/api/sessions
```

## Local Development (No Docker)

###1. Start Ollama Locally

If you have Ollama installed locally:

```bash
# Make sure Ollama is running
ollama serve

# Pull models
ollama pull qwen3.5:0.8b
ollama pull granite-embedding:30m
```

### 2. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or with pip
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run the Server

```bash
# Development mode (hot reload)
uv run uvicorn src.app.main:app --reload --port 8000

# Or directly
python -m uvicorn src.app.main:app --reload --port 8000
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│                    (src/app/main.py)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────▼────────────┐
           │   AI Orchestrator      │  ◄── Single entry point
           │                        │      for AI operations
           └───┬────────────────┬───┘
               │                │
      ┌────────▼─────┐   ┌─────▼──────────┐
      │  Provider    │   │  Memory        │
      │  Registry    │   │  Manager       │
      └──────┬───────┘   └────────────────┘
             │
    ┌────────▼────────────┐
    │  Ollama Provider    │
    │  (qwen3.5:0.8b)     │
    └─────────────────────┘
```

### Key Components

**1. Provider Registry** (`src/ai/providers/registry.py`)
- Manages multiple LLM providers
- Switch providers at runtime
- Add new providers without code changes

**2. Memory Manager** (`src/ai/memory/manager.py`)
- Tracks multiple concurrent sessions
- Each session has isolated history
- Configurable message limits

**3. Working Memory** (`src/ai/memory/working.py`)
- In-memory conversation storage
- System prompt injection
- Automatic message pruning

**4. Orchestrator** (`src/ai/orchestrator.py`)
- Coordinates provider + memory
- Handles chat flow
- Session lifecycle management

## API Endpoints

### Chat

```http
POST /api/chat
Content-Type: application/json

{
  "session_id": "unique-session-id",
  "message": "Your message here",
  "temperature": 0.7,  // optional
  "max_tokens": 500    // optional
}
```

### Sessions

```http
# List all sessions
GET /api/sessions

# Create session with custom system prompt
POST /api/sessions
{
  "session_id": "session-123",
  "system_prompt": "You are a helpful assistant."
}

# Get session info
GET /api/sessions/{session_id}

# Get session history
GET /api/sessions/{session_id}/history

# Clear session (keeps alive)
POST /api/sessions/{session_id}/clear

# Delete session
DELETE /api/sessions/{session_id}
```

## Configuration

### Environment Variables

```bash
# Ollama Configuration
OLLAMA_MODEL=qwen3.5:0.8b
OLLAMA_EMBEDDING_MODEL=granite-embedding:30m
OLLAMA_BASE_URL=http://localhost:11434

# CORS
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Docker Compose

The `docker-compose.yml` sets up:
- **Ollama** on port 11434
- **Backend API** on port 8000
- Persistent volume for Ollama models
- Internal network for service communication

## Adding a New Provider

### 1. Create the Provider Class

```python
# src/ai/providers/openai.py
from .base import BaseLLM
from openai import AsyncOpenAI

class OpenAIProvider(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def chat(self, messages, **kwargs):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content
    
    async def close(self):
        await self.client.close()
```

###2. Register It

```python
# src/ai/providers/registry.py
from .openai import OpenAIProvider

def build_default_registry():
    ...
    # Add your provider
    _registry.register(
        "openai",
        OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY"))
    )
```

### 3. Use It

```bash
# Switch active provider
curl -X POST http://localhost:8000/api/provider/set \
  -d '{"provider": "openai"}'

# Or specify per-request
curl -X POST http://localhost:8000/api/chat \
  -d '{"session_id": "test", "message": "Hello", "provider": "openai"}'
```

## Troubleshooting

### Ollama Connection Failed

```bash
# Check if Ollama is running
docker ps | grep ollama
# or
curl http://localhost:11434/api/tags

# Restart Ollama
docker compose restart ollama
```

### Models Not Found

```bash
# List models
docker exec engineering-memory-ollama ollama list

# Pull missing model
docker exec engineering-memory-ollama ollama pull qwen3.5:0.8b
```

### Port Already in Use

```bash
# Change backend port in docker-compose.yml
ports:
  - "8001:8000"  # External:Internal
```

## Next Steps

- [ ] Add persistent storage (PostgreSQL + pgvector)
- [ ] Implement embeddings for semantic retrieval
- [ ] Add RAG (retrieval-augmented generation)
- [ ] Multi-turn tool calling
- [ ] Streaming responses
- [ ] Rate limiting & authentication
- [ ] Prometheus metrics

## License

MIT
