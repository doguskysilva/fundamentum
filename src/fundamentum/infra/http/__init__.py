from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.models import (
    HttpMethod,
    ServiceEndpoint,
    ServiceError,
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
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
    # Registry
    "EndpointRegistry",
    "get_global_registry",
    # Testing
]
