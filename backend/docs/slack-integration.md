# Slack integration

How a Slack message becomes a memory, and what you have to do on Slack's side
to make it happen.

---

## 1. The flow

```
Slack workspace
   │  message posted in a channel the bot is in
   ▼
POST /api/slack/events          ← signature-verified, must ack in 3s
   │
   ├─ url_verification?  → echo the challenge, done
   ├─ bot / edit / our own reply?  → 200, ignored
   ├─ record in `source_events`  (UNIQUE workspace+external_id)
   │     └─ already there? → 200, this is a Slack retry, stop
   ├─ 200 OK  ────────────────────────────────► Slack (well inside 3s)
   │
   └─ background: enrich → normalize → prefilter → classify → persist
                                                        │
                          `memories` + `memory_provenance` + `embeddings`
                                                        │
                              update `source_events.outcome` + `memory_id`
```

Two tables carry the connector:

| table | why it exists |
|---|---|
| `slack_installations` | maps Slack's `team_id` → our `workspace_id`, holds the bot token |
| `source_events` | every inbound event, recorded *before* the LLM runs |

`source_events` does two jobs. Its unique constraint on
`(workspace_id, external_id)` makes Slack's retries idempotent — without it a
slow classifier turns one message into three identical memories. And it keeps a
row for events the pipeline *rejected*, so "nothing worth storing" is
distinguishable from a bug.

---

## 2. What you do on Slack

### a. Create the app

1. <https://api.slack.com/apps> → **Create New App** → **From scratch**.
2. Name it (e.g. *Memory OS*), pick your workspace.

### b. Get the credentials

**Basic Information → App Credentials.** Copy into `backend/.env`:

```bash
SLACK_CLIENT_ID=...
SLACK_CLIENT_SECRET=...
SLACK_SIGNING_SECRET=...
```

The signing secret is what proves an inbound webhook actually came from Slack.
Anyone holding it can forge events into your memory store — treat it as a
password.

### c. Expose your local backend

Slack must reach your server over public HTTPS. `localhost` will not do.

```bash
ngrok http 8000        # → https://a1b2c3.ngrok-free.app
```

Then in `backend/.env`:

```bash
BACKEND_URL=https://a1b2c3.ngrok-free.app
FRONTEND_URL=http://localhost:5173
```

> The free ngrok URL changes every restart. When it does, update `BACKEND_URL`
> **and** both URLs in the Slack app config below, or OAuth fails with
> `redirect_uri_mismatch` and events stop arriving.

### d. Redirect URL

**OAuth & Permissions → Redirect URLs → Add**:

```
https://a1b2c3.ngrok-free.app/api/slack/callback
```

Save. This must match `BACKEND_URL + /api/slack/callback` byte for byte.

### e. Bot scopes

**OAuth & Permissions → Scopes → Bot Token Scopes**:

| scope | what it buys |
|---|---|
| `channels:history` | read messages in public channels |
| `channels:read` | resolve `C01AB` → `#eng-decisions` |
| `groups:history` | read messages in private channels |
| `groups:read` | resolve private channel names |
| `users:read` | resolve `U01XY` → `afraz` |
| `chat:write` | post `/ask` answers back |
| `commands` | register the `/ask` slash command |

Adding a scope later forces every workspace to reinstall, so add all of them now.

### f. Event subscriptions

**Event Subscriptions → Enable Events → Request URL**:

```
https://a1b2c3.ngrok-free.app/api/slack/events
```

Your backend must be running when you paste this — Slack immediately POSTs a
`url_verification` challenge and refuses to save the URL until it gets the echo
back. (That handler is the first branch in `slack.py`.)

Then **Subscribe to bot events** → add:

- `message.channels` — public channels
- `message.groups` — private channels

Save changes.

### g. Slash command (optional)

**Slash Commands → Create New Command**:

| field | value |
|---|---|
| Command | `/ask` |
| Request URL | `https://a1b2c3.ngrok-free.app/api/slack/commands` |
| Description | Ask the team's memory a question |

### h. Connect it

Restart the backend, open the app → **Sources** → **Connect** on the Slack card.
That runs the OAuth flow and writes the row in `slack_installations`.

### i. Invite the bot

The bot only sees channels it is in:

```
/invite @Memory OS
```

Post something with a real decision in it — short chatter is dropped by the
pre-filter on purpose:

> We decided to use Postgres SKIP LOCKED for the job queue instead of Redis,
> because Redis didn't give us the ordering guarantees we needed.

Within a few seconds it should appear under **Recent activity** on the Sources
page, marked `stored`.

---

## 3. Configuration

| variable | default | meaning |
|---|---|---|
| `SLACK_CLIENT_ID` | — | Slack app credential |
| `SLACK_CLIENT_SECRET` | — | Slack app credential |
| `SLACK_SIGNING_SECRET` | — | verifies inbound webhooks |
| `BACKEND_URL` | `http://localhost:8000` | public URL Slack calls |
| `FRONTEND_URL` | `http://localhost:5173` | where OAuth returns the user |
| `MEMORY_STORE` | `postgres` | `memory` for the throwaway dict |
| `CAPTURE_CONFIDENCE_THRESHOLD` | `0.6` | below this → `quarantined` |
| `CAPTURE_MIN_LENGTH` | `40` | shorter messages need a signal term |

---

## 4. Troubleshooting

| symptom | cause |
|---|---|
| Slack won't save the Request URL | backend not running, or `SLACK_SIGNING_SECRET` wrong/unset |
| `redirect_uri_mismatch` | `BACKEND_URL` ≠ the registered Redirect URL |
| Events arrive, nothing stored | expected — check `outcome` in **Recent activity**; most chatter is meant to be dropped |
| Everything `dropped_prefilter` | messages are too short; lower `CAPTURE_MIN_LENGTH` |
| Everything `error` | LLM provider — check `GOOGLE_API_KEY` and `LLM_PROVIDER` |
| Memories stored but search finds nothing | embeddings need `GOOGLE_API_KEY`; capture degrades without it rather than failing |
| Rows stuck at `pending` | worker died mid-classify (see §5) |

---

## 5. Known limits

1. **Bot tokens are stored in plaintext.** Fine for your own workspace; wants
   envelope encryption (KMS) before anyone else's data is on it.
2. **Background processing is in-process.** `BackgroundTasks` dies with the
   worker, leaving `source_events` rows at `pending`. There is no sweeper and no
   retry yet — a real queue is the fix.
3. **No workspace model.** `workspace_id` is the installing user's id
   (`workspace_id_for` in `app/api/slack.py` is the only place that decides
   this). Two people in one Slack workspace get two tenants.
4. **No ACL inheritance.** A private channel's content lands in the same store
   as a public one, readable by anyone with that workspace id. Scope §13 calls
   this existential; it must be solved before multi-user.
5. **No dedupe on memory content.** `source_events` prevents re-ingesting the
   same *message*, but two people stating the same decision in different words
   produce two memories. That needs embeddings + similarity, which is the next
   pipeline stage.
6. **No backfill.** Only messages posted after the install are captured;
   `conversations.history` is never called.
