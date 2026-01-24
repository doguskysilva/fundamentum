from fundamentum.infra.settings import ServiceSettingsProtocol


class ServiceRegistry:
    """Registry for managing service base URLs.
    
    Automatically discovers services from settings fields ending with '_base_url'.
    Provides a clean interface for resolving service URLs by name.
    """
    
    def __init__(self, settings: ServiceSettingsProtocol):
        """Initialize the service registry with a settings object.
        
        Args:
            settings: Settings object containing service base URLs
        """
        self._settings = settings
        self._cache: dict[str, str] = {}
    
    def get_base_url(self, service_name: str) -> str:
        """Get base URL for a service by name.
        
        Args:
            service_name: Name of the service (e.g., "census", "hermes")
            
        Returns:
            Base URL for the service
            
        Raises:
            ValueError: If service is not configured in settings
        """
        
        if service_name in self._cache:
            return self._cache[service_name]
        
        field_name = f"{service_name.lower()}_base_url"
        
        if not hasattr(self._settings, field_name):
            available_services = self.list_services()
            raise ValueError(
                f"Service '{service_name}' is not configured. "
                f"Available services: {', '.join(available_services) or 'none'}"
            )
        
        url = getattr(self._settings, field_name)
        self._cache[service_name] = url
        return url
    
    def list_services(self) -> list[str]:
        """List all registered service names.
        
        Returns:
            List of service names that have base URLs configured
        """
        return [
            field.replace("_base_url", "")
            for field in dir(self._settings)
            if field.endswith("_base_url") and not field.startswith("_")
        ]
    
    def clear_cache(self) -> None:
        """Clear the internal URL cache.
        
        Use this if settings are updated dynamically and you need to
        reload service URLs.
        """
        self._cache.clear()
