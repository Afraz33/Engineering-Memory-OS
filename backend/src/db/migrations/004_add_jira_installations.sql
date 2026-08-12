CREATE TABLE jira_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    cloud_id TEXT NOT NULL UNIQUE,
    site_url TEXT,
    site_name TEXT,

    workspace_id TEXT NOT NULL,

    access_token TEXT NOT NULL,
    refresh_token TEXT,

    installed_by TEXT,
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);