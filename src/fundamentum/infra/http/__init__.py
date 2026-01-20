"""HTTP client and inter-service communication components.

This module provides a robust HTTP client for microservices communication,
including endpoint registry, service models, and error handling.

Example:
    >>> from fundamentum.infra.http import (
    ...     ServiceClient,
    ...     EndpointRegistry,
    ...     ServiceEndpoint,
    ...     HttpMethod,
    ... )
    >>> from fundamentum.infra.settings import ServiceRegistry
    >>> from pydantic import BaseModel
    >>> 
    >>> class CustomerResponse(BaseModel):
    ...     id: str
    ...     name: str
    >>> 
    >>> # Setup registries
    >>> endpoint_registry = EndpointRegistry()
    >>> endpoint_registry.register(
    ...     "census.customer_by_id",
    ...     ServiceEndpoint(
    ...         service="census",
    ...         path="/api/customers/{customer_id}",
    ...         method=HttpMethod.GET,
    ...         request_model=None,
    ...         response_model=CustomerResponse,
    ...     )
    ... )
    >>> 
    >>> # Create client
    >>> service_registry = ServiceRegistry(settings)
    >>> client = ServiceClient(service_registry, endpoint_registry)
    >>> 
    >>> # Make request
    >>> customer = await client.get(
    ...     "census.customer_by_id",
    ...     path_params={"customer_id": "123"}
    ... )
"""

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
]
