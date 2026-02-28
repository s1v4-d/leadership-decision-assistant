"""OpenTelemetry and Prometheus observability setup."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

if TYPE_CHECKING:
    from fastapi import FastAPI

    from backend.src.core.config import Settings

_metrics: AppMetrics | None = None


@dataclass
class AppMetrics:
    """Application-level OpenTelemetry metric instruments."""

    query_counter: metrics.Counter = field(init=False)
    query_latency: metrics.Histogram = field(init=False)
    ingestion_counter: metrics.Counter = field(init=False)
    ingestion_documents: metrics.Counter = field(init=False)
    active_queries: metrics.UpDownCounter = field(init=False)
    cache_hits: metrics.Counter = field(init=False)

    def __post_init__(self) -> None:  # noqa: D105
        meter = metrics.get_meter("leadership-insight-agent")
        self.query_counter = meter.create_counter(
            name="app.query.count",
            unit="1",
            description="Total number of queries processed",
        )
        self.query_latency = meter.create_histogram(
            name="app.query.latency",
            unit="s",
            description="Query processing latency in seconds",
        )
        self.ingestion_counter = meter.create_counter(
            name="app.ingestion.count",
            unit="1",
            description="Total number of ingestion runs",
        )
        self.ingestion_documents = meter.create_counter(
            name="app.ingestion.documents",
            unit="1",
            description="Total number of documents ingested",
        )
        self.active_queries = meter.create_up_down_counter(
            name="app.query.active",
            unit="1",
            description="Number of queries currently being processed",
        )
        self.cache_hits = meter.create_counter(
            name="app.query.cache_hits",
            unit="1",
            description="Total number of cache hits for queries",
        )


APP_METRICS: AppMetrics | None = None


def configure_telemetry(settings: Settings) -> None:
    """Initialize OpenTelemetry tracing and metrics if enabled."""
    global APP_METRICS  # noqa: PLW0603

    if not settings.otel_enabled:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})

    tracer_provider = TracerProvider(resource=resource)
    if settings.otel_exporter_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint))
        )
    else:
        tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[prometheus_reader])
    metrics.set_meter_provider(meter_provider)

    APP_METRICS = AppMetrics()


def shutdown_telemetry() -> None:
    """Flush and shut down telemetry providers."""
    global APP_METRICS  # noqa: PLW0603

    provider = trace.get_tracer_provider()
    if isinstance(provider, TracerProvider):
        provider.shutdown()
    trace.set_tracer_provider(trace.NoOpTracerProvider())

    meter_prov = metrics.get_meter_provider()
    if isinstance(meter_prov, MeterProvider):
        meter_prov.shutdown()
    metrics.set_meter_provider(metrics.NoOpMeterProvider())

    APP_METRICS = None


def instrument_fastapi(app: FastAPI, settings: Settings) -> None:
    """Instrument a FastAPI app with OpenTelemetry auto-instrumentation."""
    if not settings.otel_enabled:
        return
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,ready,metrics",
    )


def get_metrics() -> AppMetrics | None:
    """Return the current application metrics instance, or None if not initialized."""
    return APP_METRICS


def record_query(*, latency_seconds: float, status: str, cached: bool) -> None:
    """Record metrics for a completed query."""
    m = get_metrics()
    if m is None:
        return
    attributes = {"status": status}
    m.query_counter.add(1, attributes)
    m.query_latency.record(latency_seconds, attributes)
    if cached:
        m.cache_hits.add(1)


def record_ingestion(*, document_count: int, node_count: int, status: str) -> None:
    """Record metrics for a completed ingestion run."""
    m = get_metrics()
    if m is None:
        return
    attributes = {"status": status}
    m.ingestion_counter.add(1, attributes)
    m.ingestion_documents.add(document_count + node_count, attributes)
