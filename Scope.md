# Engineering Memory OS — Scope & Goals

**Status:** Draft v1 · 2026-08-08
**Owner:** Afraz
**One line:** A shared memory layer for engineering teams and the AI agents they work with.

---

## 1. The problem

Every engineer now works with three or four agents — Claude Code, Codex, Cursor, ChatGPT — and each
one starts cold. We compensate by hand-maintaining `CLAUDE.md`, `.cursorrules`, `AGENTS.md`, Notion
logs, and ADR folders. That has three failure modes:

1. **N copies, N drift rates.** The same architectural fact is written in four files that disagree within a month.
2. **Maintaining the log becomes a second job.** People forget, entries go stale, duplicates accumulate. The discipline required is exactly the discipline nobody has.
3. **The real rationale was never written down anywhere.** It lives in a merged PR thread, a Slack argument from March, and one person's head. When that person leaves, so does the *why*.

Meanwhile the organization already generates this knowledge continuously — in GitHub PRs, Slack
threads, Jira tickets, and design docs. It is captured but not *retrievable*, and it is completely
invisible to the agents doing the work.

The gap is not storage. It is a **shared context layer** that distinguishes stable identity from
project context from a one-off session detail from a durable decision — and serves the right slice
to whoever is asking, human or agent.

## 2. Thesis

Engineering Memory OS connects to the tools a team already uses, automatically extracts durable
engineering knowledge into a **typed, versioned, provenance-tracked memory store**, and exposes it
through **MCP** (so any agent can read and write it), a **VS Code extension**, and a **web app**.
One workspace replaces N markdown files and becomes the source of truth for both people and agents.

The two hard technical bets, and the actual product:

- **Extraction quality** — turning noisy PR threads and Slack arguments into clean, attributable decisions.
- **Retrieval intelligence** — classifying query intent, weighting memory categories accordingly, and never returning a decision that has since been overturned.

Vector search over a document dump is the commodity part. It is not the product.

## 3. Non-goals

Explicitly out of scope, so the edges stay sharp:

- **Not a chat product.** The chat endpoint in `backend/` is a harness for testing retrieval, not the deliverable.
- **Not a replacement for Notion/Confluence.** We do not author or host long-form docs. We index them and extract from them.
- **Not a code index.** Semantic code search is a solved, crowded space. We index the *conversation about* the code, not the code.
- **Not a transcript archive.** We do not save every message. We store derived, typed memories with pointers back to the source.
- **Not an agent.** We are the memory layer other agents call. We do not compete with Claude Code or Cursor.
- **Not an observability/analytics product.** No dashboards about engineering velocity.

## 4. Users and jobs

**Primary (v1): the individual engineer.** Ships with a workspace model from day one so the same
schema scales to a team without a rewrite, but a single developer must get full value alone. If it
requires four teammates to be useful, it never gets adopted.

| Job | Today | With Memory OS |
|---|---|---|
| Give an agent project context | Hand-write and re-sync `CLAUDE.md` per repo | Agent calls MCP, gets scoped context automatically |
| "Why is it built this way?" | Ask around, dig through PRs | One query, answer with citations |
| Resume work after two weeks | Re-read your own diff | Session + decision recall for that project |
| Onboard someone | Pair for a week | Project + convention + decision history on demand |
| Stop repeating a resolved debate | It gets re-litigated | Superseded decisions carry their own history |

**Secondary (phase 2+): the team.** Shared workspace, invites, per-source permissions, org-wide
decision search.

## 5. The memory model

### 5.1 Categories

Six types. Every memory is exactly one. This taxonomy is the backbone — retrieval weighting,
decay rates, and write permissions all key off it.

