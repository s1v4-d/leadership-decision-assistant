"""RAG evaluation pipeline using RAGAS metrics."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

import structlog

if TYPE_CHECKING:
    from pathlib import Path

    from ragas import EvaluationDataset

logger = structlog.get_logger(__name__)


def _check_ragas_available() -> None:
    try:
        import ragas  # noqa: F401
    except ImportError:
        raise ImportError(  # noqa: B904
            "ragas is required for evaluation. Install with: uv sync --group eval"
        )


def load_golden_dataset(path: Path) -> list[dict[str, Any]]:
    """Load a golden Q&A dataset from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {path}")

    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    return cast("list[dict[str, Any]]", data)


def build_evaluation_dataset(samples: list[dict[str, Any]]) -> EvaluationDataset:
    """Convert raw sample dicts into a RAGAS EvaluationDataset."""
    _check_ragas_available()
    from ragas import EvaluationDataset as _EvaluationDataset
    from ragas import SingleTurnSample

    ragas_samples = [
        SingleTurnSample(
            user_input=s["user_input"],
            retrieved_contexts=s["retrieved_contexts"],
            response=s["response"],
            reference=s.get("reference", ""),
        )
        for s in samples
    ]
    return _EvaluationDataset(samples=ragas_samples)  # type: ignore[arg-type]


def get_default_rag_metrics() -> list[Any]:
    """Return the default set of RAGAS metrics for RAG evaluation."""
    _check_ragas_available()
    from ragas.metrics import Faithfulness, LLMContextRecall, ResponseRelevancy

    return [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextRecall(),
    ]


async def run_rag_evaluation(
    dataset: EvaluationDataset,
    metrics: list[Any],
) -> dict[str, float]:
    """Run RAGAS evaluation and return metric scores."""
    _check_ragas_available()
    from ragas import evaluate

    logger.info(
        "evaluation_starting",
        sample_count=len(dataset),
        metric_count=len(metrics),
    )

    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        raise_exceptions=False,
    )

    scores: dict[str, float] = {}
    for key, value in result.items():  # type: ignore[union-attr]
        if isinstance(value, int | float):
            scores[key] = float(value)

    logger.info("evaluation_complete", scores=scores)
    return scores
