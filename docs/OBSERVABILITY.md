# Observability Logging Structure

## Overview

This document describes the standardized logging structure for observability across microservices. All logs follow a consistent format with predictable event names and field structures.

## Base Log Structure

Every log entry includes these base fields:

```json
{
  "timestamp": "2026-01-24T15:04:12.123Z",
  "level": "INFO",
  "logger": "fundamentum.http.client",
  "trace_id": "CLI.NUNTIUS.0003",
  "service": "nuntius",
  "version": "v0.3.1",
  "environment": "production",
  "data": { }
}
```

The `data` field contains event-specific information structured according to the event type.

## Event Types

### 1. HTTP Client Request (Outbound)

Logged when a service **makes** an HTTP request to another service.

**Event Name:** `http.client.request`

```json
{
  "data": {
    "name": "http.client.request",
    "direction": "outbound",
    "peer_service": "census",
    "method": "GET",
    "url": "http://census:8001/api/customers/123",
    "url_name": "census.customer.get"
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_http_request

log_http_request(
    logger,
    url_name="census.customer.get",
    peer_service="census",
    url="http://census:8001/api/customers/123",
    method="GET",
)
```

### 2. HTTP Server Request (Inbound)

Logged when a service **receives** an HTTP request from another service.

**Event Name:** `http.server.request`

```json
{
  "data": {
    "name": "http.server.request",
    "direction": "inbound",
    "peer_service": "nuntius",
    "method": "GET",
    "path": "/api/customers/123",
    "url_name": "customer.get"
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_service_request

log_service_request(
    logger,
    url_name="customer.get",
    peer_service="nuntius",
    path="/api/customers/123",
    method="GET",
)
```

### 3. HTTP Server Response (Outbound)

Logged when a service **returns** a response to a caller.

**Event Name:** `http.server.response`

```json
{
  "data": {
    "name": "http.server.response",
    "direction": "outbound",
    "peer_service": "nuntius",
    "method": "GET",
    "url_name": "customer.get",
    "status_code": 200,
    "duration_ms": 42
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_service_response

log_service_response(
    logger,
    url_name="customer.get",
    peer_service="nuntius",
    method="GET",
    status_code=200,
    duration_ms=42,
)
```

### 4. HTTP Client Response (Inbound)

Logged when a service **receives** a response from another service.

**Event Name:** `http.client.response`

```json
{
  "data": {
    "name": "http.client.response",
    "direction": "inbound",
    "peer_service": "census",
    "method": "GET",
    "url_name": "census.customer.get",
    "status_code": 200,
    "duration_ms": 45
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_http_response

log_http_response(
    logger,
    url_name="census.customer.get",
    peer_service="census",
    status_code=200,
    method="GET",
    duration_ms=45,
)
```

### 5. HTTP Client Error

Logged when an HTTP client request fails.

**Event Name:** `http.client.error`

```json
{
  "data": {
    "name": "http.client.error",
    "direction": "inbound",
    "peer_service": "census",
    "method": "GET",
    "url_name": "census.customer.get",
    "error": "Connection refused",
    "error_type": "ConnectionError",
    "status_code": 503
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_http_error

log_http_error(
    logger,
    url_name="census.customer.get",
    peer_service="census",
    method="GET",
    error="Connection refused",
    error_type="ConnectionError",
    status_code=503,
)
```

### 6. HTTP Server Error

Logged when a service encounters an error while processing a request.

**Event Name:** `http.server.error`

```json
{
  "data": {
    "name": "http.server.error",
    "direction": "outbound",
    "peer_service": "nuntius",
    "method": "POST",
    "url_name": "customer.create",
    "error": "Database connection failed",
    "error_type": "DatabaseError"
  }
}
```

**Usage:**
```python
from fundamentum.infra.observability.helpers import log_service_error

log_service_error(
    logger,
    url_name="customer.create",
    peer_service="nuntius",
    method="POST",
    error="Database connection failed",
    error_type="DatabaseError",
)
```

## Required Fields

All events **must** include these fields in the `data` object:

- `name`: Event type identifier (e.g., `http.client.request`)
- `direction`: `inbound` or `outbound`
- `peer_service`: Name of the other service involved
- `method`: HTTP method (GET, POST, PUT, DELETE, PATCH)
- `url_name`: Logical endpoint identifier

