# Observability Logging Changes Summary

## What Changed

Restructured all logging to follow a standardized observability pattern with consistent event names and field structures across microservices.

## Key Changes

### 1. Standardized Event Names

**Client-side (outbound → inbound):**
- `http.client.request` - Before making HTTP request to another service
- `http.client.response` - After receiving response from another service
- `http.client.error` - When HTTP request fails

**Server-side (inbound → outbound):**
- `http.server.request` - When receiving HTTP request
- `http.server.response` - When sending HTTP response
- `http.server.error` - When request processing fails

### 2. Consistent Data Structure

All events now include:
```json
{
  "name": "event.name",
  "direction": "inbound | outbound",
  "peer_service": "<other-service-name>",
  "method": "GET | POST | ...",
  "url_name": "<logical-endpoint-name>"
}
```

### 3. Base Log Structure

Every log includes:
```json
{
  "timestamp": "2026-01-24T15:04:12.123Z",
  "level": "INFO",
  "logger": "module.name",
  "trace_id": "CLI.ABC.DEF",
  "service": "service-name",
  "version": "v1.0.0",
  "environment": "production",
  "data": { /* event-specific */ }
}
```

## Modified Files

### Core Modules
- `src/fundamentum/infra/observability/helpers.py`
  - Updated all logging helpers with new signatures
  - Added `log_http_error()` and `log_service_error()`
  
- `src/fundamentum/infra/observability/logging.py`
  - Updated `StructuredFormatter` to include service, version, environment fields

- `src/fundamentum/infra/observability/middleware.py`
  - Updated to use new event structure
  - Extracts `X-Service-Name` header for peer service identification
  - Logs `http.server.request`, `http.server.response`, and `http.server.error`

- `src/fundamentum/infra/http/client.py`
  - Updated to use new logging helpers
  - Logs `http.client.request`, `http.client.response`, and `http.client.error`

### Tests
- Updated all test files to match new structure
- All 98 tests passing

## Migration Guide

### Before:
```python
log_http_request(
    logger,
    log_name="fetch_user",
    endpoint_name="get_user",
    url="https://api.census.com/users/123",
    method="GET"
)
```

### After:
```python
log_http_request(
    logger,
    url_name="census.customer.get",
    peer_service="census",
    url="https://api.census.com/users/123",
    method="GET"
)
```

## Querying Examples

### Find all services that Service A calls:
```
service:serviceA AND data.name:http.client.request
```

### Find all response statuses Service A receives:
```
service:serviceA AND data.name:http.client.response
```
Aggregate by `data.status_code`.

### Find all services calling Service B:
```
service:serviceB AND data.name:http.server.request
```
Group by `data.peer_service`.

### Find Service B response metrics:
```
service:serviceB AND data.name:http.server.response
```
Aggregate `data.duration_ms` and `data.status_code`.

### Find errors between Service A and Service B:
```
(service:serviceA AND data.peer_service:serviceB) OR 
(service:serviceB AND data.peer_service:serviceA) 
AND data.name:*error*
```

## Benefits

1. **Consistent Structure**: All logs follow the same pattern
2. **Easy Filtering**: Standard field names enable predictable queries
3. **Direction Clarity**: Explicit inbound/outbound tracking
4. **Service Mapping**: Easy to build service dependency graphs
5. **Performance Tracking**: Duration and status metrics built-in
6. **Error Correlation**: Standardized error events with context
7. **Trace Propagation**: Trace IDs connect entire request chains

## Documentation

See [OBSERVABILITY.md](OBSERVABILITY.md) for complete documentation including:
- Detailed event schemas
- Usage examples
- Querying patterns
- Best practices
- Full request flow examples
