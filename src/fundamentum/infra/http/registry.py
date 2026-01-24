
from fundamentum.infra.http.models import ServiceEndpoint


class EndpointRegistry:
    """Registry for managing service endpoint definitions.
    
    Provides a centralized place to define and access service endpoints.
    Supports hierarchical naming (e.g., "census.customer_by_id") and
    validation of endpoint definitions.
    """
    
    def __init__(self) -> None:
        """Initialize an empty endpoint registry."""
        self._endpoints: dict[str, ServiceEndpoint] = {}
    
    def register(self, key: str, endpoint: ServiceEndpoint) -> None:
        """Register a service endpoint.
        
        Args:
            key: Unique identifier for the endpoint (e.g., "census.customer_by_id")
            endpoint: ServiceEndpoint definition
            
        Raises:
            ValueError: If key is empty or endpoint is already registered
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
        """
        return key in self._endpoints
    
    def list_keys(self) -> list[str]:
        """List all registered endpoint keys.
        
        Returns:
            List of endpoint identifiers
        """
        return list(self._endpoints.keys())
    
    def list_by_service(self, service: str) -> dict[str, ServiceEndpoint]:
        """List all endpoints for a specific service.
        
        Args:
            service: Service name
            
        Returns:
            Dictionary of endpoint keys and definitions for the service
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
        """
        if key not in self._endpoints:
            raise KeyError(f"Endpoint '{key}' not found")
        
        del self._endpoints[key]
    
    def clear(self) -> None:
        """Remove all endpoints from the registry.
        
        Useful for testing or reconfiguration.
        """
        self._endpoints.clear()
    
    def bulk_register(self, endpoints: dict[str, ServiceEndpoint]) -> None:
        """Register multiple endpoints at once.
        
        Args:
            endpoints: Dictionary of endpoint keys and definitions
            
        Raises:
            ValueError: If any key is already registered
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
    """
    return _global_registry
