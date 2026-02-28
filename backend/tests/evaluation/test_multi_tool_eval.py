"""Evaluation tests for multi-tool agent using RAGAS metrics.

Extends the single-tool RAG evaluation with a golden dataset that includes
both document-grounded (RAG) and structured data (SQL) response examples.
Validates faithfulness and relevancy across the combined pipeline.
"""

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

MULTI_TOOL_DATASET_PATH = Path(__file__).parent / "multi_tool_golden_dataset.json"

_ragas_available = importlib.util.find_spec("ragas") is not None
requires_ragas = pytest.mark.skipif(not _ragas_available, reason="ragas not installed — run 'uv sync --group eval'")


class TestMultiToolGoldenDataset:
    """Tests for loading and validating the multi-tool golden dataset."""

    def test_load_multi_tool_dataset_returns_list(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        assert isinstance(samples, list)
        assert len(samples) == 5

    def test_samples_have_required_fields(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        for sample in samples:
            assert "user_input" in sample
            assert "retrieved_contexts" in sample
            assert "response" in sample
            assert "reference" in sample

    def test_samples_include_sql_context(self) -> None:
        """Multi-tool samples should include SQL-derived data in contexts."""
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        sql_contexts_found = any(any("SQL Result" in ctx for ctx in sample["retrieved_contexts"]) for sample in samples)
        assert sql_contexts_found

    def test_samples_include_document_context(self) -> None:
        """Multi-tool samples should also include document-derived contexts."""
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        doc_contexts_found = any(
            any("SQL Result" not in ctx for ctx in sample["retrieved_contexts"]) for sample in samples
        )
        assert doc_contexts_found

    def test_sample_contexts_are_lists(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        for sample in samples:
            assert isinstance(sample["retrieved_contexts"], list)


@requires_ragas
class TestMultiToolBuildDataset:
    """Tests for building RAGAS EvaluationDataset from multi-tool samples."""

    def test_build_multi_tool_dataset_returns_correct_type(self) -> None:
        from ragas import EvaluationDataset

        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        assert isinstance(dataset, EvaluationDataset)

    def test_build_multi_tool_dataset_has_correct_length(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        assert len(dataset) == 5

    def test_multi_tool_dataset_preserves_sql_contexts(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        first_sample = dataset[0]
        has_sql = any("SQL Result" in ctx for ctx in first_sample.retrieved_contexts)
        assert has_sql


@requires_ragas
@pytest.mark.evaluation
class TestMultiToolRagasEvaluation:
    """Run RAGAS evaluation on multi-tool agent golden dataset.

    These tests require an LLM API key and will be skipped in CI unless
    evaluation credentials are configured.
    """

    @pytest.mark.asyncio
    async def test_multi_tool_evaluation_returns_scores(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        assert isinstance(results, dict)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_multi_tool_faithfulness_above_threshold(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        if "faithfulness" in results:
            assert results["faithfulness"] >= 0.7, f"Faithfulness {results['faithfulness']:.2f} below 0.7 threshold"

    @pytest.mark.asyncio
    async def test_multi_tool_relevancy_above_threshold(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        if "answer_relevancy" in results:
            assert results["answer_relevancy"] >= 0.7, (
                f"Relevancy {results['answer_relevancy']:.2f} below 0.7 threshold"
            )

    @pytest.mark.asyncio
    async def test_multi_tool_scores_between_zero_and_one(self) -> None:
        samples = load_golden_dataset(MULTI_TOOL_DATASET_PATH)
        dataset = build_evaluation_dataset(samples)
        metrics = get_default_rag_metrics()

        results = await run_rag_evaluation(dataset, metrics)

        for metric_name, score in results.items():
            assert 0.0 <= score <= 1.0, f"{metric_name} score {score} out of range"
