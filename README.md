# Fundamentum

[![CI](https://github.com/doguskysilva/fundamentum/actions/workflows/ci.yml/badge.svg)](https://github.com/doguskysilva/fundamentum/actions/workflows/ci.yml)

Fundamentum is a shared Python package that provides infrastructure primitives
for a microservices ecosystem.

It exists to centralize cross-cutting concerns such as observability and
internal service communication, while explicitly avoiding domain coupling.

*The goal is consistency without overengineering.*

## About the name

*Fundamentum* is the Latin word for a foundation or groundwork — the base on
which a structure rests. That's the role this package plays in the ecosystem:
it isn't a service itself, but the common ground the services are built on.
Officina, Exemplar, Cursus, and the rest all stand on the same *Fundamentum*.

## Purpose

Fundamentum is designed to be used by multiple Python microservices
(FastAPI-based) to avoid code duplication while preserving service autonomy.

It provides:

- Structured logging
- Request correlation
- Minimal distributed tracing (header propagation — see the note below)
- A generic internal HTTP client
- Explicit service integration contracts

It contains no business logic and no domain models — see
[What Fundamentum Does NOT Provide](#what-fundamentum-does-not-provide).

## Requirements

- Python 3.14+
- FastAPI / Pydantic

The project uses [`uv`](https://github.com/astral-sh/uv) for dependency
management and [`ruff`](https://github.com/astral-sh/ruff) for linting. If
you're contributing, install `uv` and run `uv sync` to set up the environment.

## What Fundamentum Provides

### Observability

- `request_id` propagation using `contextvars`
- FastAPI middleware for request tracing
- JSON logging to stdout
- Automatic injection of:
  - service name
  - environment
  - version
  - request_id

> **Note on tracing:** tracing here means propagating a correlation header
> (`X-Request-ID`) across service calls, not emitting spans. There is no
> OpenTelemetry integration today — this is deliberately minimal.

### Internal HTTP Communication

- `ServiceEndpoint` contract definition
- Generic `ServiceClient`
- Automatic propagation of `X-Request-ID`
- Environment-based service resolution via `.env`

## What Fundamentum Does NOT Provide

- No domain models
- No wire models specific to any service
- No service registry with concrete endpoints
- No business logic
- No orchestration logic
- No service discovery or mesh abstractions

Each microservice remains responsible for:

- Its own wire models
- Its own endpoint registry
- Its own configuration
- Its own domain logic

## Installation

Used as a Git dependency (pin to a published tag):

```
fundamentum @ git+https://github.com/doguskysilva/fundamentum.git@v0.2.0
```

Or install locally for development:

```
pip install -e /path/to/fundamentum
```

## Quick Start

```python
from fastapi import FastAPI
from fundamentum.infra.settings import BaseServiceSettings
from fundamentum.infra.observability import setup_logging, ObservabilityMiddleware
from fundamentum.infra.http import ServiceClient, EndpointRegistry, ServiceEndpoint, HttpMethod
from fundamentum.infra.settings import ServiceRegistry
from pydantic import Field, BaseModel

# 1. Define settings
class Settings(BaseServiceSettings):
    census_base_url: str = Field(default="http://localhost:8001")

settings = Settings(service_name="my-service")

# 2. Setup logging
logger = setup_logging(settings)

# 3. Create FastAPI app with middleware (adds request tracing and logging)
app = FastAPI()
app.add_middleware(ObservabilityMiddleware)

# 4. Setup HTTP client
service_registry = ServiceRegistry(settings)
endpoint_registry = EndpointRegistry()

class CustomerResponse(BaseModel):
    id: str
    name: str

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

http_client = ServiceClient(service_registry, endpoint_registry)

# 5. Use in endpoints
@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    return await http_client.get(
        "census.get_customer",
        path_params={"customer_id": customer_id}
    )
```

## Documentation

For detailed documentation, see the [docs/](docs) directory:

- **[Quick Setup Guide](docs/README.md)** — Getting started
- **[HTTP Module](docs/api/http.md)** — Inter-service communication
- **[Settings Module](docs/api/settings.md)** — Configuration management
- **[Observability Module](docs/api/observability.md)** — Logging and tracing
- **[HTTP Testing Utilities](docs/api/testing.md)** — Mocking peer-service HTTP calls

## License

MIT — see [LICENSE](LICENSE).
