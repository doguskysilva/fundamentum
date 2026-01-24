# Integration Guide: Migrating from temp/ to fundamentum

This guide shows how to migrate an existing service from using `temp/` files to the new `fundamentum` library.

## Step 1: Install fundamentum

Add to your service's `requirements.txt` or `pyproject.toml`:

```bash
# Option 1: Local development
fundamentum @ file:///path/to/fundamentum

# Option 2: Git repository
fundamentum @ git+https://github.com/yourorg/fundamentum.git@main

# Option 3: Internal PyPI (if published)
fundamentum>=0.1.0
```

Install:
```bash
pip install -e /path/to/fundamentum
```

## Step 2: Update Settings

### Before (using temp/settings.py)
```python
# app/core/settings.py
from app.core.temp.settings import Settings, settings

# Usage
print(settings.census_base_url)
```

### After (using fundamentum)
```python
# app/core/settings.py
from fundamentum.infra.settings import BaseServiceSettings
from pydantic import Field

class Settings(BaseServiceSettings):
    # Your service-specific settings
    database_url: str = Field(
        default="postgresql://localhost/mydb",
        description="Database connection URL"
    )
    
    # Service URLs for inter-service communication
    census_base_url: str = Field(default="http://localhost:8001")
    hermes_base_url: str = Field(default="http://localhost:8002")

# Create instance
settings = Settings(service_name="your-service-name")  # IMPORTANT: Add service name
```

**Changes needed:**
1. ✅ Change import from `temp.settings` to `fundamentum.infra.settings`
2. ✅ Inherit from `BaseServiceSettings` instead of `BaseSettings`
3. ✅ Add `service_name` parameter when instantiating
4. ✅ Remove hardcoded `service_name` field

## Step 3: Update Logging

### Before (using temp/logging.py)
```python
# app/core/logging.py
from app.core.temp.logging import setup_logging

setup_logging()
```

### After (using fundamentum)
```python
# app/main.py (or wherever you initialize the app)
from fundamentum.infra.observability import setup_logging, get_logger
from app.core.settings import settings

# Setup logging at application startup
logger = setup_logging(settings)

# Get loggers in other modules
# app/services/customer.py
from fundamentum.infra.observability import get_logger

logger = get_logger(__name__)

def process_customer(customer_id: str):
    logger.info("Processing customer", extra={"customer_id": customer_id})
```

**Changes needed:**
1. ✅ Change import from `temp.logging` to `fundamentum.infra.observability`
2. ✅ Pass `settings` to `setup_logging()`
3. ✅ Use `get_logger(__name__)` instead of `logging.getLogger()`

## Step 4: Update Observability Middleware

### Before (using temp/observability.py)
```python
# app/main.py
from app.core.temp.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

### After (using fundamentum)
```python
# app/main.py
from fundamentum.infra.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

**Changes needed:**
1. ✅ Change import from `temp.observability` to `fundamentum.infra.observability`
2. ✅ No other changes needed!

## Step 5: Update HTTP Models

### Before (using temp/http/models.py)
```python
# app/wire/endpoints.py
from app.core.temp.http.models import ServiceEndpoint, HttpMethod
```

### After (using fundamentum)
```python
# app/wire/endpoints.py
from fundamentum.infra.http import ServiceEndpoint, HttpMethod
```

**Changes needed:**
1. ✅ Change import from `temp.http.models` to `fundamentum.infra.http`
2. ✅ Change `url` to `path` in ServiceEndpoint
3. ✅ Change `request` to `request_model` in ServiceEndpoint
4. ✅ Change `response` to `response_model` in ServiceEndpoint

### Example:
```python
# Before
endpoint = ServiceEndpoint(
    service="census",
    url="/api/customers/{customer_id}",
    method=HttpMethod.GET,
    request=None,
    response=CustomerResponse,
)

# After
endpoint = ServiceEndpoint(
    service="census",
    path="/api/customers/{customer_id}",  # Changed: url -> path
    method=HttpMethod.GET,
    request_model=None,  # Changed: request -> request_model
    response_model=CustomerResponse,  # Changed: response -> response_model
)
```

