# HTTP Module

Async HTTP client for inter-service communication.

## Components

- **ServiceClient** - Async HTTP client
- **EndpointRegistry** - Endpoint definitions registry
- **ServiceEndpoint** - Immutable endpoint definition
- **HttpMethod** - HTTP method enum (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)

## Basic Usage

```python
from fundamentum.infra.http import (
    ServiceClient,
    EndpointRegistry,
    ServiceEndpoint,
    HttpMethod,
)
from fundamentum.infra.settings import ServiceRegistry
from pydantic import BaseModel

class CustomerResponse(BaseModel):
    id: str
    name: str

# Setup
service_registry = ServiceRegistry(settings)
endpoint_registry = EndpointRegistry()

# Register endpoint
endpoint_registry.register(
    "census.get_customer",
    ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=CustomerResponse,
    )
)

# Create client — holds one pooled connection, reused across requests
client = ServiceClient(service_registry, endpoint_registry)

# Make request
customer = await client.get(
    "census.get_customer",
    path_params={"customer_id": "123"}
)

# Close the pool once at shutdown (or use it as an async context manager)
await client.aclose()
```

`ServiceClient` can also be used as an async context manager, which closes
the pool automatically — handy for wiring into a FastAPI `lifespan`:

```python
async with ServiceClient(service_registry, endpoint_registry) as client:
    customer = await client.get("census.get_customer", path_params={"customer_id": "123"})
```

### Response types

`get`/`post`/`put`/`delete` accept an optional `response_type` keyword —
purely a static-typing aid so your type checker infers the concrete return
type instead of `Any`. It doesn't affect validation, which always uses the
endpoint's own `response_model`:

```python
customer = await client.get(
    "census.get_customer",
    response_type=CustomerResponse,
    path_params={"customer_id": "123"},
)
# customer: CustomerResponse
```

List responses work the same way — declare `response_model=list[CustomerResponse]`
on the `ServiceEndpoint` and the client validates/returns a `list[CustomerResponse]`.

### Retries

Idempotent methods (`GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS`) are retried
automatically on connection errors, timeouts, and 5xx responses, with
exponential backoff and jitter (honoring a `Retry-After` header when the
server sends one). `POST`/`PATCH` are never retried automatically, since
retrying a non-idempotent call risks duplicating its effect. Control the
retry budget with `max_retries` (default 3):

```python
client = ServiceClient(service_registry, endpoint_registry, max_retries=5)
```

## Endpoint Registry

```python
registry = EndpointRegistry()

# Register single endpoint
registry.register("census.get_customer", endpoint)

# Bulk register
registry.bulk_register({
    "census.get_customer": ServiceEndpoint(...),
    "census.list_customers": ServiceEndpoint(...),
})

# Check existence
if registry.has("census.get_customer"):
    endpoint = registry.get("census.get_customer")

# List endpoints
all_keys = registry.list_keys()
census_keys = registry.list_by_service("census")
```

## ServiceClient

```python
# GET
customer = await client.get(
    "census.get_customer",
    path_params={"customer_id": "123"}
)

# POST
class CreateCustomerRequest(BaseModel):
    name: str
    email: str

customer = await client.post(
    "census.create_customer",
    body=CreateCustomerRequest(name="John", email="john@example.com")
)

# With query params
customers = await client.get(
    "census.list_customers",
    query_params={"limit": 10}
)
```

## Error Handling

```python
from fundamentum.infra.http import (
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    RequestValidationError,
    UnresolvedPathParameterError,
    ServiceError,
)

try:
    customer = await client.get("census.get_customer", ...)
except ServiceNotFoundError:
    # 404 error
    pass
except ServiceTimeoutError:
    # Timeout (after retries are exhausted, for retryable methods)
    pass
except ServiceUnavailableError:
    # 5xx or connection failure (after retries are exhausted)
    pass
except RequestValidationError:
    # body doesn't match the endpoint's declared request_model
    pass
except UnresolvedPathParameterError:
    # a required {param} in the endpoint path was never supplied
    pass
except ServiceError:
    # Catches all of the above plus any other client-side failure —
    # every exception this module raises is a ServiceError subclass
    pass
```

## API Reference

**ServiceClient(service_registry, endpoint_registry, timeout=10.0, max_retries=3, service_name=None, transport=None, limits=None)**
- `get(endpoint_key, *, response_type=None, path_params=None, query_params=None)`
- `post(endpoint_key, body, *, response_type=None, path_params=None, query_params=None)`
- `put(endpoint_key, body, *, response_type=None, path_params=None, query_params=None)`
- `delete(endpoint_key, *, response_type=None, path_params=None, query_params=None)`
- `aclose()` - Close the pooled connection
- Usable as `async with ServiceClient(...) as client: ...`

**EndpointRegistry()**
- `register(key, endpoint)`
- `bulk_register(endpoints)`
- `get(key)` - Raises KeyError if not found
- `has(key)` - Returns bool
- `list_keys()` - Returns list of all keys
- `list_by_service(service)` - Returns list of keys for service
- `unregister(key)`
- `clear()`

**ServiceEndpoint**
- `service: str` - Service name
- `path: str` - URL path with {param} placeholders
- `method: HttpMethod`
- `request_model: BaseModel | None`
- `response_model: BaseModel | type`
- `timeout: float | None`
