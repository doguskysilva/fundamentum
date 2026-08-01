"""Pluggable request-metrics recording.

Fundamentum already computes request duration for logging (see
`infra.observability.helpers` and `infra.http.client`); this module gives
that data a second, structured outlet so services can wire it into whatever
metrics backend they use, without forcing that backend on every consumer.

By default nothing is recorded (`NoopMetricsRecorder`). Call
`set_metrics_recorder()` once at startup — e.g. with the Prometheus adapter
in `fundamentum.infra.observability.prometheus` (requires the `metrics`
extra: `fundamentum[metrics]`) — to start collecting.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class MetricsRecorder(Protocol):
    """Receives one event per HTTP request, inbound or outbound."""

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
        """Record a single completed request.

        Args:
            peer_service: Name of the other side of the call — the target
                service for outbound (client) requests, or the calling
                service for inbound (server) requests.
            method: HTTP method used.
            url_name: Logical endpoint name (e.g. 'census.get_customer').
            status_code: HTTP status code returned.
            duration_ms: Request duration in milliseconds.
            direction: 'outbound' for client calls, 'inbound' for server
                requests handled by this service.
        """
        ...


class NoopMetricsRecorder:
    """Default recorder: discards everything. Zero overhead, zero deps."""

    def record_request(self, **_kwargs: object) -> None:
        return None


_metrics_recorder: MetricsRecorder = NoopMetricsRecorder()


def set_metrics_recorder(recorder: MetricsRecorder) -> None:
    """Install the recorder used by `record_request` for the rest of the process."""
    global _metrics_recorder
    _metrics_recorder = recorder


def get_metrics_recorder() -> MetricsRecorder:
    """Return the currently installed recorder."""
    return _metrics_recorder


def record_request(
    *,
    peer_service: str,
    method: str,
    url_name: str,
    status_code: int,
    duration_ms: int,
    direction: str,
) -> None:
    """Forward a request event to the currently installed recorder."""
    _metrics_recorder.record_request(
        peer_service=peer_service,
        method=method,
        url_name=url_name,
        status_code=status_code,
        duration_ms=duration_ms,
        direction=direction,
    )