## Step 6: Update Service Registry

### Before (using temp/http/service_registry.py)
```python
# app/wire/endpoints.py
from app.core.temp.http.service_registry import SERVICE_ENDPOINTS

SERVICE_ENDPOINTS = {
    "census.customer_by_id": ServiceEndpoint(...),
}
```

### After (using fundamentum)
```python
# app/wire/endpoints.py
from fundamentum.infra.http import EndpointRegistry, ServiceEndpoint, HttpMethod
from app.wire.models import CustomerResponse

# Create registry
endpoint_registry = EndpointRegistry()

# Register endpoints
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

# Or register multiple at once
endpoint_registry.bulk_register({
    "census.customer_by_id": ServiceEndpoint(...),
    "census.list_customers": ServiceEndpoint(...),
})
```

**Changes needed:**
1. ✅ Change from global dict to `EndpointRegistry` class
2. ✅ Use `register()` or `bulk_register()` methods
3. ✅ Update field names (url->path, request->request_model, etc.)

## Step 7: Update Service Client

### Before (using temp/http/service_client.py)
```python
# app/services/census.py
from app.core.temp.http.service_client import service_client

async def get_customer(customer_id: str):
    return await service_client.get(
        "census.customer_by_id",
        path_params={"customer_id": customer_id}
    )
```

### After (using fundamentum)
```python
# app/clients.py (create this file)
from fundamentum.infra.http import ServiceClient
from fundamentum.infra.settings import ServiceRegistry
from app.core.settings import settings
from app.wire.endpoints import endpoint_registry

# Create service registry
service_registry = ServiceRegistry(settings)

# Create HTTP client
http_client = ServiceClient(
    service_registry=service_registry,
    endpoint_registry=endpoint_registry,
    timeout=settings.http_timeout,
)

# app/services/census.py
from app.clients import http_client

async def get_customer(customer_id: str):
    return await http_client.get(
        "census.customer_by_id",
        path_params={"customer_id": customer_id}
    )
```

**Changes needed:**
1. ✅ Create service registry with settings
2. ✅ Create client with dependencies (not singleton)
3. ✅ Use dependency injection
4. ✅ Update imports

## Step 8: Update Context Usage

### Before (using temp/observability.py)
```python
from app.core.temp.observability import request_id_ctx

request_id = request_id_ctx.get()
```

### After (using fundamentum)
```python
from fundamentum.infra.observability import get_request_id

request_id = get_request_id()
```

**Changes needed:**
1. ✅ Use `get_request_id()` function instead of direct context variable access
2. ✅ Use `set_request_id()` instead of `request_id_ctx.set()`

## Step 9: Update Error Handling

### Before
```python
try:
    result = await service_client.get(...)
except Exception as e:
    logger.error(f"Error: {e}")
```

### After
```python
from fundamentum.infra.http import (
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    ServiceError,
)

try:
    result = await http_client.get(...)
except ServiceNotFoundError:
    # Handle 404
    logger.warning("Resource not found")
except ServiceTimeoutError:
    # Handle timeout
    logger.error("Request timed out")
except ServiceUnavailableError:
    # Handle 5xx
    logger.error("Service unavailable")
except ServiceError as e:
    # Handle other errors
    logger.error(f"Service error: {e}")
```

**Changes needed:**
1. ✅ Use specific exception types
2. ✅ Better error handling

## Step 10: Remove temp/ Dependencies

After verifying everything works:

```bash
# Remove temp/ imports
grep -r "from app.core.temp" app/
# Or
grep -r "import.*temp" app/

# Remove temp/ folder
rm -rf app/core/temp/
```

## Complete Example

Here's a complete before/after example:

### Before (app/main.py)
```python
from fastapi import FastAPI
from app.core.temp.settings import settings
from app.core.temp.logging import setup_logging
from app.core.temp.observability import ObservabilityMiddleware
from app.core.temp.http.service_client import service_client

setup_logging()

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    return await service_client.get(
        "census.customer_by_id",
        path_params={"customer_id": customer_id}
    )
```

