import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv

# Same reason as db/session.py: this module is also an entry point (`init-db`),
# so nothing else has loaded .env by the time DATABASE_URL is read below.
load_dotenv()

INIT_DB_NAME_SQL = "CREATE DATABASE IF NOT EXISTS engineering_memory;"

# Run separately from the table batch, and allowed to fail: CockroachDB has a
# native VECTOR type and does not implement CREATE EXTENSION. Inside the batch,
# one error here would roll back every CREATE TABLE with it.
INIT_EXTENSIONS_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

INIT_TABLES_SQL = """
-- 1. memories table
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY,
    workspace_id STRING NOT NULL,

    type STRING NOT NULL,
    title STRING NOT NULL,
    body STRING NOT NULL,

    scope STRING DEFAULT 'workspace',
    status STRING DEFAULT 'active',
    confidence FLOAT DEFAULT 0.0,

    entities JSONB,

    superseded_by UUID,

    valid_from TIMESTAMP,
    valid_until TIMESTAMP,

    created_at TIMESTAMP DEFAULT now(),
    last_accessed_at TIMESTAMP,
    access_count INT DEFAULT 0
);

-- 2. memory_provenance table
CREATE TABLE IF NOT EXISTS memory_provenance (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id) ON DELETE CASCADE,

    source STRING,
    author STRING,
    url STRING,
    excerpt STRING,

    created_at TIMESTAMP DEFAULT now()
);

-- 3. embeddings table
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id) ON DELETE CASCADE,

    -- Denormalized from memories so it can prefix the vector index below. A
    -- joined column cannot be an index prefix, and without the prefix the
    -- tenant filter turns the search into a full scan -- see
    -- src/db/migrations/004_add_vector_index.sql for the measured plans.
    workspace_id STRING NOT NULL,

    vector VECTOR(768),
    model STRING,

    created_at TIMESTAMP DEFAULT now()
);

-- 4. messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id STRING NOT NULL,
    role STRING NOT NULL,
    content STRING NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

-- 5. documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content STRING NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT now()
);

-- 6. users table
-- google_sub is the identity key, not email: Google's `sub` claim is permanent
-- while a user's address can change under them.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub STRING NOT NULL UNIQUE,
    email STRING NOT NULL UNIQUE,
    name STRING,
    avatar_url STRING,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- 7. slack_installations table
-- One row per Slack workspace that installed the app. `team_id` is Slack's id
-- for that workspace; `workspace_id` is ours. Keeping both is what lets an
-- inbound webhook — which only ever carries `team_id` — find the right tenant.
CREATE TABLE IF NOT EXISTS slack_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id STRING NOT NULL UNIQUE,
    team_name STRING,

    workspace_id STRING NOT NULL,

    -- xoxb- token. Plaintext today; see docs/slack-integration.md — this wants
    -- envelope encryption before anything but your own workspace is on it.
    bot_token STRING NOT NULL,
    bot_user_id STRING,

    installed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. source_events table
-- Every inbound event, recorded *before* the LLM ever sees it. Two jobs:
--   1. idempotency — Slack retries a delivery up to 3 times, and the unique
--      constraint below turns a retry into a no-op instead of a second memory.
--   2. audit — a message the classifier threw away leaves a row saying so,
--      which is the difference between "nothing worth storing" and a bug.
CREATE TABLE IF NOT EXISTS source_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id STRING NOT NULL,

    source STRING NOT NULL,
    external_id STRING NOT NULL,

    author STRING,
    text STRING,
    occurred_at TIMESTAMPTZ,

    payload JSONB NOT NULL,

    -- pending | stored | quarantined | dropped_prefilter | dropped_classifier | error
    outcome STRING NOT NULL DEFAULT 'pending',
    reason STRING,
    memory_id UUID REFERENCES memories(id) ON DELETE SET NULL,

    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,

    UNIQUE (workspace_id, external_id)
);

-- 8b. jira_installations table
-- The Jira half of the same idea as slack_installations. `cloud_id` is
-- Atlassian's id for the connected site and the routing key for every REST
-- call; `workspace_id` is ours. Unlike Slack's long-lived bot token, a 3LO
-- access token dies after an hour, so the refresh token and expiry live here
-- too. See src/db/migrations/003_add_jira.sql for the full commentary.
CREATE TABLE IF NOT EXISTS jira_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    cloud_id STRING NOT NULL UNIQUE,
    site_name STRING,
    site_url STRING,

    workspace_id STRING NOT NULL,

    access_token STRING NOT NULL,
    refresh_token STRING,
    expires_at TIMESTAMPTZ,
    scopes STRING,

    webhook_id STRING,
    webhook_registered_at TIMESTAMPTZ,
    -- Jira does not sign webhook deliveries for OAuth apps, so this secret in
    -- the callback path is what authenticates an inbound event.
    webhook_secret STRING NOT NULL UNIQUE,

    last_synced_at TIMESTAMPTZ,

    installed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. workspaces table
CREATE TABLE IF NOT EXISTS workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name STRING NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 10. workspace_members table
-- A user can belong to many workspaces at once; users.active_workspace_id
-- (below) says which one is "current" for routes that don't take an explicit
-- workspace_id, e.g. the Slack connector.
CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role STRING NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- 11. workspace_invites table
-- Pending invite by email for someone who hasn't signed in yet. Resolved (and
-- deleted) the next time a matching email completes Google login.
CREATE TABLE IF NOT EXISTS workspace_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email STRING NOT NULL,
    invited_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, email)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories (workspace_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (type);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories (status);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories (created_at);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id);
CREATE INDEX IF NOT EXISTS idx_provenance_memory ON memory_provenance (memory_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_memory ON embeddings (memory_id);
-- Semantic search. Prefixed by workspace_id so the tenant filter narrows the
-- search to one partition instead of defeating the index; cosine because that
-- is the operator (`<=>`) the retrieval query orders by.
CREATE VECTOR INDEX IF NOT EXISTS idx_embeddings_workspace_vector
    ON embeddings (workspace_id, vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_slack_install_workspace ON slack_installations (workspace_id);
CREATE INDEX IF NOT EXISTS idx_jira_install_workspace ON jira_installations (workspace_id);
CREATE INDEX IF NOT EXISTS idx_source_events_workspace ON source_events (workspace_id, received_at DESC);
-- Every audit read is per-source now: Slack's card must not count Jira's events.
CREATE INDEX IF NOT EXISTS idx_source_events_workspace_source ON source_events (workspace_id, source, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_events_outcome ON source_events (outcome);
CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace ON workspace_members (workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_invites_email ON workspace_invites (email);
"""

