"""Observability middleware and utilities for request tracking and monitoring.

This module provides FastAPI middleware for request tracing, logging,
and observability across microservices.
"""

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from fundamentum.infra.observability.context import (
    get_trace_id,
    increment_trace_id,
    set_trace_id,
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
        
        response = None
        status_code = 500  # Default to error if something goes wrong
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            logger.error(
                "request_error",
                extra={
                    "data": {
                        "log_name": "request_error",
                        "method": request.method,
                        "path": request.url.path,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                },
                exc_info=True,
            )
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request completion
            logger.info(
                "request_completed",
                extra={
                    "data": {
                        "log_name": "request_completed",
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
            
            # Add trace ID to response headers if response exists
            if response is not None:
                response.headers["X-Trace-ID"] = trace_id



