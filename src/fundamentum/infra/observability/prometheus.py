"""Prometheus adapter for `fundamentum.infra.observability.metrics`.

Requires the `metrics` extra (`fundamentum[metrics]`, which pulls in
`prometheus-client`). Importing this module without that extra installed
raises `ImportError` — it's never imported by the rest of the package, so
services that don't opt in never pay for it.
"""

try:
    from prometheus_client import Counter, Histogram
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "PrometheusMetricsRecorder requires the 'metrics' extra: "
        "install with `fundamentum[metrics]` (pulls in prometheus-client)."
    ) from exc

_REQUEST_COUNT = Counter(
    "fundamentum_http_requests_total",
    "Total HTTP requests observed by Fundamentum's HTTP client/middleware.",
    ["peer_service", "method", "url_name", "status_code", "direction"],
)

_REQUEST_DURATION = Histogram(
    "fundamentum_http_request_duration_seconds",
    "Duration of HTTP requests observed by Fundamentum's HTTP client/middleware.",
    ["peer_service", "method", "url_name", "direction"],
)


class PrometheusMetricsRecorder:
    """`MetricsRecorder` that publishes to the default Prometheus registry."""

    def record_request(
        self,
        *,
        peer_service: str,
        method: str,
        url_name: str,
        status_code: int,
        duration_ms: int,
        direction: str,
    ) -> None:
        _REQUEST_COUNT.labels(
            peer_service=peer_service,
            method=method,
            url_name=url_name,
            status_code=str(status_code),
            direction=direction,
        ).inc()
        _REQUEST_DURATION.labels(
            peer_service=peer_service,
            method=method,
            url_name=url_name,
            direction=direction,
        ).observe(duration_ms / 1000)
