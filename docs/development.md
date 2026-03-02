# Development Guide

Guide for contributing to and developing the Leadership Decision Agent.

---

## Local Setup

### Prerequisites

- **Python 3.12+** — [download](https://www.python.org/downloads/)
- **uv** (Astral) — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **Docker** and **Docker Compose** — [install](https://docs.docker.com/get-docker/)
- **OpenAI API key** — [get one](https://platform.openai.com/api-keys)

### Initial Setup

```bash
git clone https://github.com/s1v4-d/leadership-decision-assistant.git
cd leadership-decision-assistant

make init              # uv sync + pre-commit hooks (including commit-msg)
cp .env.example .env   # Edit and set OPENAI_API_KEY
```

`make init` does three things:
1. `uv sync` — installs all dependencies (production + dev) into a single `.venv` at the workspace root
2. `uv run pre-commit install --install-hooks` — installs pre-commit hooks
3. `uv run pre-commit install --hook-type commit-msg` — installs conventional commit linting

### Running Locally

```bash
make start     # Start all services (FastAPI + Streamlit + PostgreSQL + Redis)
make logs      # Tail container logs
make stop      # Stop and clean up
```

Services:
- **FastAPI:** http://localhost:8000 (API docs at http://localhost:8000/docs)
- **Streamlit:** http://localhost:8501
- **PostgreSQL:** localhost:5432
- **Redis:** localhost:6379

---

## Tooling Policy

All tools are invoked via `make` targets or `uv run`. Never use bare `pip`, `python`, `pytest`, `ruff`, or `mypy` directly.

| Action | Command |
|--------|---------|
| Install/sync deps | `make init` or `uv sync` |
| Run linter | `uv run ruff check .` |
| Run formatter | `uv run ruff format .` |
| Run type checker | `uv run mypy backend/src/ --config-file pyproject.toml` |
| Run tests | `uv run pytest backend/tests/ -v --tb=short` |
| Run everything | `make tests` (lint + typecheck + tests) |
| Add a dependency | Add to `pyproject.toml`, then `uv sync` |

Never `pip install` anything. All dependencies are declared in [`pyproject.toml`](../pyproject.toml) and resolved via `uv sync`.

### Dependency Groups

| Group | Where | Purpose |
|-------|-------|---------|
| `[project.dependencies]` | Production | FastAPI, LlamaIndex, database drivers, etc. |
| `[dependency-groups].dev` | Development | Ruff, mypy, pytest, pre-commit, mocking libs |
| `[dependency-groups].eval` | Evaluation | RAGAS, datasets |
| `[dependency-groups].providers` | Optional | Anthropic, Ollama, HuggingFace LLM support |

---

## Testing

The project follows **Test-Driven Development** — tests are written first, then implementation. Three test tiers exist:

### Unit Tests

Fast, isolated tests with mocked external dependencies.

```bash
uv run pytest backend/tests/unit/ -v --tb=short
```

19 test modules in [`backend/tests/unit/`](../backend/tests/unit/):

| Module | Coverage |
|--------|----------|
| `test_config.py` | Settings loading, env overrides, nested config |
| `test_llm_provider.py` | LLM/embedding factory, provider switching |
| `test_security.py` | Sanitization, injection detection, PII masking |
| `test_leadership_agent.py` | Agent construction, tool wiring, execution |
| `test_rag_tool.py` | Vector store creation, query engine, search |
| `test_sql_tool.py` | SQL database, NL2SQL engine |
| `test_ingestion.py` | Pipeline construction, document processing |
| `test_excel_parser.py` | Excel/CSV parsing, metrics ingestion |
| `test_api.py` | App factory, middleware, exception handlers |
| `test_query_api.py` | Query endpoint, caching, streaming |
| `test_agent_routes.py` | Agent endpoint, SSE streaming |
| `test_collection_routes.py` | Collection CRUD, asset upload |
| `test_ingest_api.py` | Ingestion endpoint |
| `test_database.py` | Engine creation, schema management |
| `test_tables.py` | ORM table definitions |
| `test_telemetry.py` | OpenTelemetry setup, metrics recording |
| `test_seed.py` | Data seeding logic |
| `test_multi_collection_search.py` | Multi-collection vector search |
| `test_ui_api_client.py` | Streamlit API client |

### Integration Tests

Test real service interactions against the Docker Compose stack:

```bash
make start   # Ensure services are running
uv run pytest backend/tests/integration/ -m integration -v
```

| Module | Coverage |
|--------|----------|
| `test_api_integration.py` | Full API lifecycle with real database |
| `test_e2e_rag.py` | Ingest docs -> RAG query -> verify sources |
| `test_e2e_sql.py` | Ingest Excel -> NL2SQL query -> verify answer |
| `test_e2e_agent.py` | Agent routes correct tool for query type |

### Evaluation Tests

RAG quality evaluation using [RAGAS](https://docs.ragas.io/) metrics:

```bash
uv run pytest backend/tests/evaluation/ -m evaluation -v
```

Golden datasets in [`backend/tests/evaluation/`](../backend/tests/evaluation/):
- `golden_dataset.json` — RAG evaluation (faithfulness, relevancy)
- `multi_tool_golden_dataset.json` — Multi-tool agent evaluation

### Test Naming Convention

All tests follow `test_<unit>_<scenario>_<expected>`:

```python
def test_create_llm_with_invalid_provider_raises_value_error(): ...
def test_sanitize_query_removes_control_characters(): ...
def test_detect_injection_with_ignore_instructions_raises(): ...
```

### Test Configuration

Configured in [`pyproject.toml`](../pyproject.toml):

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (fast, no external deps)",
    "integration: Integration tests (require running services)",
    "evaluation: RAG evaluation tests (slow, require LLM)",
]
addopts = "-v --tb=short -m 'not integration and not evaluation'"
```

By default, `pytest` runs only unit tests. Integration and evaluation tests require explicit markers.

---

## Code Style

### Linter & Formatter

**Ruff** handles both linting and formatting (replaces flake8, isort, black). Full config in [`pyproject.toml`](../pyproject.toml).

```bash
uv run ruff check .              # Lint
uv run ruff check . --fix        # Auto-fix
uv run ruff format .             # Format
uv run ruff format --check .     # Check formatting
```

Key settings: `line-length = 120`, `target-version = "py312"`, Google-style docstrings.

### Type Checking

**mypy** in strict mode with Pydantic plugin:

```bash
uv run mypy backend/src/ --config-file pyproject.toml
```

All function signatures require type annotations. Third-party stubs are configured for libraries without type support.

### Pre-commit Hooks

Installed by `make init`. Runs on every commit:
- Ruff (lint + format)
- mypy
- Trailing whitespace removal
- YAML lint
- Conventional commit message validation

---

## Git Conventions

### Commit Messages

Conventional commits are enforced by a commit-msg hook:

```
<type>(scope): concise imperative description
```

| Type | Use |
|------|-----|
| `feat` | New feature |
| `fix` | Bug fix |
| `test` | Adding/updating tests |
| `refactor` | Code restructuring |
| `docs` | Documentation |
| `chore` | Maintenance |
| `ci` | CI/CD changes |
| `build` | Build system changes |

Examples:
```
feat(config): add model-agnostic LLM provider settings
test(security): add sanitize_query edge case coverage
refactor(api): extract health check into dedicated router
```

### Branch Naming

```
<type>/<short-description>
```

Branch from `main`. Examples: `feat/repo-scaffold`, `fix/docker-timeout`, `ci/github-actions`.

---

## Configuration Reference

All configuration flows through [`backend/src/core/config.py`](../backend/src/core/config.py) via Pydantic Settings v2. Variables load from `.env` with `__` as the nested delimiter.

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `leadership-insight-agent` | Application identifier |
| `DEBUG` | `true` | Enables API docs UI, reload mode |
| `LOG_LEVEL` | `DEBUG` | Root log level |
| `LOG_FORMAT` | `console` | `json` for production, `console` for dev |
| `API_HOST` | `0.0.0.0` | Uvicorn bind address |
| `API_PORT` | `8000` | Uvicorn bind port |
| `API_WORKERS` | `1` | Uvicorn worker count |
| `ALLOWED_HOSTS` | `*` | TrustedHost middleware |
| `CORS_ORIGINS` | `http://localhost:8501,...` | CORS allowed origins (comma-separated) |

### LLM & Embeddings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `sk-change-me` | OpenAI API key (`SecretStr`) |
| `LLM_PROVIDER` | `openai` | LLM backend (`openai`, `anthropic`) |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `LLM_TEMPERATURE` | `0.1` | LLM temperature |
| `LLM_MAX_TOKENS` | `4096` | LLM max output tokens |
| `LLM_REQUEST_TIMEOUT` | `60` | LLM request timeout (seconds) |
| `EMBEDDING_PROVIDER` | `openai` | Embedding backend |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `EMBEDDING_DIMENSION` | `1536` | Embedding vector dimension |

### PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES__HOST` | `localhost` | PostgreSQL host |
| `POSTGRES__PORT` | `5432` | PostgreSQL port |
| `POSTGRES__USER` | `leadership` | PostgreSQL user |
| `POSTGRES__PASSWORD` | `leadership_dev_password` | PostgreSQL password (`SecretStr`) |
| `POSTGRES__DATABASE` | `leadership_agent` | Database name |
| `POSTGRES__VECTOR_TABLE` | `document_vectors` | Default vector table name |
| `POSTGRES__VECTOR_SCHEMA` | `vector_store` | Schema for vector tables |
| `POSTGRES__SQL_SCHEMA` | `structured` | Schema for ORM tables |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS__URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS__TTL_SECONDS` | `3600` | Cache TTL |

### RAG Pipeline

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG__CHUNK_SIZE` | `512` | SentenceSplitter chunk size (tokens) |
| `RAG__CHUNK_OVERLAP` | `50` | SentenceSplitter overlap |
| `RAG__SIMILARITY_TOP_K` | `5` | Top-K vector search results |
| `RAG__RERANK_TOP_N` | `3` | Reranker top-N |
| `RAG__RESPONSE_MODE` | `tree_summarize` | LlamaIndex response synthesis mode |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `SECURITY__RATE_LIMIT` | `20/minute` | SlowAPI rate limit on query endpoint |
| `SECURITY__MAX_QUERY_LENGTH` | `2000` | Maximum query characters |
| `SECURITY__ENABLE_PII_MASKING` | `true` | PII detection and masking via Presidio |
| `SECURITY__BLOCKED_PATTERNS` | `""` | Extra prompt injection patterns (comma-separated) |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_ENABLED` | `false` | Toggle OpenTelemetry tracing + metrics |
| `OTEL_SERVICE_NAME` | `leadership-insight-agent` | OTel service name |
| `OTEL_EXPORTER_ENDPOINT` | `""` | OTLP gRPC endpoint (empty = console exporter) |

---

## Tech Stack

### Core Runtime

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | >= 3.12 | Language runtime |
| FastAPI | >= 0.115.0 | Async web framework |
| Uvicorn | >= 0.32.0 | ASGI server |
| Pydantic | >= 2.10.0 | Data validation and schemas |
| Pydantic Settings | >= 2.7.0 | Environment-based configuration |
| Streamlit | >= 1.41.0 | Chat UI |

### AI / ML

| Technology | Version | Purpose |
|------------|---------|---------|
| LlamaIndex Core | >= 0.14.0 | Agent framework, query engines, ingestion |
| LlamaIndex OpenAI LLMs | >= 0.4.0 | GPT-4o-mini integration |
| LlamaIndex OpenAI Embeddings | >= 0.3.0 | text-embedding-3-small |
| LlamaIndex PGVector | >= 0.6.0 | PostgreSQL vector store |

### Data Layer

| Technology | Version | Purpose |
|------------|---------|---------|
| PostgreSQL + pgvector | 17 + 0.8.0 | Vector storage (HNSW) + structured data |
| SQLAlchemy | >= 2.0.0 | ORM for structured tables |
| Redis | 7-alpine | Response caching |

### Security & Observability

| Technology | Purpose |
|------------|---------|
| Presidio Analyzer + Anonymizer | PII detection and masking |
| SlowAPI | Rate limiting |
| structlog | Structured logging (JSON + console) |
| OpenTelemetry | Distributed tracing + Prometheus metrics |

### Development

| Technology | Purpose |
|------------|---------|
| uv (Astral) | Dependency management and virtual environments |
| Ruff | Linter + formatter |
| mypy (strict) | Static type checking |
| pytest + pytest-asyncio | Test framework |
| RAGAS | RAG evaluation metrics |
| pre-commit | Git hook management |

### Infrastructure

| Technology | Purpose |
|------------|---------|
| Docker (multi-stage) | Containerization |
| Docker Compose | Local dev orchestration |
| Terraform | AWS ECS Fargate infrastructure |
| GitHub Actions | CI/CD pipelines |
