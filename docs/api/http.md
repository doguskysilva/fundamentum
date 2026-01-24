# HTTP Module

Async HTTP client for inter-service communication.

## Components

- **ServiceClient** - Async HTTP client
- **EndpointRegistry** - Endpoint definitions registry
- **ServiceEndpoint** - Immutable endpoint definition
- **HttpMethod** - HTTP method enum (GET, POST, PUT, DELETE, PATCH)

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

# Create client
client = ServiceClient(service_registry, endpoint_registry)

# Make request
customer = await client.get(
    "census.get_customer",
    path_params={"customer_id": "123"}
)
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
    ServiceError,
)

try:
    customer = await client.get("census.get_customer", ...)
except ServiceNotFoundError:
    # 404 error
    pass
except ServiceTimeoutError:
    # Timeout
    pass
except ServiceUnavailableError:
    # 5xx error
    pass
except ServiceError:
    # Other errors
    pass
```

## API Reference

**ServiceClient(service_registry, endpoint_registry, timeout=10.0, service_name=None)**
- `get(endpoint_key, path_params=None, query_params=None)`
- `post(endpoint_key, body, path_params=None, query_params=None)`
- `put(endpoint_key, body, path_params=None, query_params=None)`
- `delete(endpoint_key, path_params=None, query_params=None)`

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
