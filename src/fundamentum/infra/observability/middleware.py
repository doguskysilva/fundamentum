"""Observability middleware and utilities for request tracking and monitoring.

This module provides FastAPI middleware for request tracing, logging,
and observability across microservices.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from fundamentum.infra.observability.context import (
    increment_trace_id,
    set_trace_id,
)
from fundamentum.infra.observability.helpers import (
    log_service_error,
    log_service_request,
    log_service_response,
)

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking, logging, and observability.
    
    Features:
    - Generates or increments trace IDs from headers
    - Logs all incoming requests with duration and status
    - Propagates trace ID through context variables
    - Adds trace ID to response headers
    
    The middleware automatically:
    - Extracts X-Trace-ID from headers and appends a new segment
    - If no X-Trace-ID exists, creates a new trace with generated segment
    - Stores trace ID in context variable for use in logging
    - Logs request completion with method, path, status, and duration
    - Adds X-Trace-ID to response headers for tracing
    
    Trace ID Flow:
    - UI calls service: 'UICALL.C32PO'
    - Service increments: 'UICALL.C32PO.V40PO'
    - Service calls another: sends 'UICALL.C32PO.V40PO'
    - Next service increments: 'UICALL.C32PO.V40PO.A1B2C'
    
    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(ObservabilityMiddleware)
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
        self, 
        request: Request, 
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request and add observability information.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler
            
        Returns:
            HTTP response with added observability headers
        """
        start_time = time.time()
        
        # Extract incoming trace ID and increment it with a new segment
        incoming_trace_id = request.headers.get("X-Trace-ID")
        trace_id = increment_trace_id(incoming_trace_id)
        set_trace_id(trace_id)
        
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
            
            # Add trace ID to response headers if response exists
            if response is not None:
                response.headers["X-Trace-ID"] = trace_id



