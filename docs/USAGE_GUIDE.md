# Fundamentum Usage Guide

Quick reference guide for using Fundamentum infrastructure in your microservices.

## Installation

```bash
pip install -e /path/to/fundamentum
```

Or add to your `requirements.txt`:
```
fundamentum @ file:///path/to/fundamentum
```

## Quick Start

### 1. Create Your Service Settings

```python
# app/config.py
from fundamentum.infra.settings import BaseServiceSettings
from pydantic import Field

class Settings(BaseServiceSettings):
    # Service-specific settings
    database_url: str = Field(
        default="postgresql://localhost/mydb",
        description="Database connection URL"
    )
    
    # Other service URLs (for inter-service communication)
    census_base_url: str = Field(default="http://localhost:8001")
    hermes_base_url: str = Field(default="http://localhost:8002")

settings = Settings(service_name="my-service")
```

### 2. Setup Logging

```python
# app/main.py
from fundamentum.infra.observability import setup_logging
from app.config import settings

# Setup logging at application startup
logger = setup_logging(settings)
logger.info("Application starting")
```

### 3. Add Observability Middleware (FastAPI)

```python
# app/main.py
from fastapi import FastAPI
from fundamentum.infra.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

### 4. Setup HTTP Client for Inter-Service Communication

```python
# app/clients.py
from fundamentum.infra.http import (
    ServiceClient,
    EndpointRegistry,
    ServiceEndpoint,
    HttpMethod,
)
from fundamentum.infra.settings import ServiceRegistry
from app.config import settings
from app.models import CustomerResponse

# Create service registry
service_registry = ServiceRegistry(settings)

# Create endpoint registry and register endpoints
endpoint_registry = EndpointRegistry()

endpoint_registry.register(
    "census.customer_by_id",
    ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=CustomerResponse,
    )
)

# Create HTTP client
http_client = ServiceClient(
    service_registry=service_registry,
    endpoint_registry=endpoint_registry,
    timeout=settings.http_timeout,
)
```

### 5. Use the HTTP Client in Your Routes

```python
# app/routes.py
from fastapi import APIRouter, HTTPException
from fundamentum.infra.http import ServiceNotFoundError
from app.clients import http_client

router = APIRouter()

@router.get("/customer/{customer_id}")
async def get_customer(customer_id: str):
    try:
        customer = await http_client.get(
            "census.customer_by_id",
            path_params={"customer_id": customer_id}
        )
        return customer
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Customer not found")
```

## Common Patterns

### Custom Logger with Context

```python
from fundamentum.infra.observability import get_logger, get_request_id

logger = get_logger(__name__)

def process_order(order_id: str):
    logger.info(
        "Processing order",
        extra={
            "order_id": order_id,
            "request_id": get_request_id(),
        }
    )
```

### Background Tasks with Request ID

```python
from fundamentum.infra.observability import get_request_id, set_request_id
from fastapi import BackgroundTasks

async def send_notification(user_id: str, request_id: str):
    # Restore request ID for tracing
    set_request_id(request_id)
    
    # Your background task logic
    logger.info(f"Sending notification to {user_id}")

@app.post("/orders")
async def create_order(background_tasks: BackgroundTasks):
    request_id = get_request_id()
    
    # Add background task with request ID
    background_tasks.add_task(
        send_notification,
        user_id="123",
        request_id=request_id
    )
    
    return {"status": "created"}
```

### Using Global Endpoint Registry

```python
from fundamentum.infra.http import get_global_registry, ServiceEndpoint, HttpMethod

# Get the global registry
registry = get_global_registry()

# Register your endpoints at startup
def register_endpoints():
    registry.bulk_register({
        "census.customer_by_id": ServiceEndpoint(...),
        "census.list_customers": ServiceEndpoint(...),
        "hermes.send_email": ServiceEndpoint(...),
    })

# In your main.py startup
@app.on_event("startup")
async def startup():
    register_endpoints()
```

### Error Handling

```python
from fundamentum.infra.http import (
    ServiceError,
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)

try:
    result = await http_client.get("census.customer_by_id", ...)
except ServiceNotFoundError as e:
    # Handle 404
    logger.warning(f"Resource not found: {e}")
