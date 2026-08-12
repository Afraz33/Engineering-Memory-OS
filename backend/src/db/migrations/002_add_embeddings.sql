-- embeddings table
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    
    memory_id UUID REFERENCES memories(id),

    vector VECTOR(1536),   -- adjust dim based on model
    model STRING,          

    created_at TIMESTAMP DEFAULT now()
);

-- index for embeddings
CREATE INDEX ON embeddings USING hnsw(vector);