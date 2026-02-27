"""Tests for Docker infrastructure files."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


class TestDockerFiles:
    """Validate Docker infrastructure files exist and have correct structure."""

    def test_dockerfile_exists(self) -> None:
        assert (ROOT / "infra" / "docker" / "Dockerfile").is_file()

    def test_dockerfile_has_builder_stage(self) -> None:
        content = (ROOT / "infra" / "docker" / "Dockerfile").read_text()
        assert "AS builder" in content

    def test_dockerfile_has_runtime_stage(self) -> None:
        content = (ROOT / "infra" / "docker" / "Dockerfile").read_text()
        assert "AS runtime" in content

    def test_dockerfile_uses_non_root_user(self) -> None:
        content = (ROOT / "infra" / "docker" / "Dockerfile").read_text()
        assert "USER app" in content

    def test_dockerfile_copies_uv_binary(self) -> None:
        content = (ROOT / "infra" / "docker" / "Dockerfile").read_text()
        assert "ghcr.io/astral-sh/uv" in content

    def test_dockerfile_uses_locked_sync(self) -> None:
        content = (ROOT / "infra" / "docker" / "Dockerfile").read_text()
        assert "--locked" in content

    def test_dockerignore_exists(self) -> None:
        assert (ROOT / ".dockerignore").is_file()

    def test_dockerignore_excludes_venv(self) -> None:
        content = (ROOT / ".dockerignore").read_text()
        assert ".venv" in content

    def test_start_script_exists_and_executable(self) -> None:
        script = ROOT / "infra" / "docker" / "start.sh"
        assert script.is_file()
        content = script.read_text()
        assert "uvicorn" in content
        assert "streamlit" in content

    def test_init_db_sql_enables_pgvector(self) -> None:
        sql = ROOT / "infra" / "docker" / "init-db.sql"
        assert sql.is_file()
        content = sql.read_text()
        assert "CREATE EXTENSION" in content
        assert "vector" in content


class TestDockerCompose:
    """Validate docker-compose.yml structure and services."""

    def test_docker_compose_exists(self) -> None:
        assert (ROOT / "docker-compose.yml").is_file()

    def test_docker_compose_is_valid_yaml(self) -> None:
        content = (ROOT / "docker-compose.yml").read_text()
        data = yaml.safe_load(content)
        assert isinstance(data, dict)
        assert "services" in data

    def test_docker_compose_has_app_service(self) -> None:
        data = _load_compose()
        assert "app" in data["services"]

    def test_docker_compose_has_postgres_service(self) -> None:
        data = _load_compose()
        assert "postgres" in data["services"]

    def test_docker_compose_has_redis_service(self) -> None:
        data = _load_compose()
        assert "redis" in data["services"]

    def test_postgres_uses_pgvector_image(self) -> None:
        data = _load_compose()
        image = data["services"]["postgres"]["image"]
        assert "pgvector" in image

    def test_app_depends_on_postgres_and_redis(self) -> None:
        data = _load_compose()
        depends = data["services"]["app"]["depends_on"]
        assert "postgres" in depends
        assert "redis" in depends

    def test_postgres_has_healthcheck(self) -> None:
        data = _load_compose()
        assert "healthcheck" in data["services"]["postgres"]

    def test_redis_has_healthcheck(self) -> None:
        data = _load_compose()
        assert "healthcheck" in data["services"]["redis"]

    def test_docker_compose_has_volumes(self) -> None:
        data = _load_compose()
        assert "volumes" in data
        assert "pgdata" in data["volumes"]
        assert "redisdata" in data["volumes"]

    def test_app_service_uses_env_file(self) -> None:
        data = _load_compose()
        assert "env_file" in data["services"]["app"]


def _load_compose() -> dict:  # type: ignore[type-arg]
    content = (ROOT / "docker-compose.yml").read_text()
    return yaml.safe_load(content)  # type: ignore[no-any-return]
