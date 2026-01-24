"""Example: Setting up observability logging in a FastAPI microservice.

This example demonstrates how to configure and use the standardized
observability logging system across your microservice.
"""

from fastapi import FastAPI, Request
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.models import HttpMethod, ServiceEndpoint
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.observability.logging import setup_logging
from fundamentum.infra.observability.middleware import ObservabilityMiddleware
from fundamentum.infra.settings.registry import ServiceRegistry


# 1. Define your settings
class Settings(BaseSettings):
    """Service settings with observability configuration."""
    
    service_name: str = "nuntius"
    service_version: str = "v1.0.0"
    environment: str = "production"
    log_json: bool = True
    log_level: str = "INFO"
    
    # Other service URLs
    census_base_url: str = "http://census:8001"
    hermes_base_url: str = "http://hermes:8002"


# 2. Initialize settings and logging
settings = Settings()
logger = setup_logging(settings)


# 3. Create FastAPI app with observability middleware
app = FastAPI(title=settings.service_name, version=settings.service_version)

# Add observability middleware - this will automatically log all incoming requests
app.add_middleware(
    ObservabilityMiddleware,
    service_name=settings.service_name,
)


# 4. Set up HTTP client for inter-service communication
service_registry = ServiceRegistry(settings)
endpoint_registry = EndpointRegistry()

# Register external service endpoints
endpoint_registry.register(
    "census.customer.get",
    ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=dict,  # Replace with actual Pydantic model
    ),
)

http_client = ServiceClient(
    service_registry=service_registry,
    endpoint_registry=endpoint_registry,
)


# 5. Define your API endpoints
class NotificationRequest(BaseModel):
    customer_id: str
    message: str


@app.post("/api/notifications")
async def send_notification(request: NotificationRequest):
    """Send a notification to a customer.
    
    This endpoint will automatically generate the following logs:
    
    1. http.server.request - When request is received (by middleware)
    2. http.client.request - Before calling Census service (by ServiceClient)
    3. http.client.response - After Census responds (by ServiceClient)
    4. http.server.response - When response is sent (by middleware)
    
    All logs will share the same trace_id for correlation.
    """
    
    # Call another service - logging happens automatically
    customer = await http_client.get(
        "census.customer.get",
        path_params={"customer_id": request.customer_id},
    )
    
    # Your business logic here
    # ...
    
    return {"status": "sent", "customer": customer}


# 6. Example: Manual logging for custom events (optional)
from fundamentum.infra.observability.helpers import log_service_request

@app.middleware("http")
async def add_service_header(request: Request, call_next):
    """Add X-Service-Name header to outgoing requests."""
    # Add our service name to headers for peer identification
    request.state.service_name = settings.service_name
    response = await call_next(request)
    return response


# Example log output for a request:
"""
# 1. Middleware logs incoming request
{
  "timestamp": "2026-01-24T15:04:12.123Z",
  "level": "INFO",
  "logger": "fundamentum.infra.observability.middleware",
  "trace_id": "CLI.ABC12.DEF34",
  "service": "nuntius",
  "version": "v1.0.0",
  "environment": "production",
  "data": {
    "name": "http.server.request",
    "direction": "inbound",
    "peer_service": "api-gateway",
    "method": "POST",
    "path": "/api/notifications",
    "url_name": "api.notifications"
  }
}

# 2. ServiceClient logs outbound request to Census
{
  "timestamp": "2026-01-24T15:04:12.145Z",
  "level": "INFO",
  "logger": "fundamentum.infra.http.client",
  "trace_id": "CLI.ABC12.DEF34",
  "service": "nuntius",
  "version": "v1.0.0",
  "environment": "production",
  "data": {
    "name": "http.client.request",
    "direction": "outbound",
    "peer_service": "census",
    "method": "GET",
    "url": "http://census:8001/api/customers/123",
    "url_name": "census.customer.get"
  }
}

# 3. ServiceClient logs response from Census
{
  "timestamp": "2026-01-24T15:04:12.187Z",
  "level": "INFO",
  "logger": "fundamentum.infra.http.client",
  "trace_id": "CLI.ABC12.DEF34",
  "service": "nuntius",
  "version": "v1.0.0",
  "environment": "production",
  "data": {
    "name": "http.client.response",
    "direction": "inbound",
    "peer_service": "census",
    "method": "GET",
    "url_name": "census.customer.get",
    "status_code": 200,
    "duration_ms": 42
  }
}

# 4. Middleware logs outbound response
{
  "timestamp": "2026-01-24T15:04:12.234Z",
  "level": "INFO",
  "logger": "fundamentum.infra.observability.middleware",
  "trace_id": "CLI.ABC12.DEF34",
  "service": "nuntius",
  "version": "v1.0.0",
  "environment": "production",
  "data": {
    "name": "http.server.response",
    "direction": "outbound",
    "peer_service": "api-gateway",
    "method": "POST",
    "url_name": "api.notifications",
    "status_code": 200,
    "duration_ms": 112
  }
}
"""


# Querying examples:
"""
# Find all services Nuntius calls:
service:nuntius AND data.name:http.client.request

# Find all services that call Nuntius:
service:nuntius AND data.name:http.server.request

# Get Nuntius performance metrics:
service:nuntius AND data.name:http.server.response
# Then aggregate data.duration_ms and data.status_code

# Find errors in Nuntius → Census communication:
service:nuntius AND data.peer_service:census AND data.name:*error*
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
