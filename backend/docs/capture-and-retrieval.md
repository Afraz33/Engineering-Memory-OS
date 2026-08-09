# Capture and retrieval — implementation note

**Date:** 2026-08-09 · **Branch:** `afraz/retrieval-pipeline`
**Covers:** Scope §5 (memory model), §6 (capture), §7 (retrieval — contract only)

Two endpoints landed this iteration: `POST /api/events` (ingest an event, let an
LLM decide whether it becomes a memory) and `POST /api/retrieve` (a deliberate
placeholder — the request/response shape, none of the retrieval intelligence).

> **Status: written, not run.** Verification was interrupted before the app was
> imported or either endpoint exercised. Nothing below has been observed
> working. Treat the first run as the real test.

---

## 1. What exists now

| File | Role |
|---|---|
| `src/app/memory/models.py` | `Memory` + `Provenance`; six `MemoryType`s, four `MemoryStatus`es |
| `src/app/memory/store.py` | `MemoryStore` ABC + `InMemoryMemoryStore` |
| `src/app/ingest/events.py` | Slack / GitHub / Jira payloads → one normalized `Event` |
| `src/app/ingest/filter.py` | Free pre-filter (no LLM) |
| `src/app/ingest/classifier.py` | The single LLM call |
| `src/app/ingest/pipeline.py` | normalize → filter → classify → persist |
| `src/app/api/events.py` | `POST /api/events` |
| `src/app/api/retrieval.py` | `POST /api/retrieve` |
| `src/app/api/schemas.py` | Wire shapes shared by both routers |

`src/app/main.py` was edited to mount the two new routers. Nothing else was
touched — `README.md`, `.env.example`, and `requirements.txt` are unchanged and
now under-document the service (see §7).

### Storage is in-memory, and that is load-bearing to understand

The repo has no database: no SQLAlchemy, no models, no Alembic, nothing in
`requirements.txt`. So `InMemoryMemoryStore` is a process-local dict — it dies
on restart, caps at 10k records, and evicts oldest-first. It sits behind the
`MemoryStore` ABC so the CockroachDB + pgvector implementation arrives as a
second class rather than a rewrite of every caller.

`Memory` deliberately has **no `embedding` field**. There is no vector
substrate yet, and a field nothing can populate is worse than no field.

---

## 2. Ingestion

### 2.1 Normalization

`source` is a Pydantic discriminated union, so FastAPI validates the correct
payload shape and errors name the offending field instead of dumping all three
schemas.

Slack is modeled properly (`channel`, `ts`, `thread_ts`, `subtype`, `bot_id`,
`permalink`). GitHub and Jira are field-mapping only — they exist so the `Event`
shape has more than one producer and cannot quietly grow Slack-specific fields.

Default scope per source, overridable by a `scope` field on the request:

| Source | Default scope | Why |
|---|---|---|
| Slack | `workspace` | Channels don't map cleanly onto repos or projects, so it is not guessed |
| GitHub | `repo:<repo>` | Direct |
| Jira | `project:<KEY>` | Direct |

### 2.2 Pre-filter — deterministic, free, no LLM

A **cost control, not a quality control** (Scope §6). Hard drops:

- bot messages (`bot_id` present)
- Slack noise subtypes — `channel_join`, `channel_leave`, topic/purpose/name
  changes, `message_deleted`, `file_share`, …
- empty after stripping code blocks, Slack links, and mentions
- whole-message acknowledgements
- a bare URL with no commentary
- **under `CAPTURE_MIN_LENGTH` (40) chars *and* containing no signal term**

A ~40-term signal lexicon (`decided`, `instead of`, `because`, `convention`,
`always`, `never`, `migrate`, `deprecat`, `adr`, `owns`, …) rescues short but
decisive messages. "We're going with Postgres, not Mongo" is exactly what a
pure length cutoff would throw away.

Two deliberate biases:

- **The ack regex is anchored.** `lgtm` dies; `lgtm, but the retry loop still
  double-counts` survives — the second one is a real convention signal.
- **The stage leans toward keeping.** A false keep costs one cheap model call.
  A false drop loses the memory permanently and silently. Tune
  `CAPTURE_MIN_LENGTH` before adding cleverness here.

