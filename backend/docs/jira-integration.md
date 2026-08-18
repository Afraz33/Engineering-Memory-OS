# Jira integration

How a Jira issue becomes a memory, and what you have to do on Atlassian's side
to make it happen.

Companion to [slack-integration.md](./slack-integration.md) — the pipeline is
the same one; only the connector in front of it differs.

---

## 1. The flow

```
Jira Cloud site
   │  issue created/edited, or a comment posted
   ▼
POST /api/jira/webhook/{secret}   ← the secret in the path IS the auth
   │
   ├─ unknown secret?           → 404, stop
   ├─ issue_updated with no description/summary change? → 200, ignored
   │       (a status drag across a board is not new prose)
   ├─ record in `source_events`  (UNIQUE workspace+external_id)
   │     └─ already there? → 200, this is a Jira retry, stop
   ├─ 200 OK  ─────────────────────────────────► Jira
   │
   └─ background: ADF→text → normalize → prefilter → classify → persist
                                                        │
                          `memories` + `memory_provenance` + `embeddings`
                                                        │
                              update `source_events.outcome` + `memory_id`
```

Plus a pull path that webhooks cannot cover:

```
POST /api/jira/sync   →  JQL `updated >= <last sync>`  →  same pipeline
```

Two tables carry the connector:

| table | why it exists |
|---|---|
| `jira_installations` | maps Atlassian's `cloud_id` → our `workspace_id`, holds the OAuth tokens and the webhook secret |
| `source_events` | every inbound event, recorded *before* the LLM runs — shared with Slack, keyed by `source = 'jira'` |

### Three things that differ from Slack

**1. Tokens expire.** Slack's `xoxb-` token lives until revoked. A Jira 3LO
access token lasts an hour, so every install stores a refresh token and
`_token()` in `app/api/jira.py` refreshes-and-persists before every outbound
call. Atlassian *rotates* the refresh token on use — dropping that write breaks
the install an hour later, which is the worst kind of failure to debug.

**2. Webhooks are not signed.** Slack HMACs the raw body. Atlassian does not
sign deliveries for OAuth apps at all, so a high-entropy per-installation
secret sits in the callback path instead and possession of it is the
authentication. That URL is a bearer credential: anyone holding it can post
events into your workspace. Disconnecting revokes it.

**3. Text arrives as a document.** REST v3 returns descriptions and comments in
Atlassian Document Format — a nested JSON tree, not a string. `adf_to_text` in
`services/jira_client.py` flattens it, because the classifier reads prose and
the pre-filter measures length in characters of prose.

### What gets filtered, and where

Four gates, cheapest first — the point is that most Jira traffic never reaches
an LLM call:

| gate | drops | where |
|---|---|---|
| `jqlFilter` on the webhook | issues outside the query | Atlassian's side, free |
| event type | worklogs, deletions, sprint churn | `webhook()` |
| changelog check | `issue_updated` that touched no description/summary | `_changed_text()` |
| pre-filter | short text, acks, bare links | `ai/ingest/filter.py` |
| classifier | anything not durable | `ai/ingest/classifier.py` |

The changelog check is the one that matters for cost. Jira fires
`jira:issue_updated` for every field touch — assignee, status, sprint, story
points — and none of those change the prose. Without that gate, one drag of a
card across a board is one LLM call.

---

## 2. What you do on Atlassian

### a. Create the app

1. <https://developer.atlassian.com/console/myapps/> → **Create** →
   **OAuth 2.0 integration**.
2. Name it (e.g. *Memory OS*), accept the terms, **Create**.

### b. Add the Jira API and its scopes

**Permissions → Jira API → Add**, then **Configure** → add:

| scope | what it buys |
|---|---|
| `read:jira-work` | read issues, comments, projects |
| `read:jira-user` | resolve reporters and comment authors to names |
| `manage:jira-webhook` | register the webhook without you hand-configuring one |

Then **Authorization → OAuth 2.0 → Configure** and make sure `offline_access`
is included — that is what mints a refresh token. Without it the connection
dies silently after one hour.

Adding a scope later forces every site to reconnect, so add all of them now.

### c. Expose your local backend

Atlassian must reach your server over public HTTPS. `localhost` will not do.

```bash
ngrok http 8000        # → https://a1b2c3.ngrok-free.app
```

Then in `backend/.env`:

```bash
BACKEND_URL=https://a1b2c3.ngrok-free.app
FRONTEND_URL=http://localhost:5173
```

> The free ngrok URL changes every restart. When it does, update `BACKEND_URL`
> **and** the callback URL in the developer console, or OAuth fails and events
> stop arriving. You will also need to reconnect, since the registered webhook
> still points at the dead hostname.

### d. Callback URL

**Authorization → OAuth 2.0 → Configure → Callback URL**:

```
https://a1b2c3.ngrok-free.app/api/jira/callback
```

This must match `BACKEND_URL + /api/jira/callback` byte for byte.

### e. Credentials

**Settings → Authentication details.** Copy into `backend/.env`:

```bash
JIRA_CLIENT_ID=...
JIRA_CLIENT_SECRET=...
```

