# Jira integration

How a Jira issue becomes a memory

## 1. The flow

```text
Jira Cloud
   │
   │ User clicks Connect
   ▼
GET /api/jira/install
   │
   ▼
Atlassian OAuth 2.0
   │
   ▼
GET /api/jira/callback
   │
   ├─ verify state
   ├─ exchange code for tokens
   ├─ get Jira Cloud ID
   └─ store installation
   │
   ▼
POST /api/jira/sync
   │
   ├─ run JQL
   ├─ fetch issues
   ├─ record in `source_events`
   │     └─ already seen → skip
   │
   └─ background: normalize → classify → persist
                                      │
                         memories + provenance + embeddings
                                      │
                         update `source_events`
````

Two tables are involved:

| table                | purpose                                      |
| -------------------- | -------------------------------------------- |
| `jira_installations` | Stores Jira connection and OAuth information |
| `source_events`      | Stores raw Jira issues and tracks ingestion  |

`source_events` is shared with Slack so every connector uses the same ingestion
and audit system.

---

## 2. What you do on Atlassian

### a. Create the app

Go to:

[https://developer.atlassian.com/console/myapps/](https://developer.atlassian.com/console/myapps/)

Create an app using **OAuth 2.0 (3LO)**.

### b. Add credentials

Add these to `backend/.env`:

```bash
JIRA_CLIENT_ID=...
JIRA_CLIENT_SECRET=...
```

Keep the client secret on the backend.

### c. Configure redirect URL

If using ngrok:

```bash
ngrok http 8000
```

Then set:

```bash
BACKEND_URL=https://your-ngrok-url.ngrok-free.app
FRONTEND_URL=http://localhost:5173
```

In the Atlassian app, add:

```text
https://your-ngrok-url.ngrok-free.app/api/jira/callback
```

This must exactly match `BACKEND_URL + /api/jira/callback`.

### d. Add scopes

For read-only Jira ingestion:

```text
read:jira-work
read:jira-user
offline_access
```

We don't need Jira write permissions.

---

## 3. Connect Jira

From the application:

```text
Sources → Jira → Connect
```

This starts the OAuth flow.

After approval:

```text
Atlassian
   ↓
/api/jira/callback
   ↓
jira_installations
   ↓
Jira connected
```

---

## 4. Sync issues

The connector uses JQL to fetch issues.

Example:

```json
{
  "jql": "project = ENG ORDER BY updated DESC",
  "max_results": 100
}
```

The backend fetches:

```text
Issue key
Summary
Description
Project
Issue type
Status
Priority
Labels
Components
Reporter
Assignee
Created
Updated
Jira URL
```

Then:

```text
Jira issue
    ↓
source_events
    ↓
normalize()
    ↓
AI classification
    ↓
memory + embedding
```

---

## 5. Issue updates

Issues can change, so the external ID should include the update timestamp:

```text
jira:{cloud_id}:{issue_key}:{updated_timestamp}
```

Example:

```text
jira:abc123:ENG-123:2026-08-12T14:30:00
```

This means:

```text
Same issue + same update → skip

Same issue + new update → ingest again
```

---

## 6. API endpoints

| endpoint                      | purpose                 |
| ----------------------------- | ----------------------- |
| `GET /api/jira/install`       | Start OAuth             |
| `GET /api/jira/callback`      | Handle OAuth callback   |
| `GET /api/jira/status`        | Check connection        |
| `DELETE /api/jira/disconnect` | Disconnect Jira         |
| `POST /api/jira/sync`         | Fetch and ingest issues |
| `GET /api/jira/activity`      | View ingestion activity |

---

## 7. Configuration

```bash
JIRA_CLIENT_ID=...
JIRA_CLIENT_SECRET=...

BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

---

# End improvements

These are **not required for the MVP**, but can be added later:

1. **Pagination** — fetch more than 100 issues safely.
2. **Jira webhooks** — automatically ingest new/updated issues instead of polling.
3. **Token encryption** — encrypt OAuth tokens in production.
4. **Token refresh** — automatically refresh expired access tokens.
5. **Comments** — add Jira comments to the knowledge base.
6. **Attachments** — extract and index PDFs, documents, etc.
7. **Linked issues** — include relationships between Jira issues.
8. **Changelog** — track important issue history.
9. **ACL support** — preserve Jira permissions in the knowledge base.
10. **Background queue** — replace in-process `BackgroundTasks` with a real worker.
11. **Version cleanup** — remove/supersede old embeddings when an issue changes.
12. **Semantic deduplication** — avoid storing duplicate knowledge from similar issues.
13. **Multi-workspace support** — replace the current user-based workspace model.