# Observability Module

Structured logging, request tracking, and middleware.

## Components

- **setup_logging** - Configure structured logging
- **ObservabilityMiddleware** - FastAPI middleware
- **Context Functions** - Request/trace ID management
- **Logging Helpers** - Structured log utilities

## Basic Usage

```python
from fastapi import FastAPI
from fundamentum.infra.observability import (
    setup_logging,
    ObservabilityMiddleware,
    get_logger,
)

# Setup logging
logger = setup_logging(settings)

# Add middleware
app = FastAPI()
app.add_middleware(ObservabilityMiddleware)

# Get logger
logger = get_logger(__name__)

@app.get("/customers/{customer_id}")
async def get_customer(customer_id: str):
    logger.info("Fetching customer", extra={"customer_id": customer_id})
    return {"id": customer_id}
```

## Logging

```python
from fundamentum.infra.observability import setup_logging, get_logger

# Setup once at startup
logger = setup_logging(settings)

# Get logger in modules
logger = get_logger(__name__)

# Structured logging with context
logger.info(
    "Customer created",
    extra={
        "customer_id": "123",
        "email": "john@example.com"
    }
)
```

## Trace ID (X-Trace-ID)

Fundamentum's own scheme: a chained trace ID that grows one segment per hop,
so the full call graph is reconstructable from the ID alone
(`UICALL.C32PO.V40PO.A1B2C`). Propagated via the `X-Trace-ID` header.

```python
from fundamentum.infra.observability import (
    get_trace_id,
    set_trace_id,
    increment_trace_id,
    clear_trace_id,
)

# Increment appends a new random segment to the incoming trace, or starts
# a fresh one if there is no incoming trace
incoming = None  # e.g. request.headers.get("X-Trace-ID")
trace_id = increment_trace_id(incoming)  # "V40PO"
set_trace_id(trace_id)

# Get current trace (from the context var set above)
trace_id = get_trace_id()

# Clear (cleanup / tests)
clear_trace_id()
```

`ObservabilityMiddleware` does this automatically for every request — see
below.

## W3C traceparent

Alongside `X-Trace-ID`, Fundamentum also propagates a standard
[W3C `traceparent`](https://www.w3.org/TR/trace-context/) header, so requests
show up correctly in standard tracing backends (Jaeger, Tempo, etc.) even
without a full OpenTelemetry SDK integration. Unlike `X-Trace-ID`, the
trace-id portion stays fixed for the whole call chain — only a fresh
parent-id (span-id) is generated per hop.

```python
from fundamentum.infra.observability import (
    generate_traceparent,
    get_traceparent,
    set_traceparent,
    parse_traceparent,
)

# Build the outgoing header for this hop, reusing the trace-id from an
# incoming traceparent if there is one
incoming = None  # e.g. request.headers.get("traceparent")
traceparent = generate_traceparent(incoming)
set_traceparent(traceparent)

# Get current value (from the context var set above)
traceparent = get_traceparent()

# Parse a raw header into (trace_id, parent_id), or None if malformed
parse_traceparent("00-" + "a" * 32 + "-" + "b" * 16 + "-01")
```

## Middleware

The middleware automatically:
- Extracts/increments `X-Trace-ID` for each request (see Trace ID above)
- Extracts/generates a `traceparent` header for each request (see W3C
  traceparent above)
- Adds both `X-Trace-ID` and `traceparent` to response headers
- Logs request/response details, including duration
- Records an inbound request metric via
  `fundamentum.infra.observability.metrics` (no-op unless a recorder is
  installed — see Metrics below)

```python
from fastapi import FastAPI
from fundamentum.infra.observability import ObservabilityMiddleware

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
```

## Logging Helpers

```python
from fundamentum.infra.observability import (
    log_http_request,
    log_http_response,
    get_logger,
)

logger = get_logger(__name__)

# Log outgoing HTTP request
log_http_request(
    logger,
    url_name="census.get_customer",
    peer_service="census",
    url="https://census.test/api/customers/123",
    method="GET",
)

# Log HTTP response
log_http_response(
    logger,
    url_name="census.get_customer",
    peer_service="census",
    status_code=200,
    method="GET",
    duration_ms=150,
    url="https://census.test/api/customers/123",
)
```

## Metrics

`infra.observability.metrics` exposes the request duration the middleware
and `ServiceClient` already compute, via a pluggable recorder. By default
nothing is recorded.

```python
from fundamentum.infra.observability.metrics import set_metrics_recorder

# Requires the `metrics` extra: fundamentum[metrics]
from fundamentum.infra.observability.prometheus import PrometheusMetricsRecorder

set_metrics_recorder(PrometheusMetricsRecorder())
```

Bring your own recorder by implementing `MetricsRecorder.record_request(...)`
— see `docs/api/testing.md` for how tests typically stub it out.

## API Reference

**Functions:**
- `setup_logging(settings) -> Logger` - Configure structured logging
- `get_logger(name) -> Logger` - Get logger with context
- `get_trace_id() -> str | None` - Current X-Trace-ID
- `set_trace_id(trace_id: str)` - Set X-Trace-ID
- `increment_trace_id(incoming, segment=None) -> str` - Append a segment to a trace ID
- `append_trace_segment(trace_id, segment=None) -> str` - Append a segment to a trace ID
- `generate_trace_segment() -> str` - Generate a random 5-char segment
- `clear_trace_id()` - Clear X-Trace-ID
- `get_traceparent() -> str | None` - Current W3C traceparent
- `set_traceparent(traceparent: str)` - Set W3C traceparent
- `generate_traceparent(incoming=None) -> str` - Build the outgoing traceparent for this hop
- `parse_traceparent(header: str) -> tuple[str, str] | None` - Parse into (trace_id, parent_id)
- `clear_traceparent()` - Clear traceparent
- `set_metrics_recorder(recorder)` / `get_metrics_recorder()` - Install/read the active `MetricsRecorder`
- `record_request(...)` - Forward a request event to the installed recorder

**Classes:**
- `ObservabilityMiddleware` - FastAPI/Starlette middleware
- `StructuredFormatter` - JSON log formatter
- `ContextFilter` - Adds trace context to logs
- `MetricsRecorder` (Protocol) / `NoopMetricsRecorder` - Pluggable metrics sink
- `PrometheusMetricsRecorder` (in `infra.observability.prometheus`, requires
  the `metrics` extra) - Publishes to the default Prometheus registry
