# Engineering Memory OS — backend

FastAPI service.

## Python version

**Python 3.12** (3.12.x — any patch release). This is what `Dockerfile` builds
on, so local and deployed environments match. Pinned in `.python-version` and
`pyproject.toml` (`requires-python = ">=3.12"`).

Avoid 3.13/3.14 for now: some dependencies don't yet ship prebuilt Windows
wheels for them, and pip falls back to compiling from source.

Windows — install from [python.org/downloads](https://www.python.org/downloads/release/python-3128/)
(pick the *Windows installer (64-bit)*) and **tick "Add python.exe to PATH"** on
the first screen. The `python.exe` that ships in `WindowsApps` is a Microsoft
Store placeholder, not an interpreter — if `python --version` prints nothing or
opens the Store, that's the one you're hitting.

Verify before continuing:

```bash
python --version    # Python 3.12.x
```

## Setup (pip)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate         # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env         # cp on macOS/Linux — then fill in GOOGLE_API_KEY
```

Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

## Run

```bash
uvicorn --app-dir src app.main:app --reload --port 8000
```

`--app-dir src` is required: the code lives under `src/` and isn't installed
into the venv, so `app.main` is otherwise not importable. (The Dockerfile does
the same job with `ENV PYTHONPATH=/app/src`.)

Interactive docs at http://localhost:8000/docs.

## Setup (uv, alternative)

```bash
cd backend
uv sync
uv run uvicorn --app-dir src app.main:app --reload --port 8000
```

uv downloads the interpreter itself, so no separate Python install is needed.
`requirements.txt` and `pyproject.toml` list the same dependencies — if you add
one, update both.

## Chat API

`POST /api/chat` — full reply as JSON.

```bash
curl localhost:8000/api/chat -H 'content-type: application/json' -d '{
  "messages": [{"role": "user", "content": "Why did we move off MongoDB?"}],
  "system": "Answer from the retrieved memory context only."
}'
```

```json
{
  "content": "...",
  "model": "gemini-2.5-flash",
  "provider": "gemini",
  "usage": { "input_tokens": 128, "output_tokens": 342 }
}
```

`POST /api/chat/stream` — same body, replies as SSE. Each event is
`data: {"delta": "..."}`, terminated by `data: [DONE]`. A mid-stream failure
arrives as `event: error` with a `{"error": "..."}` payload (the response has
already committed a 200 by then, so it can't be an HTTP status).

Optional request fields: `model`, `max_tokens`, `temperature`.

## Swapping providers

`app/llm/` holds one adapter per provider behind the `ChatProvider` interface
in `base.py`; `LLM_PROVIDER` picks one at startup. Each adapter imports its SDK
lazily, so only the active provider's package needs to be installed.

```bash
pip install anthropic          # or: uv sync --extra anthropic
# .env: LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY=...
```

Nothing outside `app/llm/` knows which provider is in use — the router only
sees `ChatMessage` / `ChatResponse`.

Two provider quirks the adapters absorb:

- Gemini names the assistant role `model`; the adapter translates.
- Claude Opus 5 rejects `temperature`, so the Anthropic adapter drops it rather
  than 400-ing. Steer tone via `system` there.

To add a provider: implement `ChatProvider` in a new module and register it in
`PROVIDERS` in `app/llm/__init__.py`.