| Type | What it holds | Lifetime | Example |
|---|---|---|---|
| `identity` | Who a person or team is; role, preferences, working style | Very stable | "Afraz prefers explicit error handling over exceptions" |
| `project` | What a system is; architecture, constraints, goals | Slow-changing | "Billing service is Go, talks to Stripe, owned by payments team" |
| `convention` | How we do things here | Slow-changing | "All migrations reviewed by a DBA before merge" |
| `decision` | A choice made, with rationale and alternatives | Immutable; superseded, never edited | "Moved off MongoDB to CockroachDB for multi-region writes" |
| `reference` | Pointer to an external artifact | Stable | "Prod runbook → \<url\>" |
| `session` | Ephemeral working state | TTL, hours to days | "Currently debugging the retry loop in worker.py" |

`convention` earns its own type because it is precisely what `CLAUDE.md` / `.cursorrules` contain.
Replacing those files is a core promise, and conventions need different retrieval weighting than
project facts — they matter on every write-code query, regardless of topic.

### 5.2 Record shape

```jsonc
{
  "id": "uuid",
  "workspace_id": "uuid",
  "type": "decision",
  "title": "Moved off MongoDB to CockroachDB",       // one-sentence claim
  "body": "...",                                     // rationale, alternatives, tradeoffs
  "scope": "repo:billing-service",                   // workspace | project:x | repo:y | user:z
  "status": "active",                                // active | superseded | reverted | quarantined
  "supersedes": ["uuid"],
  "superseded_by": null,
  "confidence": 0.86,                                // extractor confidence
  "provenance": [
    { "source": "github", "url": "...", "author": "...", "ts": "...", "excerpt": "..." }
  ],
  "valid_from": "2026-03-14T00:00:00Z",
  "valid_until": null,
  "entities": ["mongodb", "cockroachdb", "billing-service"],
  "embedding": [768 floats],
  "acl": "inherited-from-source",
  "created_at": "...", "last_accessed_at": "...", "access_count": 12
}
```

**Provenance is mandatory.** A memory with no source pointer cannot be written. This is what makes
fully-automatic capture survivable: every claim is auditable back to the PR or thread it came from,
and one click removes it.

### 5.3 Supersession

Decisions form a DAG, never an edit history. When a new decision contradicts an old one, the old
record stays intact with `status: superseded` and a `superseded_by` pointer.

```
D1: "Use MongoDB"        (2024-01, superseded_by D2)
      ↓
D2: "Move to Cockroach"  (2026-03, active)
```

Retrieval returns **only chain heads** by default. The full chain surfaces when intent is
`explain-why` or `history` — because "why did we change our minds?" is a genuinely different
question from "what do we do now?", and conflating them is how agents end up confidently citing
decisions that were reversed a year ago.

Detecting supersession is an extraction problem: entity overlap plus contradiction classification
plus recency. Low-confidence supersessions go to `quarantined` rather than silently rewriting history.

## 6. Capture — fully automatic

**Decision: capture is automatic, with no human confirmation gate.** Coverage beats curation; the
Notion-log failure mode is that manual upkeep never happens.

The known risk of ambient capture is "a pile of facts you never agreed to." Four hard requirements
mitigate it, and they are not optional:

1. **Provenance on every record** — no unattributable memories, ever.
2. **Confidence thresholds** — below threshold goes to `quarantined`, retrievable only on explicit request.
3. **One-click forget** — from any surface, including the agent that just cited it, propagating to the extraction cache so it does not get re-derived.
4. **Full audit view** — "what did you learn this week" is a first-class screen in the web app.

### Pipeline

```
Source webhook / poll
  → normalize to a common Event shape
  → filter (is this even candidate-bearing? cheap classifier, drops ~90% of Slack)
  → extract (LLM: type, title, body, entities, confidence)
  → dedupe (embedding similarity vs. existing memories in scope)
  → supersession check (entity overlap + contradiction)
  → embed + persist with provenance
  → index
```

The filter stage matters most for cost. Embedding every Slack message is economically absurd; the
cheap pre-filter is what makes Slack viable at all.

## 7. Retrieval

The differentiated half of the product. A query does **not** go straight to cosine similarity.

