"""Observability middleware for request logging and monitoring."""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from fundamentum.infra.observability.helpers import (
    log_service_error,
    log_service_request,
    log_service_response,
)
from fundamentum.infra.observability.metrics import record_request

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request logging, metrics, and observability.

    Features:
    - Logs all incoming requests with duration and status
    - Records inbound request metrics

    OpenTelemetry's FastAPI instrumentation is responsible for extracting
    and creating W3C Trace Context spans when ``setup_tracing`` is enabled.
    """

    def __init__(
        self,
        app,
        *,
        service_name: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.logger = logger or logging.getLogger(__name__)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process a request and record observability information.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response from the downstream application
        """
        start_time = time.time()

        # Extract peer service from header or use "unknown"
        peer_service = request.headers.get("X-Service-Name", "unknown")

        # Determine url_name from path (you can customize this)
        url_name = request.url.path.lstrip("/").replace("/", ".")
        if not url_name:
            url_name = "root"

        # Log incoming request
        log_service_request(
            self.logger,
            url_name=url_name,
            peer_service=peer_service,
            path=request.url.path,
            method=request.method,
        )

        response = None
        status_code = 500  # Default to error if something goes wrong

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            log_service_error(
                self.logger,
                url_name=url_name,
                peer_service=peer_service,
                method=request.method,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            log_service_response(
                self.logger,
                url_name=url_name,
                peer_service=peer_service,
                method=request.method,
                status_code=status_code,
                duration_ms=duration_ms,
            )

            record_request(
                peer_service=peer_service,
                method=request.method,
                url_name=url_name,
                status_code=status_code,
                duration_ms=duration_ms,
                direction="inbound",
            )
