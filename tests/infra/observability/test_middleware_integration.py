"""Async integration tests for ObservabilityMiddleware against a real ASGI app."""

import httpx
import pytest
from fastapi import FastAPI

from fundamentum.infra.observability.context import parse_traceparent
from fundamentum.infra.observability.metrics import (
    get_metrics_recorder,
    set_metrics_recorder,
)
from fundamentum.infra.observability.middleware import ObservabilityMiddleware


@pytest.fixture(autouse=True)
def reset_metrics_recorder():
    original = get_metrics_recorder()
    yield
    set_metrics_recorder(original)


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/ping")
    async def ping() -> dict:
        return {"pong": True}

    return app


@pytest.fixture
def client():
    app = build_app()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_response_gets_a_generated_trace_id(client):
    async with client as http_client:
        response = await http_client.get("/ping")

    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert len(response.headers["X-Trace-ID"]) == 5  # single generated segment


async def test_incoming_trace_id_is_incremented(client):
    async with client as http_client:
        response = await http_client.get("/ping", headers={"X-Trace-ID": "UICALL.START"})

    assert response.headers["X-Trace-ID"].startswith("UICALL.START.")


async def test_response_gets_a_valid_traceparent(client):
    async with client as http_client:
        response = await http_client.get("/ping")

    assert parse_traceparent(response.headers["traceparent"]) is not None


async def test_incoming_traceparent_trace_id_is_preserved(client):
    incoming = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"

    async with client as http_client:
        response = await http_client.get("/ping", headers={"traceparent": incoming})

    parsed = parse_traceparent(response.headers["traceparent"])
    assert parsed is not None
    trace_id, parent_id = parsed
    assert trace_id == "a" * 32
    assert parent_id != "b" * 16  # a fresh span-id is generated for this hop


async def test_middleware_records_inbound_metrics(client):
    events = []

    class RecordingRecorder:
        def record_request(self, **kwargs):
            events.append(kwargs)

    set_metrics_recorder(RecordingRecorder())

    async with client as http_client:
        await http_client.get("/ping")

    assert len(events) == 1
    assert events[0]["direction"] == "inbound"
    assert events[0]["status_code"] == 200
    assert events[0]["url_name"] == "ping"
