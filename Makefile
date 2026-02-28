.DEFAULT_GOAL := help

.PHONY: init tests start stop build help

init: ## Install all deps and pre-commit hooks
	uv sync
	uv run pre-commit install --install-hooks
	uv run pre-commit install --hook-type commit-msg

tests: ## Run linter, type checker, and test suite
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy backend/src/ --config-file pyproject.toml
	uv run pytest backend/tests/ -v --tb=short

start: ## Start containers in the background
	docker compose up -d

stop: ## Stop containers and prune volumes
	docker compose down -v --remove-orphans

build: ## Rebuild containers from scratch
	docker compose down -v --remove-orphans
	docker compose build --no-cache
	docker compose up -d

help: ## Show available targets
	@uv run python -c "import re; [print(f'  {m.group(1):<12s} {m.group(2)}') for line in open('Makefile') if (m := re.match(r'^([a-zA-Z_-]+):.*##\s*(.*)', line))]"
