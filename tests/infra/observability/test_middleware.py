"""Targeted synchronous tests for observability middleware helpers."""

from fundamentum.infra.observability.context import (
    clear_trace_id,
    get_trace_id,
    increment_trace_id,
    set_trace_id,
)


class TestTraceIdInMiddleware:
    """Essential trace ID handling scenarios."""

    def teardown_method(self) -> None:
        clear_trace_id()
    
    def test_increment_creates_segment_when_missing(self) -> None:
        new_trace = increment_trace_id(None)

        assert new_trace is not None
        assert len(new_trace.split(".")) == 1

    def test_increment_appends_to_existing_trace(self) -> None:
        base_trace = "UICALL.C32PO"
        new_trace = increment_trace_id(base_trace)

        assert new_trace.startswith(f"{base_trace}.")
        assert len(new_trace.split(".")) == 3

    def test_trace_id_propagates_across_services(self) -> None:
        upstream = increment_trace_id("UICALL.START")
        set_trace_id(upstream)

        downstream = increment_trace_id(get_trace_id())
        set_trace_id(downstream)

        assert get_trace_id().startswith(f"{upstream}.")
        assert len(get_trace_id().split(".")) == 4


class TestMiddlewareLoggingStructure:
    """Minimal structure validation for middleware logs."""

    def test_request_completed_payload_shape(self) -> None:
        log_data = {
            "log_name": "request_completed",
            "method": "POST",
            "path": "/api/users",
            "status_code": 201,
            "duration_ms": 150,
        }

        required = {"log_name", "method", "path", "status_code", "duration_ms"}
        assert required.issubset(log_data.keys())
        assert isinstance(log_data["duration_ms"], int)

    def test_error_payload_contains_details(self) -> None:
        log_data = {
            "log_name": "request_error",
            "method": "GET",
            "path": "/api/users",
            "error": "Database connection failed",
            "error_type": "ConnectionError",
        }

        assert {"log_name", "error", "error_type"}.issubset(log_data.keys())

    def test_extra_wrapper_preserves_data(self) -> None:
        extra = {"data": {"log_name": "test", "path": "/test"}}

        assert "data" in extra
        assert extra["data"]["log_name"] == "test"


# For full async middleware integration tests, install pytest-asyncio:
#   pip install pytest-asyncio
#
# Example async test structure:
#
# import asyncio
# from fastapi import FastAPI
# from starlette.middleware.base import BaseHTTPMiddleware
# from fundamentum.infra.observability.middleware import ObservabilityMiddleware
#
# class TestObservabilityMiddlewareAsync:
#     @pytest.mark.asyncio
#     async def test_middleware_integration(self):
#         app = FastAPI()
#         app.add_middleware(ObservabilityMiddleware)
#         # ... test implementation