```
query
 → 1. intent classification         (implement | debug | design | explain-why | onboard | recall | review)
 → 2. scope resolution              (workspace, repo, branch — from MCP client context)
 → 3. hybrid candidate generation   (vector + lexical + entity match, per category)
 → 4. category weighting            (by intent, table below)
 → 5. supersession collapse         (heads only, unless intent is explain-why/history)
 → 6. temporal decay                (per-type half-life; session decays in hours, identity in years)
 → 7. ACL filter                    (inherited from source permissions)
 → 8. rerank
 → 9. budget-pack                   (fit token budget, always with citations)
```

### Intent → category weights

| Intent | identity | project | convention | decision | reference | session |
|---|---|---|---|---|---|---|
| `implement` | 0.2 | 0.8 | **1.0** | 0.7 | 0.3 | 0.6 |
| `debug` | 0.1 | 0.7 | 0.4 | 0.6 | **1.0** | 0.7 |
| `design` | 0.3 | 0.9 | 0.5 | **1.0** | 0.4 | 0.4 |
| `explain-why` | 0.1 | 0.8 | 0.3 | **1.0** | 0.5 | 0.2 |
| `onboard` | 0.3 | **1.0** | 0.9 | 0.7 | 0.6 | 0.1 |
| `recall` | 0.4 | 0.5 | 0.1 | 0.5 | 0.3 | **1.0** |
| `review` | 0.2 | 0.6 | **1.0** | 0.8 | 0.2 | 0.4 |

Starting values, to be tuned against the eval set (§12). The classifier itself should be a small
cached model — this runs on every query and cannot cost a frontier-model call.

## 8. Surfaces

All three are committed. They share one API; the clients are thin.

**MCP server** — the leverage play. One protocol, and Claude Code, Codex, Cursor, and Claude Desktop
all work. Tools: `memory.search`, `memory.get_context(scope)`, `memory.write`, `memory.forget`,
`memory.decisions(entity)`.

**Web app** — per the mockups in `designs/`: Google sign-in → create workspace → connect tools →
invite. Dashboard, connection management, knowledge search, and the audit/curation view that
automatic capture requires.

**VS Code extension** — inline context for the current file and branch, plus capture-from-editor.
Thin client over the same API.

## 9. Connectors

All four families committed. Build order reflects signal density and integration cost.

| Source | Extracts | Why | Cost |
|---|---|---|---|
| **Local markdown / repo docs** | ADRs, READMEs, existing `CLAUDE.md` / `.cursorrules` | No OAuth, no rate limits. Directly demonstrates the "one agent, not N config files" pitch. Best migration story. | Low |
| **GitHub / GitLab** | PR descriptions, review threads, merge commits, issues | Densest source of real decisions *with rationale*. Natural provenance links. | Medium |
| **Jira / Linear** | Tickets, epics, status changes | Structured and easy. Caveat: records *what*, rarely *why* — so it mostly enriches project/reference, not decisions. | Low–medium |
| **Slack** | Channel threads | Where decisions actually get made and never written down. Highest value, worst noise, hardest extraction, heaviest permissions model. | High |

Notion is in the mockups as a sixth tile; treating it as fast-follow after the four above.

## 10. Architecture and current state

```
Surfaces      MCP server │ Web app │ VS Code ext
                        ↓ (one HTTP API)
API           FastAPI — src/app/api/
                        ↓
Retrieval     intent classify → weight → supersede → rerank → pack     ← NEW
Memory core   typed store, provenance, supersession                    ← NEW
Capture       connectors → filter → extract → dedupe → embed           ← NEW
                        ↓
Storage       CockroachDB + pgvector · embeddings · semantic_memory
Providers     Gemini │ OpenRouter │ Ollama — src/ai/providers/
```

### What already exists

- FastAPI app, worker pool with rate limiting, session CRUD (`src/app/`, `src/workers/`)
- Provider abstraction with three implementations; Gemini verified working end-to-end
- `WorkingMemory` — maps cleanly onto the `session` tier
- `SemanticMemory` — namespace/key/value; the seed of the memory store, but far too thin for the typed model above
- Embeddings table + repository with cosine/dot/L2 search — the vector substrate is real

### Known gaps to close before any of this works

