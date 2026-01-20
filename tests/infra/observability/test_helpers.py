"""Tests for observability logging helpers."""

import logging
from unittest.mock import MagicMock

from fundamentum.infra.observability.helpers import (
    log_http_request,
    log_http_response,
    log_service_request,
    log_service_response,
)


class TestLogHttpRequest:
    """Essential coverage for HTTP request logging."""

    def test_basic_request_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(
            logger,
            log_name="fetch_user",
            endpoint_name="get_user",
            url="https://api.example.com/users/123",
        )

        logger.info.assert_called_once_with(
            "http_request: fetch_user",
            extra={
                "data": {
                    "log_name": "fetch_user",
                    "endpoint": "get_user",
                    "url": "https://api.example.com/users/123",
                    "method": "GET",
                }
            },
        )

    def test_request_supports_custom_method_and_kwargs(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(
            logger,
            log_name="create_user",
            endpoint_name="post_user",
            url="https://api.example.com/users",
            method="POST",
            body={"name": "Ada"},
        )

        payload = logger.info.call_args.kwargs["extra"]["data"]
        assert payload["method"] == "POST"
        assert payload["body"] == {"name": "Ada"}


class TestLogHttpResponse:
    """Focused tests for HTTP response logging."""

    def test_success_response_logs_with_duration(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_response(
            logger,
            log_name="fetch_user",
            endpoint_name="get_user",
            url="https://api.example.com/users/123",
            status_code=200,
            method="GET",
            duration_ms=145,
        )

        logger.log.assert_called_once_with(
            logging.INFO,
            "http_response: fetch_user",
            extra={
                "data": {
                    "log_name": "fetch_user",
                    "endpoint": "get_user",
                    "url": "https://api.example.com/users/123",
                    "status_code": 200,
                    "method": "GET",
                    "duration_ms": 145,
                }
            },
        )

    def test_error_response_escalates_log_level(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_response(
            logger,
            log_name="fetch_user",
            endpoint_name="get_user",
            url="https://api.example.com/users/999",
            status_code=404,
            method="GET",
        )

        level, message = logger.log.call_args.args[:2]
        assert level == logging.ERROR
        assert message == "http_response: fetch_user"


class TestLogServiceRequest:
    """Representative tests for service request logging."""

    def test_basic_service_request_data(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_request(
            logger,
            log_name="process_update",
            endpoint="/api/users/123",
            origin_service="nuntius",
            method="PUT",
        )

        logger.info.assert_called_once_with(
            "service_request: process_update",
            extra={
                "data": {
                    "log_name": "process_update",
                    "endpoint": "/api/users/123",
                    "origin_service": "nuntius",
                    "method": "PUT",
                }
            },
        )

    def test_service_request_with_params_and_metadata(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_request(
            logger,
            log_name="create_order",
            endpoint="/api/orders",
            origin_service="order-service",
            method="POST",
            params={"order_id": "123"},
            user_id="user-456",
        )

        payload = logger.info.call_args.kwargs["extra"]["data"]
        assert payload["params"] == {"order_id": "123"}
        assert payload["user_id"] == "user-456"


class TestLogServiceResponse:
    """Tests for service response logging helper."""

    def test_basic_service_response_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_response(
            logger,
            log_name="request_completed",
            endpoint="/api/users",
            method="GET",
            status_code=200,
            service_name="profile",
            duration_ms=120,
        )

        level, message = logger.log.call_args.args[:2]
        assert level == logging.INFO
        assert message == "service_response: request_completed"

        payload = logger.log.call_args.kwargs["extra"]["data"]
        assert payload["service_name"] == "profile"
        assert payload["duration_ms"] == 120

    def test_error_response_escalates_level(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_response(
            logger,
            log_name="request_completed",
            endpoint="/api/users",
            method="GET",
            status_code=503,
        )

        level = logger.log.call_args.args[0]
        assert level == logging.ERROR


class TestHelperIntegration:
    """Lightweight integration checks."""

    def test_request_response_pair_shares_log_name(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(logger, "fetch", "endpoint", "url", "GET")
        log_http_response(logger, "fetch", "endpoint", "url", 200, "GET")

        request_log = logger.info.call_args.kwargs["extra"]["data"]
        response_log = logger.log.call_args.kwargs["extra"]["data"]
        assert request_log["log_name"] == response_log["log_name"]

    def test_all_helpers_emit_data_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(logger, "req", "endpoint", "url", "GET")
        assert "data" in logger.info.call_args.kwargs["extra"]

        logger.reset_mock()
        log_http_response(logger, "res", "endpoint", "url", 200, "GET")
        assert "data" in logger.log.call_args.kwargs["extra"]

        logger.reset_mock()
        log_service_request(logger, "svc", "/api", "origin", "GET")
        assert "data" in logger.info.call_args.kwargs["extra"]
