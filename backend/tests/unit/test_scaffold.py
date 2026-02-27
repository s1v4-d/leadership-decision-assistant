"""Scaffold validation tests to verify project structure is correct."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _package_dirs() -> list[str]:
    return [
        "backend/src",
        "backend/src/api",
        "backend/src/agents",
        "backend/src/core",
        "backend/src/ingestion",
        "backend/src/models",
        "backend/src/tools",
        "backend/tests",
        "backend/tests/unit",
        "backend/tests/integration",
        "backend/tests/evaluation",
        "ui",
        "ui/components",
    ]


@pytest.mark.unit
class TestProjectStructure:
    def test_all_python_packages_have_init_files(self) -> None:
        for package_dir in _package_dirs():
            init_file = PROJECT_ROOT / package_dir / "__init__.py"
            assert init_file.exists(), f"Missing __init__.py in {package_dir}"

    def test_root_config_files_exist(self) -> None:
        expected_files = [
            "pyproject.toml",
            ".python-version",
            "Makefile",
            ".pre-commit-config.yaml",
            ".env.example",
            ".gitignore",
            "LICENSE",
            "README.md",
        ]
        for filename in expected_files:
            assert (PROJECT_ROOT / filename).exists(), f"Missing root file: {filename}"

    def test_pyproject_toml_has_required_sections(self) -> None:
        content = (PROJECT_ROOT / "pyproject.toml").read_text()
        required_sections = [
            "[project]",
            "[build-system]",
            "[tool.ruff]",
            "[tool.mypy]",
            "[tool.pytest.ini_options]",
        ]
        for section in required_sections:
            assert section in content, f"Missing section {section} in pyproject.toml"

    def test_backend_src_has_py_typed_marker(self) -> None:
        assert (PROJECT_ROOT / "backend/src/py.typed").exists()

    def test_source_modules_exist(self) -> None:
        expected_modules = [
            "backend/src/core/config.py",
            "backend/src/core/llm_provider.py",
            "backend/src/core/log.py",
            "backend/src/core/security.py",
            "backend/src/core/telemetry.py",
            "backend/src/api/main.py",
            "backend/src/api/routes.py",
            "backend/src/api/dependencies.py",
            "backend/src/agents/leadership_agent.py",
            "backend/src/agents/prompts.py",
            "backend/src/ingestion/pipeline.py",
            "backend/src/ingestion/parsers.py",
            "backend/src/ingestion/chunking.py",
            "backend/src/models/schemas.py",
            "backend/src/models/domain.py",
            "backend/src/tools/rag_tool.py",
            "backend/src/tools/search_tool.py",
            "ui/app.py",
        ]
        for module in expected_modules:
            assert (PROJECT_ROOT / module).exists(), f"Missing module: {module}"
