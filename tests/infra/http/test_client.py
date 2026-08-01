"""Tests for the async ServiceClient."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.models import (
    HttpMethod,
    RequestValidationError,
    ServiceEndpoint,
    ServiceError,
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    UnresolvedPathParameterError,
)
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.observability.context import clear_trace_id, set_trace_id
from fundamentum.infra.observability.metrics import get_metrics_recorder, set_metrics_recorder
from fundamentum.infra.settings.registry import ServiceRegistry


class ExampleResponse(BaseModel):
    id: str
    name: str


class ExampleRequest(BaseModel):
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


@pytest.fixture(autouse=True)
def reset_trace_context():
    clear_trace_id()
    yield
    clear_trace_id()


@pytest.fixture(autouse=True)
def reset_metrics_recorder():
    original = get_metrics_recorder()
    yield
    set_metrics_recorder(original)


class ScriptedTransport(httpx.AsyncBaseTransport):
    """Replays a fixed sequence of responses/exceptions, one per call.

    Driving requests through this via `self._client.request(...)` (i.e. the
    real `httpx.AsyncClient`) exercises the exact same code path production
    traffic does, including response.request wiring for raise_for_status().
    """

    def __init__(self, script: list[httpx.Response | Exception]):
        self._script = list(script)
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if not self._script:
            raise AssertionError("ScriptedTransport ran out of scripted responses")
        outcome = self._script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def register_endpoint(
    registry: EndpointRegistry,
    method: HttpMethod,
    *,
    key: str = "census.get_user",
    path: str = "/api/customers/{customer_id}",
    request_model: type[BaseModel] | None = None,
) -> str:
    registry.register(
        key,
        ServiceEndpoint(
            service="census",
            path=path,
            method=method,
            request_model=request_model,
            response_model=ExampleResponse,
        ),
    )
    return key


def make_response(status_code: int, json_data: dict | None = None, headers=None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code, json=json_data or {"id": "123", "name": "Ada"}, headers=headers
    )


def build_client(service_registry, endpoint_registry, transport, **kwargs) -> ServiceClient:
    return ServiceClient(service_registry, endpoint_registry, transport=transport, **kwargs)


def test_build_url_replaces_path_params(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))
    endpoint = ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=ExampleResponse,
    )

    url = client._build_url(endpoint, {"customer_id": 99})

    assert url == "https://census.test/api/customers/99"


def test_build_url_warns_but_succeeds_for_extraneous_path_param(
    service_registry, endpoint_registry
):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))
    endpoint = ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=ExampleResponse,
    )

    url = client._build_url(endpoint, {"customer_id": "1", "extra": "ignored"})

    assert url == "https://census.test/api/customers/1"


def test_build_url_raises_on_unresolved_path_param(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))
    endpoint = ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=ExampleResponse,
    )

    with pytest.raises(UnresolvedPathParameterError):
        client._build_url(endpoint, None)


def test_build_headers_includes_trace_id(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))
    set_trace_id("ROOT.ABCD1")

    headers = client._build_headers()

    assert headers["X-Trace-ID"] == "ROOT.ABCD1"


def test_build_headers_includes_service_name_when_provided(service_registry, endpoint_registry):
    client = build_client(
        service_registry, endpoint_registry, ScriptedTransport([]), service_name="nuntius"
    )

    headers = client._build_headers()

    assert headers["X-Service-Name"] == "nuntius"


def test_build_headers_excludes_service_name_when_not_provided(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))

    headers = client._build_headers()

    assert "X-Service-Name" not in headers


def test_request_returns_validated_response(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(200)])
    client = build_client(service_registry, endpoint_registry, transport)

    result = run(client.get(endpoint_key, path_params={"customer_id": "123"}))

    assert isinstance(result, ExampleResponse)
    assert result.name == "Ada"


def test_response_type_hint_does_not_change_runtime_behavior(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(200)])
    client = build_client(service_registry, endpoint_registry, transport)

    result = run(
        client.get(endpoint_key, response_type=ExampleResponse, path_params={"customer_id": "123"})
    )

    assert isinstance(result, ExampleResponse)


def test_request_validates_list_response(service_registry, endpoint_registry):
    endpoint_registry.register(
        "census.list_users",
        ServiceEndpoint(
            service="census",
            path="/api/customers",
            method=HttpMethod.GET,
            request_model=None,
            response_model=list[ExampleResponse],
        ),
    )
    transport = ScriptedTransport(
        [httpx.Response(200, json=[{"id": "1", "name": "Ada"}, {"id": "2", "name": "Bob"}])]
    )
    client = build_client(service_registry, endpoint_registry, transport)

    result = run(client.get("census.list_users"))

    assert result == [ExampleResponse(id="1", name="Ada"), ExampleResponse(id="2", name="Bob")]


def test_request_raises_not_found_for_404(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(404)])
    client = build_client(service_registry, endpoint_registry, transport, max_retries=3)

    with pytest.raises(ServiceNotFoundError):
        run(client.get(endpoint_key, path_params={"customer_id": "999"}))

    assert len(transport.calls) == 1  # 404 is never retried


def test_request_raises_service_unavailable_after_exhausting_retries(
    service_registry, endpoint_registry
):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(503)] * 3)
    client = build_client(
        service_registry, endpoint_registry, transport, max_retries=2, timeout=0.5
    )

    with pytest.raises(ServiceUnavailableError):
        run(client.get(endpoint_key, path_params={"customer_id": "123"}))

    assert len(transport.calls) == 3  # initial attempt + 2 retries


def test_request_retries_get_after_transient_5xx_then_succeeds(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(503), make_response(200)])
    client = build_client(
        service_registry, endpoint_registry, transport, max_retries=2, timeout=0.5
    )

    result = run(client.get(endpoint_key, path_params={"customer_id": "123"}))

    assert isinstance(result, ExampleResponse)
    assert len(transport.calls) == 2


def test_request_does_not_retry_post_on_5xx(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(
        endpoint_registry, HttpMethod.POST, key="census.create_user", path="/api/customers"
    )
    transport = ScriptedTransport([make_response(503)])
    client = build_client(
        service_registry, endpoint_registry, transport, max_retries=3, timeout=0.5
    )

    with pytest.raises(ServiceUnavailableError):
        run(client.post(endpoint_key, body=None))

    assert len(transport.calls) == 1


def test_request_translates_timeouts_after_exhausting_retries(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([httpx.TimeoutException("boom"), httpx.TimeoutException("boom")])
    client = build_client(
        service_registry, endpoint_registry, transport, max_retries=1, timeout=0.5
    )

    with pytest.raises(ServiceTimeoutError):
        run(client.get(endpoint_key, path_params={"customer_id": "123"}))

    assert len(transport.calls) == 2


def test_request_wraps_connection_errors_as_service_unavailable(
    service_registry, endpoint_registry
):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([httpx.ConnectError("refused")])
    client = build_client(
        service_registry, endpoint_registry, transport, max_retries=0, timeout=0.5
    )

    with pytest.raises(ServiceUnavailableError):
        run(client.get(endpoint_key, path_params={"customer_id": "123"}))


def test_request_wraps_http_errors(service_registry, endpoint_registry):
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(422)])
    client = build_client(service_registry, endpoint_registry, transport)

    with pytest.raises(ServiceError):
        run(client.get(endpoint_key, path_params={"customer_id": "123"}))


def test_request_body_mismatch_raises_request_validation_error(service_registry, endpoint_registry):
    class OtherRequest(BaseModel):
        pass

    endpoint_key = register_endpoint(
        endpoint_registry,
        HttpMethod.POST,
        key="census.create_user",
        path="/api/customers",
        request_model=OtherRequest,
    )
    transport = ScriptedTransport([])  # never reached — validation fails first
    client = build_client(service_registry, endpoint_registry, transport)

    with pytest.raises(RequestValidationError):
        run(client.post(endpoint_key, body=ExampleRequest(name="Ada")))


def test_request_records_outbound_metrics_on_success(service_registry, endpoint_registry):
    events = []

    class RecordingRecorder:
        def record_request(self, **kwargs):
            events.append(kwargs)

    set_metrics_recorder(RecordingRecorder())
    endpoint_key = register_endpoint(endpoint_registry, HttpMethod.GET)
    transport = ScriptedTransport([make_response(200)])
    client = build_client(service_registry, endpoint_registry, transport)

    run(client.get(endpoint_key, path_params={"customer_id": "123"}))

    assert len(events) == 1
    assert events[0]["direction"] == "outbound"
    assert events[0]["peer_service"] == "census"
    assert events[0]["status_code"] == 200


def test_backoff_seconds_honors_retry_after_header():
    assert ServiceClient._backoff_seconds(0, "2") == 2.0


def test_backoff_seconds_falls_back_to_exponential_with_jitter():
    delay = ServiceClient._backoff_seconds(2, None)

    assert 4.0 <= delay <= 5.0  # base = min(2**2, cap) = 4, plus up to 25% jitter


def test_aclose_closes_underlying_client(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))

    run(client.aclose())

    assert client._client.is_closed


def test_async_context_manager_closes_on_exit(service_registry, endpoint_registry):
    client = build_client(service_registry, endpoint_registry, ScriptedTransport([]))

    async def _use() -> None:
        async with client:
            pass

    run(_use())

    assert client._client.is_closed
