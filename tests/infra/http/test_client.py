"""Tests for the async ServiceClient."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.models import (
	HttpMethod,
	ServiceEndpoint,
	ServiceError,
	ServiceNotFoundError,
	ServiceTimeoutError,
	ServiceUnavailableError,
)
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.observability.context import clear_trace_id, set_trace_id
from fundamentum.infra.settings.registry import ServiceRegistry


class ExampleResponse(BaseModel):
	id: str
	name: str


def run(coro):
	return asyncio.run(coro)


@pytest.fixture
def service_registry():
	settings = SimpleNamespace(census_base_url="https://census.test")
	return ServiceRegistry(settings)


@pytest.fixture
def endpoint_registry():
	return EndpointRegistry()


@pytest.fixture
def client_with_registry(service_registry, endpoint_registry):
	client = ServiceClient(service_registry, endpoint_registry, timeout=0.5)
	return client, endpoint_registry


@pytest.fixture(autouse=True)
def reset_trace_context():
	clear_trace_id()
	yield
	clear_trace_id()


@pytest.fixture
def async_client_stub(monkeypatch):
	responses: dict[str, httpx.Response | Exception] = {}

	class DummyAsyncClient:
		def __init__(self, *args, **kwargs):  # pragma: no cover - simple stub
			pass

		async def __aenter__(self):
			return self

		async def __aexit__(self, exc_type, exc, tb):
			return False

		async def _call(self, method: str, *args, **kwargs):
			if method not in responses:
				raise AssertionError(f"No stubbed response for {method}")
			payload = responses[method]
			if isinstance(payload, Exception):
				raise payload
			return payload

		async def get(self, *args, **kwargs):
			return await self._call("GET", *args, **kwargs)

		async def post(self, *args, **kwargs):
			return await self._call("POST", *args, **kwargs)

		async def put(self, *args, **kwargs):
			return await self._call("PUT", *args, **kwargs)

		async def delete(self, *args, **kwargs):
			return await self._call("DELETE", *args, **kwargs)

		async def patch(self, *args, **kwargs):
			return await self._call("PATCH", *args, **kwargs)

	monkeypatch.setattr(
		"fundamentum.infra.http.client.httpx.AsyncClient",
		lambda *args, **kwargs: DummyAsyncClient(),
	)

	return responses


def register_endpoint(registry: EndpointRegistry, method: HttpMethod) -> str:
	key = "census.get_user"
	registry.register(
		key,
		ServiceEndpoint(
			service="census",
			path="/api/customers/{customer_id}",
			method=method,
			request_model=None,
			response_model=ExampleResponse,
		),
	)
	return key


def make_response(status_code: int, method: str = "GET", json_data: dict | None = None) -> httpx.Response:
	return httpx.Response(
		status_code=status_code,
		request=httpx.Request(method, "https://census.test/api/customers/123"),
		json=json_data or {"id": "123", "name": "Ada"},
	)


def test_build_url_replaces_path_params(client_with_registry):
	client, _ = client_with_registry
	endpoint = ServiceEndpoint(
		service="census",
		path="/api/customers/{customer_id}",
		method=HttpMethod.GET,
		request_model=None,
		response_model=ExampleResponse,
	)

	url = client._build_url(endpoint, {"customer_id": 99})

	assert url == "https://census.test/api/customers/99"


def test_build_headers_includes_trace_id(client_with_registry):
	client, _ = client_with_registry
	set_trace_id("ROOT.ABCD1")

	headers = client._build_headers()

	assert headers["X-Trace-ID"] == "ROOT.ABCD1"


def test_build_headers_includes_service_name_when_provided(service_registry, endpoint_registry):
	client = ServiceClient(
		service_registry, 
		endpoint_registry, 
		timeout=0.5, 
		service_name="nuntius"
	)

	headers = client._build_headers()

	assert headers["X-Service-Name"] == "nuntius"


def test_build_headers_excludes_service_name_when_not_provided(client_with_registry):
	client, _ = client_with_registry

	headers = client._build_headers()

	assert "X-Service-Name" not in headers


def test_request_returns_validated_response(client_with_registry, async_client_stub):
	client, registry = client_with_registry
	endpoint_key = register_endpoint(registry, HttpMethod.GET)
	async_client_stub["GET"] = make_response(200)

	result = run(client.get(endpoint_key, path_params={"customer_id": "123"}))

	assert isinstance(result, ExampleResponse)
	assert result.name == "Ada"


def test_request_raises_not_found_for_404(client_with_registry, async_client_stub):
	client, registry = client_with_registry
	endpoint_key = register_endpoint(registry, HttpMethod.GET)
	async_client_stub["GET"] = make_response(404)

	with pytest.raises(ServiceNotFoundError):
		run(client.get(endpoint_key, path_params={"customer_id": "999"}))


def test_request_raises_service_unavailable_for_5xx(client_with_registry, async_client_stub):
	client, registry = client_with_registry
	endpoint_key = register_endpoint(registry, HttpMethod.GET)
	async_client_stub["GET"] = make_response(503)

	with pytest.raises(ServiceUnavailableError):
		run(client.get(endpoint_key, path_params={"customer_id": "123"}))


def test_request_translates_timeouts(client_with_registry, async_client_stub):
	client, registry = client_with_registry
	endpoint_key = register_endpoint(registry, HttpMethod.GET)
	async_client_stub["GET"] = httpx.TimeoutException("boom")

	with pytest.raises(ServiceTimeoutError):
		run(client.get(endpoint_key, path_params={"customer_id": "123"}))


def test_request_wraps_http_errors(client_with_registry, async_client_stub):
	client, registry = client_with_registry
	endpoint_key = register_endpoint(registry, HttpMethod.GET)
	async_client_stub["GET"] = make_response(422)

	with pytest.raises(ServiceError):
		run(client.get(endpoint_key, path_params={"customer_id": "123"}))
