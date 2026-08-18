-- Semantic retrieval: make the vectors we were already writing readable.
--
-- Until now `embeddings.vector` was write-only. `add_embedding` filled it on
-- every capture and nothing ever queried it -- /api/retrieve ran a lexical
-- token match instead. This migration adds what a vector search actually
-- needs: a tenant column to partition on, and a C-SPANN index to search.
--
-- Two decisions worth the ink:
--
-- 1. `workspace_id` is denormalized from `memories`. It is redundant -- you can
--    reach it with a join -- but it cannot live behind one. A vector index is
--    only used when the query's equality filters match its *prefix* columns,
--    and a joined column cannot be a prefix. See (2).
--
-- 2. The index is prefixed by workspace_id, not built on the vector alone.
--    This is the whole ballgame for a multi-tenant store. Measured on this
--    cluster (v26.2) with a bare `CREATE VECTOR INDEX ON t (v)`:
--
--        EXPLAIN ... WHERE workspace_id = 'ws1' ORDER BY v <=> $1 LIMIT 3
--          -> filter -> scan  table: t@t_pkey  spans: FULL SCAN
--
--    The tenant filter defeats the index completely and reads every row in the
--    table. With the prefix in place the same query plans as:
--
--        -> vector search  table: t@t_workspace_id_v_idx
--             prefix spans: [/'ws1' - /'ws1']
--
--    i.e. an index-backed search confined to one tenant's partition, which is
--    the behaviour we want and the reason this column exists.
--
-- Opclass is cosine, not the `vector_l2_ops` default: gemini-embedding-001
-- vectors are compared by angle, and `<=>` is the operator the retrieval query
-- uses. Mismatching these silently falls back to a scan.

ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS workspace_id STRING;

-- Backfill from the owning memory. The FK is ON DELETE CASCADE, so every
-- surviving embedding has a memory to read this from and no row is left null.
UPDATE embeddings e
SET workspace_id = m.workspace_id
FROM memories m
WHERE m.id = e.memory_id
  AND e.workspace_id IS NULL;

-- Only meaningful once the backfill above has run: a null here would land every
-- orphan in a single shared partition, which is a correctness leak between
-- tenants, not just untidy.
ALTER TABLE embeddings ALTER COLUMN workspace_id SET NOT NULL;

CREATE VECTOR INDEX IF NOT EXISTS idx_embeddings_workspace_vector
    ON embeddings (workspace_id, vector vector_cosine_ops);