## Querying Patterns

### Find all services that Service A calls

```
service:serviceA AND data.name:http.client.request
```

Or group by `peer_service`:
```
service:serviceA AND data.direction:outbound AND data.name:*client*
```

### Find all response statuses that Service A receives

```
service:serviceA AND data.name:http.client.response
```

Aggregate by `status_code`.

### Find all services that call Service B

```
service:serviceB AND data.name:http.server.request
```

Group by `peer_service`.

### Find all response metrics Service B produced

```
service:serviceB AND data.name:http.server.response
```

Aggregate `duration_ms` and `status_code` for latency and success metrics.

### Find all errors involving Service A and Service B

```
(service:serviceA AND data.peer_service:serviceB) AND data.name:*error*
```

## Trace ID Propagation

Every request carries a `trace_id` that grows as it passes through services:

1. **Client initiates**: `CLI.A1B2C`
2. **Service A increments**: `CLI.A1B2C.D3F4G`
3. **Service A → Service B**: Sends `CLI.A1B2C.D3F4G`
4. **Service B increments**: `CLI.A1B2C.D3F4G.H5I6J`

All log entries within the same request chain share a common prefix, enabling end-to-end tracing.

## Middleware Integration

The `ObservabilityMiddleware` automatically logs `http.server.request` and `http.server.response` events for every incoming request:

```python
from fastapi import FastAPI
from fundamentum.infra.observability.middleware import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware, service_name="census")
```

The middleware will:
- Extract `X-Service-Name` header to identify the caller
- Increment the `X-Trace-ID` header
- Log incoming requests and responses automatically
- Propagate trace ID to response headers

## ServiceClient Integration

The `ServiceClient` automatically logs `http.client.request` and `http.client.response` events:

```python
from fundamentum.infra.http.client import ServiceClient

client = ServiceClient(service_registry, endpoint_registry)

# This will automatically log:
# - http.client.request (before sending)
# - http.client.response (after receiving)
# - http.client.error (on failure)
response = await client.get("census.customer.get", path_params={"id": "123"})
```

## Best Practices

1. **Always use helpers**: Don't log manually; use the provided helper functions to ensure consistency.

2. **Meaningful url_name**: Use hierarchical names like `service.resource.action` (e.g., `census.customer.get`).

3. **Include peer_service**: Always identify the other party in the communication.

4. **Add context**: Use `**kwargs` to add relevant metadata (user_id, request_id, etc.).

5. **Propagate trace_id**: Ensure `X-Trace-ID` header is passed in all HTTP calls.

6. **Identify caller**: Send `X-Service-Name` header to help the receiving service log the peer.

## Example: Full Request Flow

### Service A (Nuntius) calls Service B (Census)

#### 1. Service A logs outbound request:
```json
{
  "service": "nuntius",
  "trace_id": "CLI.ABC12.DEF34",
  "data": {
    "name": "http.client.request",
    "direction": "outbound",
    "peer_service": "census",
    "method": "GET",
    "url_name": "census.customer.get"
  }
}
```

#### 2. Service B logs inbound request:
```json
{
  "service": "census",
  "trace_id": "CLI.ABC12.DEF34.GHI56",
  "data": {
    "name": "http.server.request",
    "direction": "inbound",
    "peer_service": "nuntius",
    "method": "GET",
    "url_name": "customer.get"
  }
}
```

#### 3. Service B logs outbound response:
```json
{
  "service": "census",
  "trace_id": "CLI.ABC12.DEF34.GHI56",
  "data": {
    "name": "http.server.response",
    "direction": "outbound",
    "peer_service": "nuntius",
    "method": "GET",
    "url_name": "customer.get",
    "status_code": 200,
    "duration_ms": 42
  }
}
```

#### 4. Service A logs inbound response:
```json
{
  "service": "nuntius",
  "trace_id": "CLI.ABC12.DEF34",
  "data": {
    "name": "http.client.response",
    "direction": "inbound",
    "peer_service": "census",
    "method": "GET",
    "url_name": "census.customer.get",
    "status_code": 200,
    "duration_ms": 45
  }
}
```

All four events share the trace prefix `CLI.ABC12.DEF34`, enabling correlation.
