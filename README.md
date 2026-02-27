# AI Leadership Insight & Decision Agent

Enterprise-grade AI system that ingests company documents and answers leadership questions grounded in those documents using RAG (Retrieval-Augmented Generation).

## Features

- **Document Ingestion** — PDF, DOCX, XLSX parsing with semantic chunking
- **RAG Pipeline** — Vector search with reranking for grounded, cited answers
- **ReAct Agent** — LlamaIndex-powered reasoning with tool orchestration
- **Async API** — FastAPI with streaming SSE responses
- **Security** — PII masking, prompt injection detection, rate limiting
- **Observability** — Structured logging, OpenTelemetry traces, Prometheus metrics
- **Evaluation** — RAGAS-based quality metrics for retrieval and generation

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM Framework | LlamaIndex v0.14.x (ReAct Agent) |
| API | FastAPI 0.115+ |
| Vector Store | Qdrant |
| Cache | Redis |
| Database | PostgreSQL (audit/metadata) |
| UI | Streamlit |
| Observability | structlog + OpenTelemetry + Prometheus |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (installed automatically by `make init`)
- Docker & Docker Compose (for infrastructure services)

### Setup

```bash
# Clone and initialize
git clone <repo-url>
cd leadership-decision-assistant
make init

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure (Qdrant, Redis, PostgreSQL)
make up

# Run the API server
make dev

# Run the Streamlit UI (separate terminal)
make ui
```

### Development

```bash
make lint          # Ruff linter
make format        # Ruff formatter
make typecheck     # mypy strict mode
make check         # lint + format + typecheck
make test          # Unit tests
make test-cov      # Tests with coverage report
make test-all      # Unit + integration + evaluation
make pre-commit    # Run all pre-commit hooks
make help          # Show all available targets
```

## Project Structure

```
├── backend/
│   ├── src/
│   │   ├── api/            # FastAPI app, routes, dependencies
│   │   ├── agents/         # LlamaIndex ReAct agent + prompts
│   │   ├── core/           # Config, LLM provider, logging, security
│   │   ├── ingestion/      # Document parsing and chunking pipeline
│   │   ├── models/         # Pydantic schemas and domain models
│   │   └── tools/          # RAG and search tools for the agent
│   └── tests/
│       ├── unit/           # Isolated unit tests
│       ├── integration/    # API integration tests
│       └── evaluation/     # RAG quality evaluation (RAGAS)
├── ui/                     # Streamlit frontend
├── infra/                  # Docker + Terraform
├── data/                   # Sample documents (gitignored)
├── pyproject.toml          # Single dependency and tooling config
├── Makefile                # Developer workflow commands
└── docker-compose.yml      # Infrastructure services
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE) for details.
