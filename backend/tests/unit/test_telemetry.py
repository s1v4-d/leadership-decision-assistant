"""Tests for OpenTelemetry and Prometheus observability setup."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import structlog
from opentelemetry import metrics, trace
from opentelemetry.metrics import _internal as metrics_internal
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.util._once import Once

from backend.src.core.config import Settings
from backend.src.core.log import add_trace_context, configure_logging
from backend.src.core.telemetry import (
    configure_telemetry,
    get_metrics,
    record_ingestion,
    record_query,
    shutdown_telemetry,
)


def _reset_otel_global_state() -> None:
    """Reset OTel global provider locks so each test gets a clean slate."""
    trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]  # noqa: SLF001
    trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    metrics_internal._METER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]  # noqa: SLF001
    metrics_internal._METER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001


@pytest.fixture(autouse=True)
def _isolate_otel_state() -> Any:
    """Ensure each test starts with fresh OTel global state."""
    _reset_otel_global_state()
    yield
    shutdown_telemetry()
    _reset_otel_global_state()


class TestConfigureTelemetry:
    """Tests for telemetry initialization."""

    def test_sets_tracer_provider(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

    def test_sets_meter_provider(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        provider = metrics.get_meter_provider()
        assert isinstance(provider, MeterProvider)

    def test_disabled_does_not_create_metrics(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=False)
        configure_telemetry(settings)
        assert get_metrics() is None

    def test_creates_app_metrics(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        m = get_metrics()
        assert m is not None
        assert m.query_counter is not None
        assert m.query_latency is not None
        assert m.ingestion_counter is not None
        assert m.active_queries is not None


class TestShutdownTelemetry:
    """Tests for telemetry shutdown."""

    def test_shutdown_clears_app_metrics(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        assert get_metrics() is not None
        shutdown_telemetry()
        assert get_metrics() is None

    def test_shutdown_when_not_initialized_is_safe(self) -> None:
        shutdown_telemetry()


class TestRecordQuery:
    """Tests for query metric recording."""

    def test_records_query_increments_counter(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        m = get_metrics()
        assert m is not None
        with patch.object(m, "query_counter") as mock_counter, patch.object(m, "query_latency") as mock_latency:
            record_query(latency_seconds=0.5, status="success", cached=False)
            mock_counter.add.assert_called_once_with(1, {"status": "success"})
            mock_latency.record.assert_called_once_with(0.5, {"status": "success"})

    def test_records_cached_query_increments_cache_hits(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        m = get_metrics()
        assert m is not None
        with (
            patch.object(m, "cache_hits") as mock_cache,
            patch.object(m, "query_counter"),
            patch.object(m, "query_latency"),
        ):
            record_query(latency_seconds=0.1, status="success", cached=True)
            mock_cache.add.assert_called_once_with(1)

    def test_noop_when_disabled(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=False)
        configure_telemetry(settings)
        record_query(latency_seconds=0.5, status="success", cached=False)


class TestRecordIngestion:
    """Tests for ingestion metric recording."""

    def test_records_ingestion_increments_counters(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        m = get_metrics()
        assert m is not None
        with patch.object(m, "ingestion_counter") as mock_counter, patch.object(m, "ingestion_documents") as mock_docs:
            record_ingestion(document_count=5, node_count=25, status="success")
            mock_counter.add.assert_called_once_with(1, {"status": "success"})
            mock_docs.add.assert_called_once_with(30, {"status": "success"})

    def test_noop_when_disabled(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=False)
        configure_telemetry(settings)
        record_ingestion(document_count=5, node_count=25, status="success")


class TestGetMetrics:
    """Tests for metrics accessor."""

    def test_returns_none_when_not_initialized(self) -> None:
        assert get_metrics() is None

    def test_returns_metrics_when_initialized(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        assert get_metrics() is not None


class TestAddTraceContext:
    """Tests for structlog trace context processor."""

    def test_adds_trace_and_span_id_when_active(self) -> None:
        settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        configure_telemetry(settings)
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            event_dict: dict[str, Any] = {}
            result = add_trace_context(None, "info", event_dict)
            assert "trace_id" in result
            assert "span_id" in result
            assert result["trace_id"] != "0" * 32

    def test_adds_zero_ids_when_no_active_span(self) -> None:
        event_dict: dict[str, Any] = {}
        result = add_trace_context(None, "info", event_dict)
        assert result["trace_id"] == "0" * 32
        assert result["span_id"] == "0" * 16


class TestInstrumentApp:
    """Tests for FastAPI auto-instrumentation."""

    def test_instrument_app_called_when_enabled(self) -> None:
        otel_settings = Settings(_env_file=None, otel_enabled=True, otel_service_name="test-svc")
        with (
            patch("backend.src.core.telemetry.FastAPIInstrumentor") as mock_instrumentor,
            patch("backend.src.api.main.get_settings", return_value=otel_settings),
        ):
            configure_telemetry(otel_settings)
            from backend.src.api.main import create_app

            create_app()
            mock_instrumentor.instrument_app.assert_called_once()


class TestLoggingWithTraceContext:
    """Tests for structlog integration with trace context."""

    def test_configure_logging_includes_trace_processor(self) -> None:
        configure_logging(log_level="INFO", log_format="json")
        config = structlog.get_config()
        processor_names = [p.__name__ if hasattr(p, "__name__") else str(p) for p in config["processors"]]
        assert any("add_trace_context" in name for name in processor_names)
