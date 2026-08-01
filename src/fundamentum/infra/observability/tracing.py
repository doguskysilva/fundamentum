"""Optional OpenTelemetry setup for FastAPI services."""

from fastapi import FastAPI

from fundamentum.infra.settings.protocols import SettingsProtocol

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import (
        FastAPIInstrumentor,
    )
    from opentelemetry.instrumentation.httpx import (
        HTTPXClientInstrumentor,
    )
    from opentelemetry.instrumentation.logging import (
        LoggingInstrumentor,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
    )
except ImportError as exc:  # pragma: no cover - depends on optional extra
    _OTEL_IMPORT_ERROR: ImportError | None = exc
else:
    _OTEL_IMPORT_ERROR = None


def setup_tracing(app: FastAPI, settings: SettingsProtocol) -> None:
    """Configure OpenTelemetry tracing for a FastAPI service.

    The OTel dependencies are optional. Install them with
    ``pip install fundamentum[otel]`` before calling this function. The OTLP
    exporter reads its target and authentication settings from the standard
    ``OTEL_*`` environment variables.
    """
    if _OTEL_IMPORT_ERROR is not None:
        raise ImportError(
            "OpenTelemetry tracing requires the optional dependencies; install "
            "them with `pip install fundamentum[otel]`."
        ) from _OTEL_IMPORT_ERROR

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": settings.service_version,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=False)
