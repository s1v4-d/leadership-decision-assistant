# API Reference

Complete reference for the Leadership Decision Agent REST API. All endpoints are defined in [`backend/src/api/`](../backend/src/api/). Request and response schemas are in [`backend/src/models/schemas.py`](../backend/src/models/schemas.py).

When `DEBUG=true`, interactive Swagger docs are available at http://localhost:8000/docs.

---

## Health & Readiness

Defined in [`backend/src/api/routes.py`](../backend/src/api/routes.py).

### `GET /health`

Liveness check. Always returns 200 if the server is running.

**Response:** `HealthResponse`
```json
{
  "status": "healthy",
  "app_name": "leadership-insight-agent",
  "version": "0.1.0"
}
```

### `GET /ready`

Readiness check. Verifies PostgreSQL and Redis connectivity. Returns 503 if any dependency is degraded.

**Response:** `ReadyResponse`
```json
{
  "status": "ready",
  "checks": {
    "postgres": true,
    "redis": true
  }
}
```

---

## Agent

Defined in [`backend/src/api/agent_routes.py`](../backend/src/api/agent_routes.py).

### `POST /api/v1/agent`

Runs the ReAct agent which reasons about the query, selects tools (`document_search`, `structured_query`, `analyze_context`), and synthesizes an evidence-grounded answer.

**Request:** `AgentRequest`
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | `string` | Yes | — | The question to ask (1-2000 chars) |
| `stream` | `boolean` | No | `false` | Enable Server-Sent Event streaming |
| `collection_id` | `string` | No | `null` | Scope query to a specific collection |

**Response (non-streaming):** `AgentQueryResponse`
```json
{
  "answer": "Based on the quarterly review and financial metrics...",
  "tool_calls_count": 2
}
```

**Response (streaming, `stream: true`):** Server-Sent Events
```
event: answer
data: Based on

event: answer
data: the quarterly

event: done
data: {"tool_calls_count": 2}
```

**Example:**
```bash
# Non-streaming
curl -X POST http://localhost:8000/api/v1/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What are our Q4 2025 revenue trends?"}'

# Streaming
curl -N -X POST http://localhost:8000/api/v1/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize strategic priorities", "stream": true}'
```

---

## Query (Direct RAG)

Defined in [`backend/src/api/query_routes.py`](../backend/src/api/query_routes.py).

### `POST /api/v1/query`

Direct vector search query with Redis caching. Rate limited to **20 requests/minute** per IP.

**Request:** `QueryRequest`
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | `string` | Yes | — | The question to ask (1-2000 chars) |
| `stream` | `boolean` | No | `false` | Enable Server-Sent Event streaming |
| `collection_id` | `string` | No | `null` | Scope query to a specific collection |

**Response:** `QueryResponse`
```json
{
  "answer": "According to the February leadership meeting notes...",
  "sources": [
    {
      "text": "Revenue grew 12% YoY in Q4...",
      "score": 0.87,
      "metadata": {"file_name": "quarterly_review_q4_2025.txt"}
    }
  ],
  "cached": false
}
```

**Caching behavior:**
- Cache key: `query:<SHA256(sanitized_query)>`
- TTL: 3600 seconds (configurable via `REDIS__TTL_SECONDS`)
- Streaming requests bypass cache
- Cache is gracefully optional (no-op on Redis failure)

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What was discussed in the February leadership meeting?"}'
```

---

## Ingestion

Defined in [`backend/src/api/ingest_routes.py`](../backend/src/api/ingest_routes.py).

### `POST /api/v1/ingest`

Upload documents for background ingestion into the vector store. Returns 202 immediately while processing happens asynchronously.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `files` | `File[]` | One or more files to ingest |

Supported formats: `.pdf`, `.docx`, `.txt`, `.md`, `.xlsx`, `.csv`

**Response (202 Accepted):** `IngestResponse`
```json
{
  "status": "accepted",
  "message": "Ingestion started for 3 files",
  "file_count": 3
}
```

**Processing pipeline:**
1. Files saved to a temporary directory
2. `SimpleDirectoryReader` loads documents
3. `SentenceSplitter` chunks text (512 tokens, 50 overlap)
4. `OpenAIEmbedding` generates 1536-dimensional vectors
5. `PGVectorStore` stores vectors with HNSW indexing
6. Temporary directory cleaned up

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "files=@strategy_2026.pdf" \
  -F "files=@kpis.xlsx"
```

---

## Collections

Defined in [`backend/src/api/collection_routes.py`](../backend/src/api/collection_routes.py).

### `POST /api/v1/collections`

Create a new document collection with its own isolated vector table.

**Request:** `CollectionCreate`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Collection name (1-255 chars, must be unique) |
| `description` | `string` | No | Optional description |

**Response (201):** `CollectionResponse`
```json
{
  "id": "a1b2c3d4-...",
  "name": "marketing-reports",
  "description": "Q4 marketing campaign analysis",
  "vector_table": "vec_marketing_reports_a1b2c3d4",
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-01T10:00:00Z"
}
```

Returns **409 Conflict** if a collection with the same name already exists.

### `GET /api/v1/collections`

List all collections.

**Response:** `CollectionResponse[]`
```json
[
  {
    "id": "...",
    "name": "leadership",
    "description": "Default leadership collection",
    "vector_table": "vec_leadership_default",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

### `GET /api/v1/collections/{id}`

Get a single collection by ID. Returns **404** if not found.

### `POST /api/v1/collections/{id}/assets`

Upload files into a specific collection's vector table. The `collection_id` is automatically injected into document metadata.

**Request:** `multipart/form-data` (same as ingestion)

**Response (202):** `AssetUploadResponse`
```json
{
  "status": "accepted",
  "collection_id": "a1b2c3d4-...",
  "file_count": 2
}
```

Returns **404** if collection not found.

**Example:**
```bash
# Create collection
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "marketing-reports", "description": "Campaign analysis docs"}'

# Upload into collection
curl -X POST http://localhost:8000/api/v1/collections/a1b2c3d4-.../assets \
  -F "files=@campaign_report.pdf"

# Query scoped to collection
curl -X POST http://localhost:8000/api/v1/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What were campaign results?", "collection_id": "a1b2c3d4-..."}'
```

---

## Error Responses

All errors return an `ErrorResponse` envelope:

```json
{
  "error": "error_key",
  "detail": "Human-readable explanation",
  "request_id": "uuid-from-x-request-id-header"
}
```

| Status | Error Key | Trigger |
|--------|-----------|---------|
| 422 | `prompt_injection_detected` | Query matched injection pattern |
| 429 | `rate_limit_exceeded` | Exceeded 20 requests/minute on `/api/v1/query` |
| 404 | `not_found` | Collection ID not found |
| 409 | `conflict` | Duplicate collection name |
| 500 | `internal_server_error` | Unhandled exception |
