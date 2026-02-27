"""Input sanitization, PII masking, and prompt injection detection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

logger = structlog.get_logger(__name__)

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?(prior|previous)",
    r"(reveal|show|print|output)\s+(your\s+)?system\s+prompt",
    r"you\s+are\s+now\s+",
    r"pretend\s+you\s+are\s+",
    r"act\s+as\s+(an?\s+)?",
    r"forget\s+everything",
    r"new\s+instructions:",
    r"override\s+(previous|prior|all)",
]

_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PromptInjectionError(Exception):
    """Raised when a prompt injection attempt is detected."""


@dataclass
class OutputValidation:
    """Result of output validation checks."""

    answer: str
    grounded: bool


def sanitize_query(text: str, max_length: int) -> str:
    """Remove control chars, normalize whitespace and unicode, truncate."""
    text = _CONTROL_CHAR_PATTERN.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def detect_prompt_injection(text: str, blocked_patterns: list[str]) -> bool:
    """Check if text contains prompt injection patterns."""
    lower_text = text.lower()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, lower_text):
            return True
    return any(custom.lower() in lower_text for custom in blocked_patterns)


def parse_blocked_patterns(raw: str) -> list[str]:
    """Parse comma-separated blocked patterns string into a list."""
    if not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _get_pii_analyzer() -> AnalyzerEngine | None:
    """Lazy-load Presidio AnalyzerEngine, returning None if unavailable."""
    try:
        from presidio_analyzer import AnalyzerEngine

        return AnalyzerEngine()
    except Exception:
        logger.warning("presidio_analyzer_unavailable")
        return None


def _get_pii_anonymizer() -> AnonymizerEngine | None:
    """Lazy-load Presidio AnonymizerEngine, returning None if unavailable."""
    try:
        from presidio_anonymizer import AnonymizerEngine

        return AnonymizerEngine()  # type: ignore[no-untyped-call]
    except Exception:
        logger.warning("presidio_anonymizer_unavailable")
        return None


def mask_pii(text: str, *, enable: bool) -> str:
    """Mask PII entities in text using Presidio. Returns original on failure."""
    if not enable:
        return text

    analyzer = _get_pii_analyzer()
    if analyzer is None:
        return text

    anonymizer = _get_pii_anonymizer()
    if anonymizer is None:
        return text

    try:
        results = analyzer.analyze(text=text, language="en")
        if not results:
            return text
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)  # type: ignore[arg-type]
        return str(anonymized.text)
    except Exception:
        logger.warning("pii_masking_failed")
        return text


def validate_output(
    answer: str,
    source_count: int,
    *,
    enable_pii_masking: bool = False,
) -> OutputValidation:
    """Validate output: check grounding, optionally mask PII."""
    cleaned = mask_pii(answer, enable=enable_pii_masking)
    grounded = source_count > 0
    return OutputValidation(answer=cleaned, grounded=grounded)
