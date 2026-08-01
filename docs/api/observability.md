# Observability

Fundamentum provides structured JSON logging, request/response logging, an
optional metrics recorder, and optional OpenTelemetry tracing for FastAPI
services.

## Basic setup

```python
from fastapi import FastAPI

from fundamentum.infra.observability import (
    ObservabilityMiddleware,
    setup_logging,
    setup_tracing,
)

logger = setup_logging(settings)

app = FastAPI()
app.add_middleware(ObservabilityMiddleware)
setup_tracing(app, settings)  # requires fundamentum[otel]
```

Call `setup_tracing` once during application startup. It configures a tracer
provider with an OTLP/HTTP exporter, instruments FastAPI incoming requests and
HTTPX outgoing requests, and enables log correlation. The exporter reads its
target and credentials from standard `OTEL_*` environment variables, such as
`OTEL_EXPORTER_OTLP_ENDPOINT`.

Install tracing support separately when a service opts in:

```bash
pip install "fundamentum[otel]"
```

If the extra is not installed, importing Fundamentum still works; calling
`setup_tracing` raises an actionable `ImportError`.

## Trace context and spans

OpenTelemetry extracts incoming W3C `traceparent` headers and creates a server
span. The HTTPX instrumentation injects `traceparent` into outgoing calls,
including calls made through `ServiceClient`, creating child client spans with
the same trace ID. The span tree and cross-service relationships are therefore
available in the configured OTLP backend.

The old chained `X-Trace-ID` format and its context helpers are removed. The
middleware and `ServiceClient` no longer read or emit `X-Trace-ID`; no manual
trace header code is required.

For non-HTTP boundaries such as queues, use OpenTelemetry's `inject` and
`extract` APIs to carry context in message headers:

```python
from opentelemetry.propagate import extract, inject

headers: dict[str, str] = {}
inject(headers)
consumer_context = extract(message.headers)
```

## Structured logging

`ContextFilter` adds service metadata and the current span identifiers to each
JSON log record:

```json
{
  "service": "orders",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "message": "order loaded"
}
```

When no span is active, `trace_id` and `span_id` are `null`. This keeps logs
searchable by the same identifiers shown in the tracing backend.

## Middleware

`ObservabilityMiddleware` logs incoming requests, responses, and errors and
records an inbound request metric. It does not create or mutate trace headers;
that responsibility belongs to OpenTelemetry's FastAPI instrumentation.

```python
app.add_middleware(ObservabilityMiddleware)
```

The middleware recognizes `X-Service-Name` for peer-service attribution. The
HTTP client keeps sending that caller-identification header when configured.

## Logging helpers

```python
from fundamentum.infra.observability import (
    get_logger,
    log_http_request,
    log_http_response,
)

logger = get_logger(__name__)
log_http_request(
    logger,
    url_name="census.get_customer",
    peer_service="census",
    url="https://census.test/api/customers/123",
)
log_http_response(
    logger,
    url_name="census.get_customer",
    peer_service="census",
    status_code=200,
)
```

## Metrics

`infra.observability.metrics` exposes request duration through a pluggable
recorder. By default nothing is recorded. The optional Prometheus adapter
requires `fundamentum[metrics]`.

```python
from fundamentum.infra.observability.metrics import set_metrics_recorder
from fundamentum.infra.observability.prometheus import PrometheusMetricsRecorder

set_metrics_recorder(PrometheusMetricsRecorder())
```

## API reference

Functions:

- `setup_logging(settings) -> Logger`
- `setup_tracing(app, settings) -> None` (requires `fundamentum[otel]`)
- `get_logger(name) -> Logger`
- `set_metrics_recorder(recorder)` / `get_metrics_recorder()`
- `record_request(...)`

Classes:

- `ObservabilityMiddleware`
- `StructuredFormatter`
- `ContextFilter`
- `MetricsRecorder` / `NoopMetricsRecorder`
- `PrometheusMetricsRecorder` (requires `fundamentum[metrics]`)
