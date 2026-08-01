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
- Optional OpenTelemetry tracing with W3C Trace Context propagation
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

- OpenTelemetry server/client spans using W3C `traceparent` propagation
- FastAPI middleware for structured request/response/error logging
- JSON logging to stdout
- Automatic injection of:
  - service name
  - environment
  - version
  - `trace_id` and `span_id` from the current OpenTelemetry span
- An optional, pluggable request-metrics recorder (count/duration by peer
  service), with an opt-in Prometheus adapter behind the `metrics` extra

> **Note on tracing:** tracing is opt-in. Install `fundamentum[otel]`, call
> `setup_tracing(app, settings)` once during startup, and configure the OTLP
> exporter with standard `OTEL_*` environment variables. Without the extra,
> the package still provides structured logging, middleware, and HTTP client
> functionality without span export.

### Internal HTTP Communication

- `ServiceEndpoint` contract definition
- Generic `ServiceClient`, with retry (backoff + jitter) for idempotent
  methods and a pooled connection reused across requests
- Automatic `traceparent` propagation when the OTel HTTPX instrumentation is
  enabled
- Environment-based service resolution via `.env`

### Health Checks

- `create_health_router()` — a small `APIRouter` with `/healthz` (liveness,
  no dependency checks) and `/readyz` (readiness, aggregates named
  sync/async checks you supply)

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

Ships a `py.typed` marker (PEP 561), so `mypy`/`pyright` in consuming
services pick up its type hints instead of treating it as untyped.

Want the optional Prometheus metrics adapter too? Add the `metrics` extra:

```
fundamentum[metrics] @ git+https://github.com/doguskysilva/fundamentum.git@v0.2.0
```

For OpenTelemetry tracing, install the `otel` extra as well:

```
fundamentum[otel] @ git+https://github.com/doguskysilva/fundamentum.git@v0.2.0
```

## Quick Start

```python
from fastapi import FastAPI
from fundamentum.infra.settings import BaseServiceSettings
from fundamentum.infra.observability import (
    setup_logging,
    setup_tracing,
    ObservabilityMiddleware,
)
from fundamentum.infra.http import ServiceClient, EndpointRegistry, ServiceEndpoint, HttpMethod
from fundamentum.infra.settings import ServiceRegistry
from pydantic import Field, BaseModel

# 1. Define settings
class Settings(BaseServiceSettings):
    census_base_url: str = Field(default="http://localhost:8001")

settings = Settings(service_name="my-service")

# 2. Setup logging
logger = setup_logging(settings)

# 3. Create FastAPI app with middleware (adds request logging and metrics)
app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
setup_tracing(app, settings)  # requires fundamentum[otel]

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