### After (app/main.py)
```python
from fastapi import FastAPI, HTTPException
from fundamentum.infra.observability import (
    ObservabilityMiddleware,
    setup_logging,
    get_logger,
)
from fundamentum.infra.http import ServiceNotFoundError
from app.core.settings import settings
from app.clients import http_client

# Setup logging
logger = setup_logging(settings)
app_logger = get_logger(__name__)

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
)
app.add_middleware(ObservabilityMiddleware)

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    try:
        return await http_client.get(
            "census.customer_by_id",
            path_params={"customer_id": customer_id}
        )
    except ServiceNotFoundError:
        raise HTTPException(status_code=404, detail="Customer not found")

@app.on_event("startup")
async def startup():
    app_logger.info("Application started")
```

### New Files to Create

**app/core/settings.py:**
```python
from fundamentum.infra.settings import BaseServiceSettings
from pydantic import Field

class Settings(BaseServiceSettings):
    database_url: str = Field(default="postgresql://localhost/mydb")
    census_base_url: str = Field(default="http://localhost:8001")

settings = Settings(service_name="my-service")
```

**app/clients.py:**
```python
from fundamentum.infra.http import ServiceClient
from fundamentum.infra.settings import ServiceRegistry
from app.core.settings import settings
from app.wire.endpoints import endpoint_registry

service_registry = ServiceRegistry(settings)
http_client = ServiceClient(service_registry, endpoint_registry)
```

**app/wire/endpoints.py:**
```python
from fundamentum.infra.http import EndpointRegistry, ServiceEndpoint, HttpMethod
from app.wire.models import CustomerResponse

endpoint_registry = EndpointRegistry()

endpoint_registry.bulk_register({
    "census.customer_by_id": ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=CustomerResponse,
    ),
})
```

## Testing the Migration

### 1. Unit Tests
Update test fixtures:

```python
# tests/conftest.py
import pytest
from fundamentum.infra.settings import BaseServiceSettings
from fundamentum.infra.http import EndpointRegistry

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
```

### 2. Integration Tests
Test the HTTP client:

```python
# tests/test_client.py
import pytest
from fundamentum.infra.http import ServiceClient, ServiceNotFoundError

@pytest.mark.asyncio
async def test_get_customer(http_client):
    customer = await http_client.get(
        "census.customer_by_id",
        path_params={"customer_id": "123"}
    )
    assert customer.id == "123"

@pytest.mark.asyncio
async def test_customer_not_found(http_client):
    with pytest.raises(ServiceNotFoundError):
        await http_client.get(
            "census.customer_by_id",
            path_params={"customer_id": "999"}
        )
```

## Troubleshooting

### Import Errors
```python
# Error: No module named 'fundamentum'
# Solution: Make sure fundamentum is installed
pip install -e /path/to/fundamentum
```

### Settings Validation Errors
```python
# Error: service_name field required
# Solution: Add service_name when creating Settings instance
settings = Settings(service_name="my-service")
```

### Endpoint Not Found
```python
# Error: Endpoint 'census.customer_by_id' not found
# Solution: Make sure endpoint is registered
endpoint_registry.register("census.customer_by_id", ...)
```

### Service Not Configured
```python
# Error: Service 'census' is not configured
# Solution: Add census_base_url to your settings
class Settings(BaseServiceSettings):
    census_base_url: str = Field(default="http://localhost:8001")
```

## Rollback Plan

If issues occur, you can quickly rollback:

1. Revert code changes (git revert)
2. Uninstall fundamentum: `pip uninstall fundamentum`
3. Restore temp/ folder
4. Restart service

## Success Criteria

✅ Service starts without errors  
✅ Logging works and includes request IDs  
✅ HTTP client can make requests  
✅ Error handling works correctly  
✅ Tests pass  
✅ No import errors  
✅ Settings validation works  

## Timeline Estimate

- Small service (< 10 files): 2-4 hours
- Medium service (10-30 files): 4-8 hours
- Large service (> 30 files): 1-2 days

Most time is spent on:
1. Updating imports (30%)
2. Updating settings (20%)
3. Updating client setup (20%)
4. Testing (30%)
