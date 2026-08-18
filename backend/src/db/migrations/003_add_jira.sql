-- Jira connector.
--
-- Mirrors slack_installations: one row per connected Atlassian site, keyed by
-- the id Atlassian puts in every API path (`cloud_id`) and carrying our own
-- tenant id alongside it, so an inbound webhook — which knows the site but not
-- the workspace — can resolve a tenant in one lookup.
--
-- Nothing here duplicates source_events: Jira reuses that table with
-- source = 'jira', which is what keeps the audit feed and the outcome counters
-- source-agnostic.

CREATE TABLE IF NOT EXISTS jira_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Atlassian's id for the site. Every REST call goes to
    -- api.atlassian.com/ex/jira/{cloud_id}/..., so this is the routing key.
    cloud_id STRING NOT NULL UNIQUE,
    site_name STRING,
    site_url STRING,

    workspace_id STRING NOT NULL,

    -- 3LO access tokens expire in an hour, so unlike Slack's xoxb- token these
    -- are worthless without the refresh token beside them. Plaintext today,
    -- same caveat as slack_installations.bot_token — see docs/jira-integration.md.
    access_token STRING NOT NULL,
    refresh_token STRING,
    expires_at TIMESTAMPTZ,
    scopes STRING,

    -- Dynamic webhook registered through the REST API at connect time.
    -- Atlassian expires these after 30 days unless refreshed, so the
    -- registration timestamp is load-bearing, not decoration.
    webhook_id STRING,
    webhook_registered_at TIMESTAMPTZ,

    -- Jira does not sign webhook deliveries for OAuth apps the way Slack does,
    -- so the shared secret rides in the callback path instead and is what
    -- authenticates an inbound event. Unique: it is also the lookup key.
    webhook_secret STRING NOT NULL UNIQUE,

    -- High-water mark for the JQL backfill, so a re-sync only pulls issues
    -- touched since the last one.
    last_synced_at TIMESTAMPTZ,

    installed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jira_install_workspace ON jira_installations (workspace_id);

-- The audit feed is now per-source (Slack's card must not count Jira's events),
-- so every read of source_events filters on source as well as workspace.
CREATE INDEX IF NOT EXISTS idx_source_events_workspace_source
    ON source_events (workspace_id, source, received_at DESC);
