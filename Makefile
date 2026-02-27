.DEFAULT_GOAL := help

BACKEND_DIR := backend
DOCKER_COMPOSE := docker compose

.PHONY: init
init:
	uv sync
	uv run pre-commit install --install-hooks
	uv run pre-commit install --hook-type commit-msg

.PHONY: sync
sync:
	uv sync

.PHONY: dev
dev:
	uv run uvicorn backend.src.api.main:create_app --factory --reload --host 0.0.0.0 --port 8000

.PHONY: ui
ui:
	uv run streamlit run ui/app.py --server.port 8501

.PHONY: lint
lint:
	uv run ruff check .
	uv run ruff format --check .

.PHONY: lint-fix
lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

.PHONY: format
format:
	uv run ruff format .

.PHONY: typecheck
typecheck:
	uv run mypy backend/src/ --config-file pyproject.toml

.PHONY: check
check: lint typecheck

.PHONY: pre-commit
pre-commit:
	uv run pre-commit run --all-files

.PHONY: test
test:
	uv run pytest $(BACKEND_DIR)/tests/ -v --tb=short

.PHONY: test-cov
test-cov:
	uv run pytest $(BACKEND_DIR)/tests/ --cov=$(BACKEND_DIR)/src --cov-report=term-missing --cov-report=html

.PHONY: test-integration
test-integration:
	uv run pytest $(BACKEND_DIR)/tests/ -m integration -v --tb=short

.PHONY: test-eval
test-eval:
	uv run pytest $(BACKEND_DIR)/tests/ -m evaluation -v --tb=long

.PHONY: test-all
test-all:
	uv run pytest $(BACKEND_DIR)/tests/ -v --tb=short -m ""

.PHONY: up
up:
	$(DOCKER_COMPOSE) up -d

.PHONY: down
down:
	$(DOCKER_COMPOSE) down

.PHONY: build
build:
	$(DOCKER_COMPOSE) build

.PHONY: logs
logs:
	$(DOCKER_COMPOSE) logs -f

.PHONY: clean
clean:
	$(DOCKER_COMPOSE) down -v --remove-orphans 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache .pytest_cache htmlcov .coverage

.PHONY: help
help:
	@uv run python -c "import re; lines=open('Makefile').readlines(); targets=[(m.group(1),m.group(2)) for l in lines if (m:=re.match(r'^([a-zA-Z_-]+):.*?##\s*(.*)$$',l))]; [print(f'  {n:<20s} {d}') for n,d in targets] if targets else print('  No documented targets. Add ## comments to Makefile targets.')"

init: ## Bootstrap project — install deps and pre-commit hooks
sync: ## Sync dependencies from lockfile
dev: ## Run backend with hot-reload
ui: ## Run Streamlit UI
lint: ## Run linter and format check
lint-fix: ## Auto-fix lint and format issues
format: ## Format all source files
typecheck: ## Run mypy type checker
check: ## Run all code quality checks
pre-commit: ## Run pre-commit hooks on all files
test: ## Run unit tests
test-cov: ## Run tests with coverage
test-integration: ## Run integration tests
test-eval: ## Run RAG evaluation tests
test-all: ## Run entire test suite
up: ## Start services via Docker Compose
down: ## Stop services
build: ## Build Docker images
logs: ## Tail service logs
clean: ## Remove containers, caches, artifacts
help: ## Show available targets
