# Fundamentum Documentation

Common infrastructure library for Python microservices.

## Installation

```bash
pip install -e /path/to/fundamentum
```

## Quick Setup

### 1. Create Settings

```python
from fundamentum.infra.settings import BaseServiceSettings
from pydantic import Field

class Settings(BaseServiceSettings):
    database_url: str = Field(default="postgresql://localhost/mydb")
    census_base_url: str = Field(default="http://localhost:8001")

settings = Settings(service_name="my-service")
```

### 2. Setup Logging & Middleware

```python
from fastapi import FastAPI
from fundamentum.infra.observability import setup_logging, ObservabilityMiddleware

logger = setup_logging(settings)

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

### 3. Setup HTTP Client

```python
from fundamentum.infra.http import ServiceClient, EndpointRegistry, ServiceEndpoint, HttpMethod
from fundamentum.infra.settings import ServiceRegistry
from pydantic import BaseModel

class CustomerResponse(BaseModel):
    id: str
    name: str

# Create registries
service_registry = ServiceRegistry(settings)
endpoint_registry = EndpointRegistry()

# Register endpoints
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
http_client = ServiceClient(service_registry, endpoint_registry)
```

### 4. Use in Routes

```python
@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    return await http_client.get(
        "census.get_customer",
        path_params={"customer_id": customer_id}
    )
```

## Component Documentation

- **[HTTP](api/http.md)** - Inter-service HTTP client and endpoints
- **[Settings](api/settings.md)** - Configuration management
- **[Observability](api/observability.md)** - Logging and request tracking
- **[Testing](api/testing.md)** - Mocking utilities

## Migration Guide

Migrating from `temp/` code? See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
