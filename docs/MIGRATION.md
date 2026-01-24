# Fundamentum Infrastructure Migration

## Overview

This document describes the improved infrastructure structure for the Fundamentum common library, migrated from the `temp/` folder with best practices and enhanced Python organization.

## Structure

```
src/fundamentum/
├── __init__.py
├── infra/
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py          # Base settings classes
│   │   ├── protocols.py      # Type protocols for settings
│   │   └── registry.py       # Service URL registry
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── context.py        # Context variables for request tracking
│   │   ├── logging.py        # Structured logging setup
│   │   └── middleware.py     # FastAPI observability middleware
│   ├── http/
│   │   ├── __init__.py
│   │   ├── models.py         # HTTP models and enums
│   │   ├── registry.py       # Endpoint registry
│   │   └── client.py         # Async HTTP client
│   └── utils/
│       └── __init__.py
└── utils/
    └── __init__.py
```

## Key Improvements

### 1. Settings Module (`infra/settings/`)

**Improvements:**
- Created `BaseServiceSettings` as a reusable base class with common fields
- Separated concerns: `base.py` for classes, `protocols.py` for interfaces, `registry.py` for service resolution
- Used Pydantic v2 with proper type hints and validation
- Added comprehensive configuration options (log level, HTTP settings, etc.)
- Improved service registry with caching and better error messages

**Key Classes:**
- `BaseServiceSettings`: Base class for all service settings
- `ServiceRegistry`: Manages service base URLs from settings
- `SettingsProtocol`: Type protocol for settings objects

### 2. Observability Module (`infra/observability/`)

**Improvements:**
- Separated context management into `context.py`
- Improved middleware with better error handling and response headers
- Enhanced logging with structured JSON formatter
- Added utility functions for request ID management
- Better separation of concerns

**Key Components:**
- `ObservabilityMiddleware`: FastAPI middleware for request tracking
- `setup_logging()`: Configures structured logging
- `get_request_id()`, `set_request_id()`: Context management functions
- `ContextFilter`: Adds service context to all log records

### 3. HTTP Module (`infra/http/`)

**Improvements:**
- Created proper exception hierarchy for error handling
- Separated endpoint registry from client implementation
- Enhanced `ServiceEndpoint` with validation and custom timeouts
- Improved HTTP client with:
  - Better error handling and specific exceptions
  - Response validation using Pydantic models
  - Comprehensive logging
  - Request ID propagation
  - Support for all HTTP methods
- Added global registry pattern for easy endpoint management

**Key Classes:**
- `ServiceClient`: Async HTTP client for inter-service communication
- `EndpointRegistry`: Manages service endpoint definitions
- `ServiceEndpoint`: Immutable endpoint definition
- `HttpMethod`: Enum for HTTP methods
- Exception classes: `ServiceError`, `ServiceNotFoundError`, `ServiceTimeoutError`, `ServiceUnavailableError`

## Usage Examples

### Basic Setup

```python
from fundamentum.infra.settings import BaseServiceSettings, ServiceRegistry
from fundamentum.infra.observability import setup_logging, ObservabilityMiddleware
from fundamentum.infra.http import ServiceClient, EndpointRegistry

# 1. Create settings
class MyServiceSettings(BaseServiceSettings):
    census_base_url: str = "http://localhost:8001"
    hermes_base_url: str = "http://localhost:8002"

settings = MyServiceSettings(service_name="my-service")

# 2. Setup logging
logger = setup_logging(settings)

# 3. Create service registry
service_registry = ServiceRegistry(settings)

# 4. Create endpoint registry
endpoint_registry = EndpointRegistry()

# 5. Create HTTP client
client = ServiceClient(service_registry, endpoint_registry)
```

### Registering Endpoints

```python
from fundamentum.infra.http import ServiceEndpoint, HttpMethod, EndpointRegistry
from pydantic import BaseModel

# Define response model
class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str

# Create registry
registry = EndpointRegistry()

# Register endpoint
registry.register(
    "census.customer_by_id",
    ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=CustomerResponse,
    )
)
```

### Making HTTP Requests

```python
# GET request
customer = await client.get(
    "census.customer_by_id",
    path_params={"customer_id": "123"}
)

# POST request
class CreateCustomerRequest(BaseModel):
    name: str
    email: str

new_customer = await client.post(
    "census.create_customer",
    body=CreateCustomerRequest(name="John", email="john@example.com")
)
```

### Using with FastAPI

```python
from fastapi import FastAPI
from fundamentum.infra.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

## Migration Notes

### From `temp/logging.py`
- ✅ Improved with settings-based configuration
- ✅ Added structured formatter class
- ✅ Better context filter implementation
- ✅ Moved to `infra/observability/logging.py`

### From `temp/observability.py`
- ✅ Split into `middleware.py` and `context.py`
- ✅ Enhanced middleware with error handling
- ✅ Added request ID to response headers
- ✅ Better logging structure

### From `temp/settings.py`
- ✅ Created reusable `BaseServiceSettings` class
- ✅ Added more configuration options
- ✅ Improved type hints and validation
- ✅ Moved to `infra/settings/base.py`

### From `temp/http/models.py`
- ✅ Enhanced `ServiceEndpoint` with validation
- ✅ Added proper exception classes
- ✅ Improved `HttpMethod` enum
- ✅ Moved to `infra/http/models.py`

### From `temp/http/service_client.py`
- ✅ Complete rewrite with better architecture
- ✅ Added proper error handling
- ✅ Enhanced logging
- ✅ Support for all HTTP methods
- ✅ Request/response validation
- ✅ Moved to `infra/http/client.py`

### From `temp/http/service_registry.py`
- ✅ Separated into endpoint registry and service registry
- ✅ Better organization and naming
- ✅ Added caching and validation
- ✅ Moved to `infra/http/registry.py` and `infra/settings/registry.py`

### From `temp/http/service_resolver.py`
- ✅ Integrated into `ServiceRegistry` class
- ✅ Improved error messages
- ✅ Added caching
- ✅ Moved to `infra/settings/registry.py`

## Best Practices Applied

1. **Separation of Concerns**: Each module has a single, well-defined responsibility
2. **Type Safety**: Comprehensive type hints using Python 3.10+ syntax
3. **Documentation**: Extensive docstrings with examples
4. **Error Handling**: Proper exception hierarchy and error messages
5. **Testability**: Code structured for easy unit testing
6. **Immutability**: Used frozen dataclasses where appropriate
7. **Dependency Injection**: Components accept dependencies rather than creating them
8. **Protocol-Oriented**: Used protocols for loose coupling
9. **Async First**: Async/await throughout for better performance
10. **Observability**: Comprehensive logging and tracing support

## Next Steps

1. **Testing**: Create comprehensive test suite
2. **Documentation**: Add more examples and tutorials
3. **Validation**: Add runtime validation for critical paths
4. **Metrics**: Add metrics collection (Prometheus, etc.)
5. **Tracing**: Add distributed tracing (OpenTelemetry)
6. **Retry Logic**: Implement exponential backoff for HTTP client
7. **Circuit Breaker**: Add circuit breaker pattern for resilience
8. **Rate Limiting**: Add rate limiting support
