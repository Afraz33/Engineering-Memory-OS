import os
import psycopg

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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories (workspace_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories (type);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories (status);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories (created_at);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages (session_id);
"""

def init_db():
    db_url = os.getenv("DATABASE_URL", "postgresql://root@localhost:26257/engineering_memory?sslmode=disable")
    print(f"Connecting to database: {db_url}")

    # First connect to default system database 'defaultdb' to ensure target database exists
    base_url = db_url.rsplit('/', 1)[0] + '/defaultdb?sslmode=disable' if '/' in db_url else db_url
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

if __name__ == "__main__":
    init_db()
