"""Tests for observability logging helpers."""

import logging
from unittest.mock import MagicMock

from fundamentum.infra.observability.helpers import (
    log_http_error,
    log_http_request,
    log_http_response,
    log_service_error,
    log_service_request,
    log_service_response,
)


class TestLogHttpRequest:
    """Essential coverage for HTTP request logging."""

    def test_basic_request_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(
            logger,
            url_name="census.customer.get",
            peer_service="census",
            url="https://api.example.com/users/123",
        )

        logger.info.assert_called_once_with(
            "http.client.request",
            extra={
                "data": {
                    "name": "http.client.request",
                    "direction": "outbound",
                    "peer_service": "census",
                    "url": "https://api.example.com/users/123",
                    "url_name": "census.customer.get",
                    "method": "GET",
                }
            },
        )

    def test_request_supports_custom_method_and_kwargs(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(
            logger,
            url_name="census.customer.create",
            peer_service="census",
            url="https://api.example.com/users",
            method="POST",
            body={"name": "Ada"},
        )

        payload = logger.info.call_args.kwargs["extra"]["data"]
        assert payload["name"] == "http.client.request"
        assert payload["method"] == "POST"
        assert payload["body"] == {"name": "Ada"}


class TestLogHttpResponse:
    """Focused tests for HTTP response logging."""

    def test_success_response_logs_with_duration(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_response(
            logger,
            url_name="census.customer.get",
            peer_service="census",
            status_code=200,
            method="GET",
            duration_ms=145,
        )

        logger.log.assert_called_once_with(
            logging.INFO,
            "http.client.response",
            extra={
                "data": {
                    "name": "http.client.response",
                    "direction": "inbound",
                    "peer_service": "census",
                    "method": "GET",
                    "url_name": "census.customer.get",
                    "status_code": 200,
                    "duration_ms": 145,
                }
            },
        )

    def test_error_response_escalates_log_level(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_response(
            logger,
            url_name="census.customer.get",
            peer_service="census",
            status_code=404,
            method="GET",
        )

        level, message = logger.log.call_args.args[:2]
        assert level == logging.ERROR
        assert message == "http.client.response"


class TestLogServiceRequest:
    """Representative tests for service request logging."""

    def test_basic_service_request_data(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_request(
            logger,
            url_name="customer.update",
            peer_service="nuntius",
            path="/api/users/123",
            method="PUT",
        )

        logger.info.assert_called_once_with(
            "http.server.request",
            extra={
                "data": {
                    "name": "http.server.request",
                    "direction": "inbound",
                    "peer_service": "nuntius",
                    "path": "/api/users/123",
                    "url_name": "customer.update",
                    "method": "PUT",
                }
            },
        )

    def test_service_request_with_params_and_metadata(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_request(
            logger,
            url_name="order.create",
            peer_service="order-service",
            path="/api/orders",
            method="POST",
            params={"order_id": "123"},
            user_id="user-456",
        )

        payload = logger.info.call_args.kwargs["extra"]["data"]
        assert payload["name"] == "http.server.request"
        assert payload["params"] == {"order_id": "123"}
        assert payload["user_id"] == "user-456"


class TestLogServiceResponse:
    """Tests for service response logging helper."""

    def test_basic_service_response_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_response(
            logger,
            url_name="customer.get",
            peer_service="nuntius",
            method="GET",
            status_code=200,
            duration_ms=120,
        )

        level, message = logger.log.call_args.args[:2]
        assert level == logging.INFO
        assert message == "http.server.response"

        payload = logger.log.call_args.kwargs["extra"]["data"]
        assert payload["name"] == "http.server.response"
        assert payload["peer_service"] == "nuntius"
        assert payload["duration_ms"] == 120

    def test_error_response_escalates_level(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_response(
            logger,
            url_name="customer.get",
            peer_service="nuntius",
            method="GET",
            status_code=503,
        )

        level = logger.log.call_args.args[0]
        assert level == logging.ERROR


class TestLogHttpError:
    """Tests for HTTP client error logging."""

    def test_http_error_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_error(
            logger,
            url_name="census.customer.get",
            peer_service="census",
            method="GET",
            error="Connection refused",
            error_type="ConnectionError",
        )

        logger.error.assert_called_once_with(
            "http.client.error",
            extra={
                "data": {
                    "name": "http.client.error",
                    "direction": "inbound",
                    "peer_service": "census",
                    "method": "GET",
                    "url_name": "census.customer.get",
                    "error": "Connection refused",
                    "error_type": "ConnectionError",
                }
            },
        )


class TestLogServiceError:
    """Tests for service error logging."""

    def test_service_error_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_service_error(
            logger,
            url_name="customer.update",
            peer_service="nuntius",
            method="PUT",
            error="Database error",
            error_type="DatabaseError",
        )

        logger.error.assert_called_once_with(
            "http.server.error",
            extra={
                "data": {
                    "name": "http.server.error",
                    "direction": "outbound",
                    "peer_service": "nuntius",
                    "method": "PUT",
                    "url_name": "customer.update",
                    "error": "Database error",
                    "error_type": "DatabaseError",
                }
            },
        )


class TestHelperIntegration:
    """Lightweight integration checks."""

    def test_request_response_pair_shares_url_name(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(logger, "census.customer.get", "census", "url", "GET")
        log_http_response(logger, "census.customer.get", "census", 200, "GET")

        request_log = logger.info.call_args.kwargs["extra"]["data"]
        response_log = logger.log.call_args.kwargs["extra"]["data"]
        assert request_log["url_name"] == response_log["url_name"]

    def test_all_helpers_emit_data_payload(self) -> None:
        logger = MagicMock(spec=logging.Logger)

        log_http_request(logger, "test", "peer", "url", "GET")
        assert "data" in logger.info.call_args.kwargs["extra"]

        logger.reset_mock()
        log_http_response(logger, "test", "peer", 200, "GET")
        assert "data" in logger.log.call_args.kwargs["extra"]

        logger.reset_mock()
        log_service_request(logger, "test", "peer", "/api", "GET")
        assert "data" in logger.info.call_args.kwargs["extra"]

        logger.reset_mock()
        log_service_response(logger, "test", "peer", "GET", 200)
        assert "data" in logger.log.call_args.kwargs["extra"]

        logger.reset_mock()
        log_http_error(logger, "test", "peer", "GET", "error", "ErrorType")
        assert "data" in logger.error.call_args.kwargs["extra"]

        logger.reset_mock()
        log_service_error(logger, "test", "peer", "GET", "error", "ErrorType")
        assert "data" in logger.error.call_args.kwargs["extra"]
