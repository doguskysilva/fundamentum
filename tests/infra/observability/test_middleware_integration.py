"""Async integration tests for ObservabilityMiddleware."""

import httpx
import pytest
from fastapi import FastAPI

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


async def test_middleware_does_not_emit_legacy_trace_headers(client):
    async with client as http_client:
        response = await http_client.get("/ping")

    assert response.status_code == 200
    assert "X-Trace-ID" not in response.headers
    assert "traceparent" not in response.headers


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
