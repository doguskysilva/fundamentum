# Incremental Trace ID System

## Overview

The trace ID system implements an incremental chain where each service adds its own 5-character segment to track the request flow across microservices.

## Format

```
<origin>.<segment1>.<segment2>.<segment3>...
```

Each segment is a unique 5-character alphanumeric string (uppercase).

## Flow Example

### 1. UI calls Nuntius
```
Trace ID: UICALL.C32PO
```

### 2. Nuntius receives and increments
```
Incoming: UICALL.C32PO
Nuntius increments: UICALL.C32PO.V40PO

All logs within Nuntius use: UICALL.C32PO.V40PO
```

### 3. Nuntius calls Census
```
Nuntius sends: UICALL.C32PO.V40PO (passes current trace)
Census increments: UICALL.C32PO.V40PO.A1B2C

All logs within Census use: UICALL.C32PO.V40PO.A1B2C
```

### 4. Census calls another service
```
Census sends: UICALL.C32PO.V40PO.A1B2C
Service increments: UICALL.C32PO.V40PO.A1B2C.X9Y8Z
```

## Automatic Behavior

### Middleware (Receiving Requests)
The `ObservabilityMiddleware` automatically:
- Reads `X-Trace-ID` header from incoming request
- Appends a new 5-character segment
- Sets the incremented trace ID in context
- All logs in that request will use the same trace ID
- Adds the trace ID to the response headers

```python
# Happens automatically when middleware is installed
# No manual code needed in your endpoints
```

### HTTP Client (Making Requests)
The `ServiceClient` automatically:
- Reads current trace ID from context
- Adds `X-Trace-ID` header to outgoing request (doesn't increment)
- The receiving service will increment when it receives the request

```python
# Happens automatically when using ServiceClient
response = await client.get("census.customer_by_id", path_params={"id": "123"})
```

## Log Structure

Every log entry includes:

```json
{
  "level": "INFO",
  "logger": "my_service.handlers",
  "trace_id": "UICALL.C32PO.V40PO",
  "message": "Processing user",
  "data": {
    "log_name": "process_user",
    "user_id": "123"
  }
}
```

### HTTP Request Logs

```json
{
  "level": "INFO",
  "logger": "fundamentum.infra.http.client",
  "trace_id": "UICALL.C32PO.V40PO",
  "message": "http_request: request_census.customer_by_id",
  "data": {
    "log_name": "request_census.customer_by_id",
    "endpoint": "census.customer_by_id",
    "url": "http://census:8001/api/customers/123",
    "method": "GET"
  }
}
```

### HTTP Response Logs

```json
{
  "level": "INFO",
  "logger": "fundamentum.infra.http.client",
  "trace_id": "UICALL.C32PO.V40PO",
  "message": "http_response: request_census.customer_by_id",
  "data": {
    "log_name": "request_census.customer_by_id",
    "endpoint": "census.customer_by_id",
    "url": "http://census:8001/api/customers/123",
    "method": "GET",
    "status_code": 200,
    "duration_ms": 145
  }
}
```

### Service Request Logs (Incoming)

```json
{
  "level": "INFO",
  "logger": "my_service.handlers",
  "trace_id": "UICALL.C32PO.V40PO.A1B2C",
  "message": "service_request: process_customer_update",
  "data": {
    "log_name": "process_customer_update",
    "endpoint": "/api/customers/123",
    "origin_service": "nuntius",
    "method": "PUT",
    "params": {
      "name": "John Doe",
      "email": "john@example.com"
    }
  }
}
```

## Usage Examples

### Basic Logging in Your Service

```python
from fundamentum.infra.observability import get_logger

logger = get_logger(__name__)

# Simple log
logger.info("User processed", extra={"data": {"user_id": "123"}})

# With structured data
logger.info(
    "Order created",
    extra={
        "data": {
            "log_name": "create_order",
            "order_id": "abc-123",
            "customer_id": "456",
            "total": 99.99
        }
    }
)
```

### Logging HTTP Requests (Manual)

```python
from fundamentum.infra.observability import log_http_request, log_http_response, get_logger

logger = get_logger(__name__)

# When making request
log_http_request(
    logger,
    log_name="fetch_user_data",
    endpoint_name="get_user",
    url="https://api.example.com/users/123",
    method="GET"
)

# When response received
log_http_response(
    logger,
    log_name="fetch_user_data",
    endpoint_name="get_user",
    url="https://api.example.com/users/123",
    status_code=200,
    method="GET",
    duration_ms=145
)
```

Note: When using `ServiceClient`, HTTP request/response logging is automatic!

### Logging Service Requests (Incoming)

```python
from fundamentum.infra.observability import log_service_request, get_logger

logger = get_logger(__name__)

@app.post("/api/customers/{customer_id}")
async def update_customer(customer_id: str, data: CustomerUpdate):
    # Log incoming service request
    log_service_request(
        logger,
        log_name="update_customer",
        endpoint=f"/api/customers/{customer_id}",
        origin_service="nuntius",  # Or extract from headers/context
        method="POST",
        params=data.model_dump()
    )
    
    # Your business logic
    # ...
```

### Manual Trace ID Management (Advanced)

```python
from fundamentum.infra.observability import (
    get_trace_id,
    set_trace_id,
    generate_trace_segment,
    increment_trace_id
)

# Get current trace ID
current_trace = get_trace_id()  # e.g., "UICALL.C32PO.V40PO"

# Generate a new segment
segment = generate_trace_segment()  # e.g., "A1B2C"

# Manually increment (usually not needed, middleware does this)
new_trace = increment_trace_id(current_trace)  # e.g., "UICALL.C32PO.V40PO.K7M9N"

# Set trace ID (for background tasks)
set_trace_id("UICALL.C32PO.V40PO")
```

### Background Tasks

When spawning background tasks, preserve the trace ID:

```python
from fastapi import BackgroundTasks
from fundamentum.infra.observability import get_trace_id, set_trace_id, get_logger

logger = get_logger(__name__)

def background_task(trace_id: str, data: dict):
    # Restore trace ID in background context
    set_trace_id(trace_id)
    
    logger.info("Background task started", extra={"data": data})
    # Your background work...

@app.post("/api/process")
async def process_data(background_tasks: BackgroundTasks):
    # Capture current trace ID
    trace_id = get_trace_id()
    
    # Pass to background task
    background_tasks.add_task(background_task, trace_id, {"task": "process"})
    
    return {"status": "processing"}
```

## Setup

### 1. Install Middleware

```python
from fastapi import FastAPI
from fundamentum.infra.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

### 2. Setup Logging

```python
from fundamentum.infra.observability import setup_logging
from fundamentum.infra.settings.base import BaseServiceSettings

settings = BaseServiceSettings(
    service_name="my-service",
    enable_json_logging=True,
    log_level="INFO"
)

logger = setup_logging(settings)
```

### 3. Use ServiceClient for HTTP calls

```python
from fundamentum.infra.http.client import ServiceClient

client = ServiceClient(
    service_registry=service_registry,
    endpoint_registry=endpoint_registry
)

# Automatically propagates trace_id and logs requests/responses
response = await client.get("other-service.endpoint")
```

## Benefits

1. **Complete Request Tracing**: Follow a request through the entire microservice chain
2. **Automatic Propagation**: No manual trace ID management in most cases
3. **Consistent Logging**: All logs have the same structure
4. **Easy Debugging**: Search logs by trace ID to see the complete flow
5. **Performance Tracking**: See duration at each service hop
