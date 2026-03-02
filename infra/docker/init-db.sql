CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS vector_store;
CREATE SCHEMA IF NOT EXISTS structured;

GRANT USAGE ON SCHEMA vector_store TO CURRENT_USER;
GRANT CREATE ON SCHEMA vector_store TO CURRENT_USER;
GRANT USAGE ON SCHEMA structured TO CURRENT_USER;
GRANT CREATE ON SCHEMA structured TO CURRENT_USER;

CREATE TABLE IF NOT EXISTS structured.collections (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    vector_table VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS structured.business_metrics (
    id VARCHAR(36) PRIMARY KEY,
    collection_id VARCHAR(36) NOT NULL REFERENCES structured.collections(id),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50),
    period VARCHAR(50),
    category VARCHAR(100),
    source_file VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
