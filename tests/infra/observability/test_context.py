"""Tests for trace ID context management."""

import string

from fundamentum.infra.observability.context import (
    append_trace_segment,
    clear_trace_id,
    generate_trace_segment,
    get_trace_id,
    increment_trace_id,
    set_trace_id,
)


class TestTraceIdContext:
    """Focused tests for basic trace ID context operations."""

    def teardown_method(self) -> None:
        clear_trace_id()

    def test_set_get_and_clear(self) -> None:
        assert get_trace_id() is None

        set_trace_id("TRACE.ABCDE")
        assert get_trace_id() == "TRACE.ABCDE"

        clear_trace_id()
        assert get_trace_id() is None

    def test_set_overwrites_existing_value(self) -> None:
        set_trace_id("FIRST.AAA11")
        set_trace_id("SECOND.BBB22")
        assert get_trace_id() == "SECOND.BBB22"


class TestGenerateTraceSegment:
    """Minimal tests for segment generation guarantees."""

    def test_segment_length_and_charset(self) -> None:
        allowed_chars = set(string.ascii_uppercase + string.digits)
        segment = generate_trace_segment()
        assert len(segment) == 5
        assert all(char in allowed_chars for char in segment)

    def test_segments_are_statistically_unique(self) -> None:
        segments = [generate_trace_segment() for _ in range(50)]
        assert len(set(segments)) >= 45  # loose uniqueness check


class TestAppendTraceSegment:
    """Representative tests for append behavior."""

    def test_append_to_existing_trace(self) -> None:
        assert append_trace_segment("TRACE.AAA11", "BBB22") == "TRACE.AAA11.BBB22"

    def test_append_when_trace_is_none(self) -> None:
        assert append_trace_segment(None, "START") == "START"

    def test_auto_generated_segment_appends(self) -> None:
        result = append_trace_segment("TRACE.AAA11", None)
        parts = result.split(".")
        assert parts[0:2] == ["TRACE", "AAA11"]
        assert len(parts[2]) == 5


class TestIncrementTraceId:
    """Essential tests for increment logic."""

    def test_increment_existing_trace_adds_segment(self) -> None:
        result = increment_trace_id("TRACE.AAA11")
        parts = result.split(".")
        assert parts[0] == "TRACE"
        assert parts[1] == "AAA11"
        assert len(parts[2]) == 5

    def test_increment_without_incoming_creates_segment(self) -> None:
        assert len(increment_trace_id(None)) == 5

    def test_increment_with_custom_segment(self) -> None:
        assert increment_trace_id("TRACE.AAA11", "SERVICE") == "TRACE.AAA11.SERVICE"


class TestTraceIdIntegration:
    """End-to-end scenarios using the public helpers."""

    def test_full_request_flow(self) -> None:
        clear_trace_id()
        incoming = "TRACE.ROOT"
        new_trace = increment_trace_id(incoming, "EDGE")
        set_trace_id(new_trace)

        assert get_trace_id() == "TRACE.ROOT.EDGE"
        assert get_trace_id() == new_trace

    def test_multi_service_propagation(self) -> None:
        base_trace = "UICALL.START"

        service_a = increment_trace_id(base_trace, "SVC_A")
        service_b = increment_trace_id(service_a, "SVC_B")
        service_c = increment_trace_id(service_b)

        assert service_a == "UICALL.START.SVC_A"
        assert service_b == "UICALL.START.SVC_A.SVC_B"
        assert service_c.startswith("UICALL.START.SVC_A.SVC_B.")
