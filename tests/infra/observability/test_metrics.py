"""Tests for the pluggable metrics recorder."""

import pytest

from fundamentum.infra.observability.metrics import (
    NoopMetricsRecorder,
    get_metrics_recorder,
    record_request,
    set_metrics_recorder,
)


@pytest.fixture(autouse=True)
def reset_recorder():
    original = get_metrics_recorder()
    yield
    set_metrics_recorder(original)


def test_default_recorder_is_noop():
    assert isinstance(get_metrics_recorder(), NoopMetricsRecorder)


def test_noop_recorder_accepts_calls_without_error():
    NoopMetricsRecorder().record_request(
        peer_service="census",
        method="GET",
        url_name="census.get_customer",
        status_code=200,
        duration_ms=42,
        direction="outbound",
    )


def test_set_metrics_recorder_installs_a_custom_recorder():
    events = []

    class RecordingRecorder:
        def record_request(self, **kwargs):
            events.append(kwargs)

    set_metrics_recorder(RecordingRecorder())
    record_request(
        peer_service="census",
        method="GET",
        url_name="census.get_customer",
        status_code=200,
        duration_ms=42,
        direction="outbound",
    )

    assert events == [
        {
            "peer_service": "census",
            "method": "GET",
            "url_name": "census.get_customer",
            "status_code": 200,
            "duration_ms": 42,
            "direction": "outbound",
        }
    ]


def test_prometheus_recorder_records_count_and_duration():
    prometheus_client = pytest.importorskip("prometheus_client")
    from fundamentum.infra.observability.prometheus import PrometheusMetricsRecorder

    recorder = PrometheusMetricsRecorder()
    recorder.record_request(
        peer_service="census",
        method="GET",
        url_name="census.get_customer",
        status_code=200,
        duration_ms=250,
        direction="outbound",
    )

    count = prometheus_client.REGISTRY.get_sample_value(
        "fundamentum_http_requests_total",
        {
            "peer_service": "census",
            "method": "GET",
            "url_name": "census.get_customer",
            "status_code": "200",
            "direction": "outbound",
        },
    )
    assert count == 1.0
