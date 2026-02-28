CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS collections (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    vector_table VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    id VARCHAR(36) PRIMARY KEY,
    collection_id VARCHAR(36) NOT NULL REFERENCES collections(id),
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    metadata_ TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_metrics (
    id VARCHAR(36) PRIMARY KEY,
    collection_id VARCHAR(36) NOT NULL REFERENCES collections(id),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50),
    period VARCHAR(50),
    category VARCHAR(100),
    source_file VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
