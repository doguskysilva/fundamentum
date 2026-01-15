from typing import Dict

from fundamentum.infra.http.models import ServiceEndpoint


class EndpointRegistry:
    """Registry for managing service endpoint definitions.
    
    Provides a centralized place to define and access service endpoints.
    Supports hierarchical naming (e.g., "census.customer_by_id") and
    validation of endpoint definitions.
    
    Example:
        >>> from fundamentum.infra.http.models import HttpMethod, ServiceEndpoint
        >>> from pydantic import BaseModel
        >>> 
        >>> class CustomerResponse(BaseModel):
        ...     id: str
        ...     name: str
        ... 
        >>> registry = EndpointRegistry()
        >>> registry.register(
        ...     "census.customer_by_id",
        ...     ServiceEndpoint(
        ...         service="census",
        ...         path="/api/customers/{customer_id}",
        ...         method=HttpMethod.GET,
        ...         request_model=None,
        ...         response_model=CustomerResponse,
        ...     )
        ... )
        >>> endpoint = registry.get("census.customer_by_id")
    """
    
    def __init__(self) -> None:
        """Initialize an empty endpoint registry."""
        self._endpoints: Dict[str, ServiceEndpoint] = {}
    
    def register(self, key: str, endpoint: ServiceEndpoint) -> None:
        """Register a service endpoint.
        
        Args:
            key: Unique identifier for the endpoint (e.g., "census.customer_by_id")
            endpoint: ServiceEndpoint definition
            
        Raises:
            ValueError: If key is empty or endpoint is already registered
            
        Example:
            >>> registry.register("census.list_customers", endpoint)
        """
        if not key:
            raise ValueError("Endpoint key cannot be empty")
        
        if key in self._endpoints:
            raise ValueError(f"Endpoint '{key}' is already registered")
        
        self._endpoints[key] = endpoint
    
    def get(self, key: str) -> ServiceEndpoint:
        """Get a service endpoint by key.
        
        Args:
            key: Endpoint identifier
            
        Returns:
            ServiceEndpoint definition
            
        Raises:
            KeyError: If endpoint is not found
            
        Example:
            >>> endpoint = registry.get("census.customer_by_id")
        """
        if key not in self._endpoints:
            available = ", ".join(self.list_keys())
            raise KeyError(
                f"Endpoint '{key}' not found. "
                f"Available endpoints: {available or 'none'}"
            )
        
        return self._endpoints[key]
    
    def has(self, key: str) -> bool:
        """Check if an endpoint is registered.
        
        Args:
            key: Endpoint identifier
            
        Returns:
            True if endpoint exists, False otherwise
            
        Example:
            >>> if registry.has("census.customer_by_id"):
            ...     endpoint = registry.get("census.customer_by_id")
        """
        return key in self._endpoints
    
    def list_keys(self) -> list[str]:
        """List all registered endpoint keys.
        
        Returns:
            List of endpoint identifiers
            
        Example:
            >>> keys = registry.list_keys()
            >>> print(keys)
            ['census.customer_by_id', 'hermes.send_email']
        """
        return list(self._endpoints.keys())
    
    def list_by_service(self, service: str) -> Dict[str, ServiceEndpoint]:
        """List all endpoints for a specific service.
        
        Args:
            service: Service name
            
        Returns:
            Dictionary of endpoint keys and definitions for the service
            
        Example:
            >>> census_endpoints = registry.list_by_service("census")
            >>> for key, endpoint in census_endpoints.items():
            ...     print(f"{key}: {endpoint.path}")
        """
        return {
            key: endpoint
            for key, endpoint in self._endpoints.items()
            if endpoint.service == service
        }
    
    def unregister(self, key: str) -> None:
        """Remove an endpoint from the registry.
        
        Args:
            key: Endpoint identifier
            
        Raises:
            KeyError: If endpoint is not found
            
        Example:
            >>> registry.unregister("census.customer_by_id")
        """
        if key not in self._endpoints:
            raise KeyError(f"Endpoint '{key}' not found")
        
        del self._endpoints[key]
    
    def clear(self) -> None:
        """Remove all endpoints from the registry.
        
        Useful for testing or reconfiguration.
        
        Example:
            >>> registry.clear()
        """
        self._endpoints.clear()
    
    def bulk_register(self, endpoints: Dict[str, ServiceEndpoint]) -> None:
        """Register multiple endpoints at once.
        
        Args:
            endpoints: Dictionary of endpoint keys and definitions
            
        Raises:
            ValueError: If any key is already registered
            
        Example:
            >>> endpoints = {
            ...     "census.customer_by_id": endpoint1,
            ...     "census.list_customers": endpoint2,
            ... }
            >>> registry.bulk_register(endpoints)
        """
        # Validate all keys first
        conflicts = [key for key in endpoints if key in self._endpoints]
        if conflicts:
            raise ValueError(
                f"Cannot register endpoints: already registered: {', '.join(conflicts)}"
            )
        
        # Register all endpoints
        self._endpoints.update(endpoints)


# Global endpoint registry instance
_global_registry = EndpointRegistry()


def get_global_registry() -> EndpointRegistry:
    """Get the global endpoint registry instance.
    
    Returns:
        Global EndpointRegistry instance
        
    Example:
        >>> from fundamentum.infra.http.registry import get_global_registry
        >>> registry = get_global_registry()
        >>> registry.register("my_service.endpoint", endpoint)
    """
    return _global_registry
