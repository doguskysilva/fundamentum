from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.models import (
    HttpMethod,
    RequestValidationError,
    ServiceEndpoint,
    ServiceError,
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
    UnresolvedPathParameterError,
)
from fundamentum.infra.http.registry import EndpointRegistry, get_global_registry

__all__ = [
    # Client
    "ServiceClient",
    # Models
    "HttpMethod",
    "ServiceEndpoint",
    # Exceptions
    "ServiceError",
    "ServiceNotFoundError",
    "ServiceTimeoutError",
    "ServiceUnavailableError",
    "RequestValidationError",
    "UnresolvedPathParameterError",
    # Registry
    "EndpointRegistry",
    "get_global_registry",
    # Testing
]
