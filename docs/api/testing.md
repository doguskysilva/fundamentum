# HTTP Testing Utilities

Mocking helpers for `fundamentum.infra.http`. These utilities are scoped to
inter-service HTTP calls made through `ServiceClient` — there is no general
testing toolkit for observability or settings; use each module's own objects
directly in tests (e.g. a plain `SimpleNamespace` for settings, as shown in
`tests/infra/settings/test_settings_registry.py`).

## Components

- **`MockHttpTransport`** — builds an `httpx.MockTransport` from
  method+URL-keyed responses you register up front
- **`mock_endpoint`** — registers a mock response on a `MockHttpTransport` for
  a `ServiceEndpoint` already declared in an `EndpointRegistry`, resolving the
  URL (including path params) the same way `ServiceClient` does at runtime

## MockHttpTransport

```python
from fundamentum.infra.http.testing import MockHttpTransport

transport = MockHttpTransport()
transport.register_response(
    method="GET",
    url="https://census.test/api/users/123",
    status_code=200,
    json_body={"id": "123", "name": "John"},
)

# Use directly with httpx
import httpx

async with httpx.AsyncClient(transport=transport.build()) as client:
    response = await client.get("https://census.test/api/users/123")
    assert response.status_code == 200
```

Requesting an unregistered `(method, url)` pair raises `RuntimeError`.

## mock_endpoint

`mock_endpoint` saves you from hand-building the URL: it takes the same
`ServiceEndpoint` and `ServiceRegistry` your production code uses, so the
mocked URL can never drift from what `ServiceClient` will actually request.

```python
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint

endpoint = endpoint_registry.get("census.get_user")

mock_endpoint(
    transport=mock_transport,
    endpoint_key="census.get_user",
    endpoint=endpoint,
    service_registry=service_registry,
    path_params={"user_id": "123"},
    status_code=200,
    json_body={"id": "123", "name": "John", "email": "john@test.com"},
)
```

## Full Example — Testing a ServiceClient Call

```python
import pytest
from pydantic import BaseModel

from fundamentum.infra.http import EndpointRegistry, HttpMethod, ServiceClient, ServiceEndpoint
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint
from fundamentum.infra.settings import ServiceRegistry


class UserResponse(BaseModel):
    id: str
    name: str
    email: str


@pytest.fixture
def service_registry():
    from types import SimpleNamespace

    settings = SimpleNamespace(census_base_url="https://census.test")
    return ServiceRegistry(settings)


@pytest.fixture
def endpoint_registry():
    registry = EndpointRegistry()
    registry.register(
        "census.get_user",
        ServiceEndpoint(
            service="census",
            path="/api/users/{user_id}",
            method=HttpMethod.GET,
            request_model=None,
            response_model=UserResponse,
        ),
    )
    return registry


async def test_get_user(service_registry, endpoint_registry):
    mock_transport = MockHttpTransport()
    mock_endpoint(
        transport=mock_transport,
        endpoint_key="census.get_user",
        endpoint=endpoint_registry.get("census.get_user"),
        service_registry=service_registry,
        path_params={"user_id": "123"},
        json_body={"id": "123", "name": "John", "email": "john@test.com"},
    )

    client = ServiceClient(
        service_registry=service_registry,
        endpoint_registry=endpoint_registry,
        transport=mock_transport.build(),
    )

    response = await client.get("census.get_user", path_params={"user_id": "123"})

    assert isinstance(response, UserResponse)
    assert response.name == "John"
```

Error responses (404, 5xx) are mocked the same way — set `status_code` on
`mock_endpoint` or `register_response` and assert that `ServiceClient` raises
the matching `ServiceNotFoundError` / `ServiceUnavailableError` (see
`docs/api/http.md#error-handling`).

## API Reference

**`MockHttpTransport()`**
- `register_response(*, method: str, url: str, status_code: int = 200, json_body: dict | list | None = None)`
- `build() -> httpx.MockTransport`

**`mock_endpoint(*, transport, endpoint_key, endpoint, service_registry, path_params=None, status_code=200, json_body=None) -> None`**
- Resolves the endpoint's URL via `service_registry` and `endpoint.path`
  (substituting `path_params`), then registers it on `transport`.