### 2.3 Classification — one LLM call

Answers in JSON over the plain-text `ChatProvider` interface rather than a
provider-native structured-output mode, so switching `LLM_PROVIDER` does not
touch this file. It decides store/don't-store **and** the category in the same
call.

Store only if the fact stays useful after the conversation ends. The prompt
carries an explicit reject list: questions and speculation, proposals nobody
agreed to, status chatter and standups, transient facts, restatements of what
is already obvious from the code, and anything where a specific self-contained
claim cannot be written.

Field rules the prompt enforces:

- `title` — a standalone claim. No "the team discussed…" framing.
- `body` — only rationale actually present in the source. No invented reasoning.
- `entities` — lowercase, capped at 8.
- `confidence` — 0.0–1.0; ambiguous or one-sided discussion belongs below 0.5.

Parsing strips ``` fences, then falls back to salvaging first-`{` through
last-`}`, because models prepend prose despite instructions. An unknown type,
or `store: true` with an empty title, raises `ClassificationError` rather than
storing junk.

### 2.4 Confidence gate

`CAPTURE_CONFIDENCE_THRESHOLD` (default `0.6`). At or above → `active`. Below →
persisted as `quarantined`.

### 2.5 Provenance

Enforced in `Memory.__post_init__`, which raises without it — there is no code
path that writes an unattributable record (Scope §6.1). Excerpts cap at 500
chars, since Scope §3 rules out being a transcript archive.

### 2.6 Outcomes

Three sequential gates in `ingest()`; the first to trip wins and returns
immediately.

| Outcome | Decided by | Persisted? |
|---|---|---|
| `dropped_prefilter` | `prefilter()` returned `keep=False` — **no LLM call made** | No |
| `dropped_classifier` | Model returned `store: false` | No |
| `quarantined` | `confidence < threshold` | Yes, `status=quarantined` |
| `stored` | `confidence >= threshold` | Yes, `status=active` |

Each carries a `reason` — from the check that fired, or the model's own
rationale. Rejections are `200`: "nothing worth storing" is a normal connector
outcome, not an error.

A `ClassificationError` is **not** an outcome. It propagates uncaught and the
router returns `502`, so the connector retries instead of recording "nothing to
store."

### 2.7 Not implemented from Scope §6

`dedupe` and `supersession detection`. Both need embedding similarity against
existing memories in scope, and there is no vector substrate.

---

## 3. Retrieval

Intentionally inert. The Scope §7 pipeline is M3 work and none of it exists:

```
intent classify → scope resolve → hybrid candidates → category weighting
→ supersession collapse → temporal decay → ACL filter → rerank → pack
```

What actually runs: case-insensitive token overlap across title, body, and
entities. `score` is the fraction of query tokens matched. Sorted by score,
with recency as the stable tiebreak. Filters for `workspace_id`, `scope`,
`types`, and `limit` (1–100). Quarantined records are excluded unless
`include_quarantined: true`.

Every response carries a `pipeline_stages` map marking each stage
`not_implemented` / `passthrough` / `lexical_only`, plus a `note` stating
plainly that no ranking intelligence was applied. That exists so nothing
downstream — MCP, the web app — mistakes this output for supersession-safe.

**The response shape is the deliverable.** MCP `memory.search`, the web app, and
the VS Code extension can all be built against it while the internals are
replaced wholesale.

---

## 4. `stored` vs `quarantined`

Same store, same fields, same mandatory provenance. One field differs, and one
filter reads it:

```python
# api/retrieval.py — the only branch on status in the codebase
statuses = ["active", "quarantined"] if request.include_quarantined else ["active"]
```

So today quarantined means exactly "saved but invisible by default."

The state earns its place because capture has no human confirmation gate. A
shaky extraction otherwise has two bad options: store it as fact, and an agent
eventually cites it confidently; or discard it, and coverage is lost with no
record that anything was there. Quarantine keeps the record and its provenance
but withholds it from queries until a human looks.

---

## 5. API

### `POST /api/events`

```bash
curl localhost:8000/api/events -H 'content-type: application/json' -d '{
  "source": "slack",
  "workspace_id": "ws_1",
  "payload": {
    "channel": "C0123",
    "channel_name": "eng-backend",
    "user_name": "afraz",
    "text": "We are moving off MongoDB to CockroachDB — we need multi-region writes and Mongo cannot do them without a rewrite.",
    "ts": "1730000000.000100",
    "permalink": "https://acme.slack.com/archives/C0123/p1730000000000100"
  }
}'
```

```json
{
  "outcome": "stored",
  "stored": true,
  "reason": "stored as decision",
  "memory": {
    "id": "…",
    "type": "decision",
    "title": "Moved off MongoDB to CockroachDB for multi-region writes",
    "scope": "workspace",
    "status": "active",
    "confidence": 0.86,
    "entities": ["mongodb", "cockroachdb"],
    "provenance": [{ "source": "slack", "author": "afraz", "url": "…", "excerpt": "…" }]
  }
}
```

### `POST /api/retrieve`

```bash
curl localhost:8000/api/retrieve -H 'content-type: application/json' -d '{
  "query": "why did we leave mongodb",
  "workspace_id": "ws_1",
  "limit": 5
}'
```

Returns `{ query, count, results: [{ memory, score }], pipeline_stages, note }`.

---

## 6. Configuration

Three new environment variables, none of which are in `.env.example` yet:

| Variable | Default | Effect |
|---|---|---|
| `CAPTURE_MIN_LENGTH` | `40` | Pre-filter length cutoff for text with no signal term |
| `CAPTURE_CONFIDENCE_THRESHOLD` | `0.6` | Below this, a record is quarantined rather than active |
| `MEMORY_STORE_CAPACITY` | `10000` | In-memory store cap before oldest-first eviction |

---

## 7. Known gaps and open questions

Ordered by how much they would hurt.

1. **Nothing has been run.** No import check, no route listing, no live request.
   A Pylance parse error was reported at `classifier.py:25` (the
   `SYSTEM_PROMPT = """\` line) and is *believed* to be a false positive from
   the backslash continuation inside a triple-quoted string — unconfirmed.
2. **Nothing survives a restart.** In-memory store, per §1.
3. **No promotion path out of quarantine.** No endpoint, no review flow, no way
   to flip `quarantined` → `active`. The write side of the state exists; the
   curation side does not. Currently a one-way door.
4. **The `stored` boolean is misleading.** It is set from
   `result.memory is not None`, so a `quarantined` outcome returns
   `stored: true`. Technically accurate — it *is* in the store — but a caller
   doing `if response.stored` will treat a low-confidence extraction as a
   first-class memory. Rename to `persisted`, or narrow it to
   `outcome == "stored"`. **Decision needed.**
5. **The confidence threshold is not grounded.** `confidence` is self-reported
   by the model and only clamped to 0–1; nothing calibrates it. Models cluster
   on round numbers and skew overconfident, so `0.6` is a guess until the eval
   set in Scope §12 exists.
6. **The signal lexicon is hand-written and English-only.** It is the single
   biggest lever on both cost and recall, and it has never been measured against
   real Slack traffic. Scope §6 targets dropping ~90%; the actual rate here is
   unknown.
7. **No auth, no tenancy.** `workspace_id` is whatever the caller claims. Any
   client can write to or read from any workspace. Fine for a local harness,
   disqualifying for anything else — and Scope §13 calls ACL leakage
   existential.
8. **No dedupe.** Re-posting the same event creates a second identical memory.
   `external_id` is computed on the `Event` and then dropped on the floor rather
   than used for idempotency.
9. **Docs are stale.** `README.md` documents only the chat API; `.env.example`
   omits all three variables in §6.

---

## 8. Next

Roughly in dependency order:

- Run it. Confirm import, routes, and one real Slack event end to end.
- Settle gap #4, then update `README.md` and `.env.example`.
- Use `external_id` for idempotency — cheapest real win, no new dependencies.
- Alembic + schema + a `PostgresMemoryStore` behind the existing ABC.
- pgvector, then embeddings — which unblocks dedupe and supersession, the two
  pipeline stages currently missing.