- **Nothing commits to the database.** `ChatService` holds a session and never calls `.commit()`.
- **No migrations.** Alembic is a declared dependency with no `alembic.ini` and no `versions/`.
- **pgvector not installed** — `models/embeddings.py` silently falls back to `LargeBinary`, which makes the embeddings table unusable for search.
- **Tool calling is a stub.** `Orchestrator._extract_tool_calls` returns `[]` unconditionally, so memory writes can never fire.
- **No auth, no tenancy, no workspace table** despite workspaces being central to the design.
- **No ingestion, extraction, intent classification, or supersession** — the entire product surface.

## 11. Milestones

Sequenced because all-at-once is not a plan. Reorder as needed; the dependencies are real but the priorities are a guess.

- **M0 — Foundation** *(done)*: chat endpoint, providers, embeddings substrate.
- **M1 — Memory core**: typed schema + Alembic migrations, provenance, supersession, pgvector, working persistence, read/write API. Local markdown connector. MCP server, read-only. → *A single dev gets real value: one workspace replacing their per-tool markdown files.*
- **M2 — Automatic capture**: GitHub/GitLab connector, extraction pipeline, dedupe, supersession detection, MCP write tools. → *Memory starts filling itself.*
- **M3 — Intelligent retrieval**: intent classifier, category weighting, hybrid search, reranking, eval harness. Web app with Google auth + workspaces + audit view. → *The differentiated product exists and is measurable.*
- **M4 — Breadth**: Slack, Jira/Linear, VS Code extension, team invites and permissions.
- **M5 — Hardening**: multi-tenant isolation, ACL enforcement, cost controls, retention policy.

## 12. Success metrics

Product is unfalsifiable without these. Build the eval harness in M3, not later.

- **Retrieval precision@5** on a hand-labeled set of 100+ real queries — the primary number.
- **Supersession correctness**: % of queries where a superseded decision is *not* returned as current. Target: >99%. This is the trust metric; one bad answer here costs more than ten misses.
- **Extraction precision**: % of auto-captured memories a human judges correct and worth keeping. Below ~80% and automatic capture is net-negative.
- **Forget rate**: % of memories users delete. A rising number means extraction is degrading.
- **Agent adoption**: MCP calls per developer per day. The honest usage signal.
- **Time-to-first-value**: signup → first useful retrieval. Target under 10 minutes.

## 13. Risks

- **Fully-automatic precision is the whole bet.** If extraction is noisy, the store becomes landfill and users stop trusting it. The §6 mitigations are load-bearing, not nice-to-haves.
- **Crowded space.** Unblocked, Pieces, and Glean solve adjacent problems; Cursor and Claude Code ship native memory; mem0 and Zep sell the memory layer directly. Our defensible wedge is the typed model + supersession + intent-weighted retrieval — *not* "RAG over your tools," which is table stakes. Worth a serious competitive teardown before committing to the pitch.
- **ACL leakage is existential.** Slack ingestion means private-channel content in a shared store. One cross-workspace leak ends the product. Permissions must be inherited at ingestion and enforced at retrieval, not bolted on in M5.
- **Cost at scale.** Embedding every event does not pencil out. The cheap pre-filter is a requirement, not an optimization.
- **Slack extraction may simply be hard.** Sarcasm, threads that trail off, decisions reversed in a DM. Budget for it landing worse than GitHub.

## 14. Open questions

1. **Do we store raw source content, or only derived memories with pointers?** Big implications for privacy, storage cost, legal posture, and re-extraction when the pipeline improves. Leaning: derived + pointers, with a short-lived raw cache.
2. **Cloud-only or self-host?** Enterprises with source in GitLab will demand self-host; it roughly doubles ops surface.
3. **Embedding model.** Currently Gemini `text-embedding-004` at 768 dims. Locks the schema — changing it later means a full re-embed.
4. **Pricing** — per-seat, per-workspace, or usage-based on ingestion volume.
5. **Retention.** Do memories expire? Does a departing employee's `identity` memory get deleted?
6. **Conflict resolution.** When two active decisions contradict and neither supersedes the other, what does retrieval return?