except ServiceTimeoutError as e:
    # Handle timeout
    logger.error(f"Request timeout: {e}")
except ServiceUnavailableError as e:
    # Handle 5xx errors
    logger.error(f"Service unavailable: {e}")
except ServiceError as e:
    # Handle other errors
    logger.error(f"Service error: {e}")
```

### Environment-Specific Configuration

```python
# .env.development
SERVICE_NAME=my-service
VERSION=dev
ENVIRONMENT=development
LOG_LEVEL=DEBUG
CENSUS_BASE_URL=http://localhost:8001

# .env.production
SERVICE_NAME=my-service
VERSION=1.0.0
ENVIRONMENT=production
LOG_LEVEL=INFO
CENSUS_BASE_URL=https://census.example.com
```

## Complete Example

```python
# app/main.py
from fastapi import FastAPI, HTTPException
from fundamentum.infra.settings import BaseServiceSettings, ServiceRegistry
from fundamentum.infra.observability import (
    ObservabilityMiddleware,
    setup_logging,
    get_logger,
)
from fundamentum.infra.http import (
    ServiceClient,
    EndpointRegistry,
    ServiceEndpoint,
    HttpMethod,
    ServiceNotFoundError,
)
from pydantic import BaseModel, Field

# 1. Settings
class Settings(BaseServiceSettings):
    database_url: str = Field(default="sqlite:///./test.db")
    census_base_url: str = Field(default="http://localhost:8001")

settings = Settings(service_name="my-service")

# 2. Setup logging
logger = setup_logging(settings)
app_logger = get_logger(__name__)

# 3. Create FastAPI app
app = FastAPI(title=settings.service_name, version=settings.service_version)

# 4. Add middleware
app.add_middleware(ObservabilityMiddleware)

# 5. Setup HTTP client
service_registry = ServiceRegistry(settings)
endpoint_registry = EndpointRegistry()

class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str

endpoint_registry.register(
    "census.customer_by_id",
    ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=CustomerResponse,
    )
)

http_client = ServiceClient(
    service_registry=service_registry,
    endpoint_registry=endpoint_registry,
)

# 6. Routes
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
    }

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    try:
        customer = await http_client.get(
            "census.customer_by_id",
            path_params={"customer_id": customer_id}
        )
        return customer
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Customer not found")

@app.on_event("startup")
async def startup():
    app_logger.info("Application started successfully")

@app.on_event("shutdown")
async def shutdown():
    app_logger.info("Application shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Testing

### Testing with Fundamentum

```python
# tests/test_app.py
import pytest
from fundamentum.infra.settings import BaseServiceSettings
from fundamentum.infra.http import EndpointRegistry, ServiceEndpoint, HttpMethod

@pytest.fixture
def settings():
    return BaseServiceSettings(
        service_name="test-service",
        environment="development",
    )

@pytest.fixture
def endpoint_registry():
    registry = EndpointRegistry()
    # Register test endpoints
    return registry

def test_settings(settings):
    assert settings.service_name == "test-service"
    assert settings.environment == "development"
```

## Tips and Best Practices

1. **Always use environment variables** for configuration in production
2. **Register all endpoints at startup** for validation
3. **Use proper exception handling** for HTTP client calls
4. **Log important events** with structured logging
5. **Include request IDs** in logs for tracing
6. **Use type hints** everywhere for better IDE support
7. **Validate Pydantic models** for request/response bodies
8. **Keep settings in a separate module** (e.g., `app/config.py`)
9. **Create a clients module** for all HTTP clients (e.g., `app/clients.py`)
10. **Test with different settings** using fixtures

## Troubleshooting

### Service not found error
```python
# Check if service URL is configured in settings
from app.config import settings
print(settings.census_base_url)  # Should print the URL
```

### Endpoint not found error
```python
# List all registered endpoints
from app.clients import endpoint_registry
print(endpoint_registry.list_keys())
```

### Request ID not appearing in logs
```python
# Make sure ObservabilityMiddleware is added to FastAPI
app.add_middleware(ObservabilityMiddleware)
```

### Import errors
```python
# Make sure fundamentum is installed
pip list | grep fundamentum
```
