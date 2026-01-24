from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass(frozen=True)
class ServiceEndpoint:
    """Definition of a service endpoint for inter-service communication.
    
    This immutable data class defines all the information needed to make
    a request to another microservice endpoint.
    
    Attributes:
        service: Name of the target service (e.g., "census", "hermes")
        path: URL path for the endpoint (can include path parameters in braces)
        method: HTTP method to use
        request_model: Pydantic model for request body validation (None for GET/DELETE)
        response_model: Pydantic model for response body validation, or list[Model] for list responses
        timeout: Optional custom timeout for this endpoint (seconds)
    """
    
    service: str
    path: str
    method: HttpMethod
    request_model: type[BaseModel] | None
    response_model: type[BaseModel] | Any
    timeout: float | None = None
    
    def __post_init__(self) -> None:
        """Validate endpoint definition."""
        if not self.service:
            raise ValueError("service cannot be empty")
        if not self.path:
            raise ValueError("path cannot be empty")
        if not self.path.startswith("/"):
            raise ValueError("path must start with /")


class ServiceError(Exception):
    """Base exception for service communication errors."""
    
    def __init__(
        self, 
        message: str, 
        endpoint: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize service error.
        
        Args:
            message: Error message
            endpoint: Endpoint identifier that failed
            status_code: HTTP status code (if available)
            details: Additional error details
        """
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code
        self.details = details or {}


class ServiceNotFoundError(ServiceError):
    """Exception raised when a service or resource is not found (404)."""
    
    def __init__(self, message: str, endpoint: str | None = None):
        super().__init__(message, endpoint=endpoint, status_code=404)


class ServiceTimeoutError(ServiceError):
    """Exception raised when a service request times out."""
    
    def __init__(self, message: str, endpoint: str | None = None):
        super().__init__(message, endpoint=endpoint)


class ServiceUnavailableError(ServiceError):
    """Exception raised when a service is unavailable (5xx errors)."""
    
    def __init__(
        self, 
        message: str, 
        endpoint: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message, endpoint=endpoint, status_code=status_code)
