"""Tests for the liveness/readiness router helpers."""

import httpx
import pytest
from fastapi import FastAPI

from fundamentum.infra.health import create_health_router


def build_app(checks=None, **kwargs) -> FastAPI:
    app = FastAPI()
    app.include_router(create_health_router(checks=checks, **kwargs))
    return app


@pytest.fixture
async def client():
    async def _make(app: FastAPI) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    return _make


async def test_liveness_is_always_ok_and_ignores_checks(client):
    async def always_fails() -> bool:
        return False

    app = build_app(checks={"db": always_fails})
    async with await client(app) as http_client:
        response = await http_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok_with_no_checks(client):
    app = build_app()
    async with await client(app) as http_client:
        response = await http_client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


async def test_readiness_aggregates_sync_and_async_checks(client):
    def sync_ok() -> bool:
        return True

    async def async_ok() -> bool:
        return True

    app = build_app(checks={"cache": sync_ok, "db": async_ok})
    async with await client(app) as http_client:
        response = await http_client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"cache": "ok", "db": "ok"}}


async def test_readiness_degrades_when_a_check_fails(client):
    def healthy() -> bool:
        return True

    def unhealthy() -> bool:
        return False

    app = build_app(checks={"cache": healthy, "db": unhealthy})
    async with await client(app) as http_client:
        response = await http_client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": {"cache": "ok", "db": "error"}}


async def test_readiness_treats_raised_exception_as_unhealthy(client):
    def broken() -> bool:
        raise RuntimeError("connection refused")

    app = build_app(checks={"db": broken})
    async with await client(app) as http_client:
        response = await http_client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"]["db"] == "error"


async def test_custom_paths(client):
    app = build_app(liveness_path="/live", readiness_path="/ready")
    async with await client(app) as http_client:
        liveness_response = await http_client.get("/live")
        readiness_response = await http_client.get("/ready")

    assert liveness_response.status_code == 200
    assert readiness_response.status_code == 200


async def test_health_routes_excluded_from_openapi_schema():
    app = build_app(checks={"db": lambda: True})

    schema = app.openapi()

    assert "/healthz" not in schema["paths"]
    assert "/readyz" not in schema["paths"]