# One-time backfill for users who existed before the workspaces table did.
# Reuses each user's own id as their personal workspace's id, so it matches
# the workspace_id values already stored in slack_installations / memories /
# source_events for that user -- no data rewrite needed there.
BACKFILL_WORKSPACES_SQL = """
INSERT INTO workspaces (id, name, owner_id)
SELECT u.id, COALESCE(u.name, u.email) || '''s workspace', u.id
FROM users u
LEFT JOIN workspace_members wm ON wm.user_id = u.id
WHERE wm.user_id IS NULL
ON CONFLICT (id) DO NOTHING;

INSERT INTO workspace_members (workspace_id, user_id, role)
SELECT u.id, u.id, 'owner'
FROM users u
LEFT JOIN workspace_members wm ON wm.user_id = u.id
WHERE wm.user_id IS NULL
ON CONFLICT (workspace_id, user_id) DO NOTHING;
"""

# Multi-workspace membership: a user can belong to several workspaces, so the
# one-membership-per-user UNIQUE from the original workspace_members schema
# has to go. Idempotent for both a fresh `init-db` run (constraint/column
# never existed) and an already-migrated database (both IF EXISTS/IF NOT
# EXISTS are no-ops the second time).
#
# Kept as separate statements (not one multi-statement string like the blocks
# above): CockroachDB plans a batched string ahead of executing it, so the new
# active_workspace_id column from the ADD COLUMN isn't visible yet to the
# UPDATE that follows it in the same batch.
MIGRATE_MULTI_WORKSPACE_SQL = [
    "ALTER TABLE workspace_members DROP CONSTRAINT IF EXISTS workspace_members_user_id_key;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL;",
    # Every user had exactly one membership before multi-workspace existed --
    # point them at it so existing sessions keep working without an explicit switch.
    """
    UPDATE users u SET active_workspace_id = wm.workspace_id
    FROM workspace_members wm
    WHERE wm.user_id = u.id AND u.active_workspace_id IS NULL;
    """,
]

def init_db():
    db_url = os.getenv("DATABASE_URL", "postgresql://root@localhost:26257/engineering_memory?sslmode=disable")
    print(f"Connecting to database: {db_url}")

    # First connect to 'defaultdb' to ensure the target database exists. Swap
    # only the path — the query string carries sslmode, and a managed cluster
    # rejects the connection outright without it.
    parsed = urlsplit(db_url)
    base_url = urlunsplit(parsed._replace(path="/defaultdb"))
    try:
        with psycopg.connect(base_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(INIT_DB_NAME_SQL)
    except Exception as e:
        print(f"Database creation check warning: {e}")

    # Connect to target database and create tables
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(INIT_EXTENSIONS_SQL)
            except Exception as e:
                print(f"Skipping vector extension (native on CockroachDB): {e}")

            cur.execute(INIT_TABLES_SQL)
            print("Successfully initialized all database tables and indexes!")

            cur.execute(BACKFILL_WORKSPACES_SQL)
            print("Backfilled personal workspaces for existing users!")

            for statement in MIGRATE_MULTI_WORKSPACE_SQL:
                cur.execute(statement)
            print("Migrated workspace_members to multi-workspace membership!")

if __name__ == "__main__":
    init_db()
