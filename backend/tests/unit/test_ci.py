"""Tests for GitHub Actions CI workflow configuration."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_workflow() -> dict:
    return yaml.safe_load(CI_PATH.read_text())


class TestCIWorkflowExists:
    def test_ci_workflow_file_exists(self):
        assert CI_PATH.exists()

    def test_ci_workflow_is_valid_yaml(self):
        workflow = _load_ci_workflow()
        assert isinstance(workflow, dict)


class TestCITriggers:
    def test_triggers_on_push_to_main(self):
        workflow = _load_ci_workflow()
        assert "main" in workflow[True]["push"]["branches"]

    def test_triggers_on_pull_request_to_main(self):
        workflow = _load_ci_workflow()
        assert "main" in workflow[True]["pull_request"]["branches"]

    def test_push_has_path_filters(self):
        workflow = _load_ci_workflow()
        paths = workflow[True]["push"]["paths"]
        assert "backend/**" in paths
        assert "ui/**" in paths

    def test_pull_request_has_path_filters(self):
        workflow = _load_ci_workflow()
        paths = workflow[True]["pull_request"]["paths"]
        assert "backend/**" in paths
        assert "ui/**" in paths


class TestCIJobs:
    def test_has_lint_job(self):
        workflow = _load_ci_workflow()
        assert "lint" in workflow["jobs"]

    def test_has_typecheck_job(self):
        workflow = _load_ci_workflow()
        assert "typecheck" in workflow["jobs"]

    def test_has_test_job(self):
        workflow = _load_ci_workflow()
        assert "test" in workflow["jobs"]

    def test_has_docker_build_job(self):
        workflow = _load_ci_workflow()
        assert "docker-build" in workflow["jobs"]


class TestCILintJob:
    def test_lint_runs_on_ubuntu(self):
        workflow = _load_ci_workflow()
        assert workflow["jobs"]["lint"]["runs-on"] == "ubuntu-latest"

    def test_lint_uses_uv_setup(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["lint"]["steps"]
        step_uses = [s.get("uses", "") for s in steps]
        assert any("astral-sh/setup-uv" in u for u in step_uses)

    def test_lint_runs_ruff_check(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["lint"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert any("ruff check" in r for r in step_runs)

    def test_lint_runs_ruff_format_check(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["lint"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert any("ruff format --check" in r for r in step_runs)


class TestCITypecheckJob:
    def test_typecheck_runs_mypy(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["typecheck"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert any("mypy" in r for r in step_runs)


class TestCITestJob:
    def test_test_runs_pytest(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["test"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert any("pytest" in r for r in step_runs)


class TestCIDockerBuildJob:
    def test_docker_build_depends_on_quality_jobs(self):
        workflow = _load_ci_workflow()
        needs = workflow["jobs"]["docker-build"]["needs"]
        assert "lint" in needs
        assert "typecheck" in needs
        assert "test" in needs

    def test_docker_build_runs_docker_build(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["docker-build"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert any("docker build" in r for r in step_runs)

    def test_docker_build_does_not_push(self):
        workflow = _load_ci_workflow()
        steps = workflow["jobs"]["docker-build"]["steps"]
        step_runs = [s.get("run", "") for s in steps]
        assert not any("docker push" in r for r in step_runs)


class TestCIUvCaching:
    def test_uv_setup_enables_caching(self):
        workflow = _load_ci_workflow()
        for job in workflow["jobs"].values():
            steps = job.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "astral-sh/setup-uv" in uses:
                    assert step.get("with", {}).get("enable-cache") is True
                    return
        raise AssertionError("No astral-sh/setup-uv step found with enable-cache")

    def test_uv_sync_uses_locked_flag(self):
        workflow = _load_ci_workflow()
        for job in workflow["jobs"].values():
            steps = job.get("steps", [])
            for step in steps:
                run_cmd = step.get("run", "")
                if "uv sync" in run_cmd:
                    assert "--locked" in run_cmd
                    return
        raise AssertionError("No uv sync --locked step found")
