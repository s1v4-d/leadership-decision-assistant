"""Evaluation tests for RAG quality using RAGAS metrics and golden dataset."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from backend.src.evaluation.pipeline import (
    build_evaluation_dataset,
    get_default_rag_metrics,
    load_golden_dataset,
    run_rag_evaluation,
)

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

_ragas_available = importlib.util.find_spec("ragas") is not None
requires_ragas = pytest.mark.skipif(not _ragas_available, reason="ragas not installed — run 'uv sync --group eval'")


class TestLoadGoldenDataset:
    """Tests for loading the golden dataset from JSON."""

    def test_load_golden_dataset_returns_list_of_samples(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)

        assert isinstance(samples, list)
        assert len(samples) == 5

    def test_load_golden_dataset_sample_has_required_fields(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        sample = samples[0]

        assert "user_input" in sample
        assert "retrieved_contexts" in sample
        assert "response" in sample
        assert "reference" in sample

    def test_load_golden_dataset_contexts_are_lists(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)

        for sample in samples:
            assert isinstance(sample["retrieved_contexts"], list)

    def test_load_golden_dataset_raises_for_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_golden_dataset(Path("/nonexistent/path.json"))

    def test_load_golden_dataset_raises_for_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_golden_dataset(bad_file)


@requires_ragas
class TestBuildEvaluationDataset:
    """Tests for building RAGAS EvaluationDataset from raw samples."""

    def test_build_evaluation_dataset_returns_correct_type(self) -> None:
        from ragas import EvaluationDataset

        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)

        assert isinstance(dataset, EvaluationDataset)

    def test_build_evaluation_dataset_has_correct_length(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)

        assert len(dataset) == 5

    def test_build_evaluation_dataset_preserves_user_input(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)

        first_sample = dataset[0]
        assert first_sample.user_input == samples[0]["user_input"]

    def test_build_evaluation_dataset_preserves_contexts(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)

        first_sample = dataset[0]
        assert first_sample.retrieved_contexts == samples[0]["retrieved_contexts"]

    def test_build_evaluation_dataset_empty_list_returns_empty(self) -> None:
        dataset = build_evaluation_dataset([])

        assert len(dataset) == 0


@requires_ragas
class TestGetDefaultRagMetrics:
    """Tests for default metric configuration."""

    def test_get_default_rag_metrics_returns_non_empty_list(self) -> None:
        metrics = get_default_rag_metrics()

        assert len(metrics) > 0

    def test_get_default_rag_metrics_contains_faithfulness(self) -> None:
        metrics = get_default_rag_metrics()
        metric_names = [type(m).__name__ for m in metrics]

        assert "Faithfulness" in metric_names

    def test_get_default_rag_metrics_contains_response_relevancy(self) -> None:
        metrics = get_default_rag_metrics()
        metric_names = [type(m).__name__ for m in metrics]

        assert "ResponseRelevancy" in metric_names


@requires_ragas
@pytest.mark.evaluation
class TestRunRagEvaluation:
    """Tests for running RAGAS evaluation (requires LLM API key)."""

    @pytest.mark.asyncio
    async def test_run_rag_evaluation_returns_results_dict(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        assert isinstance(results, dict)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_run_rag_evaluation_scores_between_zero_and_one(self) -> None:
        samples = load_golden_dataset(GOLDEN_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        for metric_name, score in results.items():
            assert 0.0 <= score <= 1.0, f"{metric_name} score {score} out of range"
