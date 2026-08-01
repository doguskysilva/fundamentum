"""OpenTelemetry tracing integration tests.

These tests run when the optional ``otel`` extra is installed. The exporter
is replaced with an in-memory exporter so no collector is needed.
"""

import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.instrumentation.fastapi")
pytest.importorskip("opentelemetry.instrumentation.httpx")
pytest.importorskip("opentelemetry.instrumentation.logging")

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind

from fundamentum.infra.http import (
    EndpointRegistry,
    HttpMethod,
    ServiceClient,
    ServiceEndpoint,
)
from fundamentum.infra.observability import (
    ObservabilityMiddleware,
    tracing as tracing_module,
)
from fundamentum.infra.observability.logging import (
    ContextFilter,
    setup_logging,
)
from fundamentum.infra.settings import ServiceRegistry


class DownstreamResponse(BaseModel):
    value: str


class Settings:
    service_name = "gateway"
    service_version = "test"
    environment = "test"
    log_level = "INFO"
    enable_json_logging = True


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def tracing_setup(monkeypatch):
    exporter = InMemorySpanExporter()
    monkeypatch.setattr(tracing_module, "OTLPSpanExporter", lambda: exporter)
    monkeypatch.setattr(tracing_module, "BatchSpanProcessor", SimpleSpanProcessor)
    yield exporter
    tracing_module.HTTPXClientInstrumentor().uninstrument()
    tracing_module.LoggingInstrumentor().uninstrument()


async def test_setup_tracing_creates_parented_http_spans_and_correlated_logs(tracing_setup):
    downstream = FastAPI()

    @downstream.get("/value")
    async def value() -> DownstreamResponse:
        return DownstreamResponse(value="ok")

    service_registry = ServiceRegistry(SimpleNamespace(downstream_base_url="http://downstream"))
    endpoint_registry = EndpointRegistry()
    endpoint_registry.register(
        "downstream.value",
        ServiceEndpoint(
            service="downstream",
            path="/value",
            method=HttpMethod.GET,
            request_model=None,
            response_model=DownstreamResponse,
        ),
    )
    service_client = ServiceClient(
        service_registry,
        endpoint_registry,
        transport=httpx.ASGITransport(app=downstream),
    )

    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/proxy")
    async def proxy() -> dict[str, str]:
        logging.getLogger("test.route").info("proxy request")
        result = await service_client.get("downstream.value")
        return {"value": result.value}

    setup_logging(Settings())
    log_handler = ListHandler()
    log_handler.addFilter(ContextFilter(Settings()))
    logging.getLogger().addHandler(log_handler)
    tracing_module.setup_tracing(app, Settings())
    tracing_module.HTTPXClientInstrumentor.instrument_client(service_client._client)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as http_client:
        response = await http_client.get("/proxy")
    tracing_module.HTTPXClientInstrumentor.uninstrument_client(service_client._client)
    await service_client.aclose()

    assert response.status_code == 200
    spans = tracing_setup.get_finished_spans()
    server_span = next(span for span in spans if span.kind == SpanKind.SERVER)
    client_span = next(span for span in spans if span.kind == SpanKind.CLIENT)

    assert server_span.context.trace_id == client_span.context.trace_id
    assert client_span.parent is not None
    assert client_span.parent.span_id == server_span.context.span_id

    correlated = next(record for record in log_handler.records if record.msg == "proxy request")
    assert correlated.trace_id == format(server_span.context.trace_id, "032x")
    assert correlated.span_id == format(server_span.context.span_id, "016x")

    json_log = json.loads(logging.getLogger().handlers[0].formatter.format(correlated))
    assert json_log["trace_id"] == correlated.trace_id
    assert json_log["span_id"] == correlated.span_id