There is no third value — Jira has no equivalent of Slack's signing secret.

### f. Run the migration

```bash
cd backend
uv run init-db          # idempotent; creates jira_installations
```

Or apply `src/db/migrations/003_add_jira.sql` directly against the cluster.

### g. Connect it

Restart the backend, open the app → **Sources** → **Connect** on the Jira card.
That runs the OAuth flow, resolves your site's cloud id, writes the row in
`jira_installations`, and registers the webhook.

### h. If the webhook card shows a warning

Atlassian only accepts a dynamically registered webhook when the URL sits under
the app's configured base URL. When it refuses, the connection still succeeds
and the Sources card shows the URL to add by hand:

**Jira Settings → System → WebHooks → Create a WebHook**

| field | value |
|---|---|
| URL | the URL shown on the card (contains the secret) |
| Issue | `created`, `updated` |
| Comment | `created`, `updated` |
| JQL | `project is not EMPTY` (or narrow it) |

### i. Try it

Hit **Sync** on the Jira card to backfill the last 90 days, or edit an issue
description to something with a real decision in it — short chatter is dropped
by the pre-filter on purpose:

> We're storing job state in Postgres with SKIP LOCKED rather than Redis,
> because we need ordering guarantees that Redis streams don't give us.

Within a few seconds it should appear under **Recent activity**, marked
`stored`.

---

## 3. Configuration

| variable | default | meaning |
|---|---|---|
| `JIRA_CLIENT_ID` | — | Atlassian app credential |
| `JIRA_CLIENT_SECRET` | — | Atlassian app credential |
| `BACKEND_URL` | `http://localhost:8000` | public URL Jira calls |
| `FRONTEND_URL` | `http://localhost:5173` | where OAuth returns the user |

Everything else (`MEMORY_STORE`, `CAPTURE_CONFIDENCE_THRESHOLD`,
`CAPTURE_MIN_LENGTH`) is shared with Slack and documented there.

Tunables that live in code rather than env, because changing them is a
deliberate act: `SYNC_LIMIT` and `SYNC_LOOKBACK_DAYS` in `app/api/jira.py`
bound what one backfill costs, and `WEBHOOK_EVENTS` in
`services/jira_client.py` is what we subscribe to.

---

## 4. Troubleshooting

| symptom | cause |
|---|---|
| Connect button does nothing, card says credentials missing | `JIRA_CLIENT_ID` / `JIRA_CLIENT_SECRET` unset — restart the backend after editing `.env` |
| Redirected back with `reason=exchange` | callback URL in the console ≠ `BACKEND_URL + /api/jira/callback` |
| Redirected back with `reason=no_site` | that Atlassian account has no Jira site, only Confluence |
| Atlassian's consent screen says *"requires access to a Jira site which you don't have"* | same root cause as `reason=no_site`, caught one step earlier — the signed-in account has no Jira site. An Atlassian account is not a Jira licence, and the account that owns the console app often has no product attached. Check <https://admin.atlassian.com>; confirm the browser is signed into the account that owns the site (incognito is the quick test); confirm your user has Jira product access on it |
| Works for an hour, then everything errors | `offline_access` was not granted — reconnect after adding it |
| Card shows the manual-webhook warning | dynamic registration refused; add the webhook by hand (§2h) |
| Nothing arrives after a status change | expected — status transitions carry no new prose and are dropped before recording |
| Events arrive, nothing stored | expected — check `outcome` in **Recent activity**; most tickets are meant to be dropped |
| Everything `dropped_prefilter` | descriptions are too short; lower `CAPTURE_MIN_LENGTH` |
| Everything `error` | LLM provider — check `GOOGLE_API_KEY` and `LLM_PROVIDER` |
| Rows stuck at `pending` | worker died mid-classify (see §5) |

---

## 5. Known limits

1. **Tokens are stored in plaintext**, same as Slack's bot token. Fine for your
   own site; wants envelope encryption (KMS) before anyone else's data is on it.
2. **The webhook URL is a bearer credential.** No signature means anyone who
   learns the URL can inject events. Rotating it means disconnecting and
   reconnecting.
3. **Background processing is in-process.** `BackgroundTasks` dies with the
   worker, leaving `source_events` rows at `pending`. No sweeper, no retry — a
   real queue is the fix. The backfill makes this more visible than Slack does,
   because it queues up to `SYNC_LIMIT` items at once.
4. **One site per workspace.** The consent screen is single-site and the
   callback takes the first entry from `accessible-resources`. A multi-site
   grant needs a picker.
5. **Backfill is issue-only.** `POST /sync` pulls issue descriptions, not their
   comment threads — and comments are often where the decision actually gets
   made. Webhooks do cover comments going forward.
6. **No ACL inheritance.** A restricted project's content lands in the same
   store as a public one. Same existential caveat as Slack's private channels
   (Scope §13).
7. **No dedupe on memory content.** `source_events` prevents re-ingesting the
   same *revision*, but an issue edited three times produces three candidate
   memories saying nearly the same thing. That needs embeddings + similarity,
   which is the next pipeline stage.
