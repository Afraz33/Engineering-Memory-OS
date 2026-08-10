-- memories table
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

    created_at TIMESTAMP,
    last_accessed_at TIMESTAMP,
    access_count INT DEFAULT 0
);

-- provenance table
CREATE TABLE IF NOT EXISTS memory_provenance (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id),

    source STRING,
    author STRING,
    url STRING,
    excerpt STRING,

    created_at TIMESTAMP DEFAULT now()
);

-- indexes (important)
CREATE INDEX ON memories (workspace_id);
CREATE INDEX ON memories (type);
CREATE INDEX ON memories (status);
CREATE INDEX ON memories (created_at);