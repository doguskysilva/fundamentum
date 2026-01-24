# Before & After Comparison

## Settings Management

### Before (`temp/settings.py`)
```python
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="", env_file=".env")
    service_name: str = Field(default="nuntius")
    service_version: str = Field(default="dev", ...)
    environment: str = Field(default="development", ...)
    census_base_url: str = Field(default="http://localhost:8081", ...)

settings = Settings()
```

**Issues:**
- ❌ Not reusable across services
- ❌ Hardcoded service name
- ❌ Limited configuration options
- ❌ No logging configuration
- ❌ Global instance couples code

### After (`infra/settings/base.py`)
```python
class BaseServiceSettings(BaseSettings):
    """Base settings class for microservices."""
    
    model_config = ConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    service_name: str = Field(..., description="Name of the microservice")
    service_version: str = Field(default="dev", validation_alias="VERSION")
    environment: Literal["development", "staging", "production"] = Field(...)
    log_level: str = Field(default="INFO", ...)
    enable_json_logging: bool = Field(default=True, ...)
    http_timeout: float = Field(default=10.0, gt=0, ...)
    http_retry_attempts: int = Field(default=3, ge=0, ...)
```

**Improvements:**
- ✅ Reusable base class for all services
- ✅ Service name as required parameter
- ✅ More configuration options
- ✅ Better type hints with Literal
- ✅ Comprehensive validation
- ✅ Extensive documentation

## Service Resolution

### Before (`temp/http/service_resolver.py`)
```python
from app.core.settings import settings

def base_url(service_name: str) -> str:
    field_name = f"{service_name.lower()}_base_url"
    
    if not hasattr(settings, field_name):
        available_services = [...]
        raise ValueError(f"Service '{service_name}' is not configured...")
    
    return getattr(settings, field_name)
```

**Issues:**
- ❌ Tightly coupled to global settings
- ❌ No caching
- ❌ Function-based API
- ❌ Hard to test

### After (`infra/settings/registry.py`)
```python
class ServiceRegistry:
    """Registry for managing service base URLs."""
    
    def __init__(self, settings: ServiceSettingsProtocol):
        self._settings = settings
        self._cache: dict[str, str] = {}
    
    def get_base_url(self, service_name: str) -> str:
        """Get base URL for a service by name."""
        if service_name in self._cache:
            return self._cache[service_name]
        
        field_name = f"{service_name.lower()}_base_url"
        if not hasattr(self._settings, field_name):
            available_services = self.list_services()
            raise ValueError(...)
        
        url = getattr(self._settings, field_name)
        self._cache[service_name] = url
        return url
    
    def list_services(self) -> list[str]: ...
    def clear_cache(self) -> None: ...
```

**Improvements:**
- ✅ Dependency injection (testable)
- ✅ Caching for performance
- ✅ Class-based API
- ✅ Additional utility methods
- ✅ Better error messages

## HTTP Client

### Before (`temp/http/service_client.py`)
```python
class ServiceClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
    
    async def get(
        self,
        endpoint_key: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if endpoint_key not in SERVICE_ENDPOINTS:
            raise ValueError(...)
        
        endpoint = SERVICE_ENDPOINTS[endpoint_key]
        url = self._build_url(endpoint_key, path_params)
        
        # Build headers...
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, ...)
            response.raise_for_status()
            return response.json() if response.content else None
```

**Issues:**
- ❌ Only supports GET method
- ❌ Returns dict instead of validated models
- ❌ Coupled to global SERVICE_ENDPOINTS
- ❌ Limited error handling
- ❌ No response validation
- ❌ Hardcoded timeout

### After (`infra/http/client.py`)
```python
class ServiceClient:
    """Async HTTP client for inter-service communication."""
    
    def __init__(
        self,
        service_registry: ServiceRegistry,
        endpoint_registry: EndpointRegistry,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        self.service_registry = service_registry
        self.endpoint_registry = endpoint_registry
        ...
    
    async def request(
        self,
        endpoint_key: str,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[BaseModel] = None,
    ) -> Any:
        """Make an HTTP request to a service endpoint."""
        endpoint = self.endpoint_registry.get(endpoint_key)
        url = self._build_url(endpoint, path_params)
        
        # Validate request body
        if body and endpoint.request_model:
            if not isinstance(body, endpoint.request_model):
                raise ValueError(...)
        
        # Make request based on method
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if endpoint.method == HttpMethod.GET:
                    response = await client.get(...)
                elif endpoint.method == HttpMethod.POST:
                    response = await client.post(...)
                # ... other methods
                
                # Handle errors specifically
                if response.status_code == 404:
                    raise ServiceNotFoundError(...)
                if response.status_code >= 500:
                    raise ServiceUnavailableError(...)
                
                # Validate response
                validated_response = endpoint.response_model.model_validate(
                    response.json()
                )
                return validated_response
        
        except httpx.TimeoutException:
            raise ServiceTimeoutError(...)
        except Exception:
            raise ServiceError(...)
    
    async def get(...): ...
    async def post(...): ...
    async def put(...): ...
    async def delete(...): ...
```

**Improvements:**
- ✅ Supports all HTTP methods
- ✅ Returns validated Pydantic models
- ✅ Dependency injection (testable)
- ✅ Comprehensive error handling with specific exceptions
- ✅ Request/response validation
- ✅ Per-endpoint timeout support
- ✅ Convenience methods for each HTTP method
- ✅ Better logging
- ✅ Request ID propagation

## Observability

### Before (`temp/observability.py`)
```python
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_ctx.set(request_id)
        
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("out_request", extra={...})
```

**Issues:**
- ❌ Everything in one file
- ❌ No error logging
- ❌ No request ID in response headers
- ❌ Limited context management functions

### After (`infra/observability/`)

**middleware.py:**
```python
class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracking, logging, and observability."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_ctx.set(request_id)
        
        response = None
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            logger.error("request_error", extra={...}, exc_info=True)
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("request_completed", extra={...})
            
            # Add request ID to response headers
            if response is not None:
                response.headers["X-Request-ID"] = request_id
```

**context.py:**
```python
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return request_id_ctx.get()

def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    request_id_ctx.set(request_id)

def clear_request_id() -> None:
    """Clear the request ID from context."""
    request_id_ctx.set(None)
```

**Improvements:**
- ✅ Separated concerns (middleware vs context)
- ✅ Better error handling and logging
- ✅ Request ID in response headers
- ✅ Utility functions for context management
- ✅ Better documentation

## Logging

### Before (`temp/logging.py`)
```python
from app.core.settings import settings
from app.core.observability import request_id_ctx

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.name = settings.service_name
        record.environment = settings.environment
        record.version = settings.service_version
        record.request_id = request_id_ctx.get()
        return True

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = JsonFormatter("...")
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    logger.addHandler(handler)
```

**Issues:**
- ❌ Tightly coupled to global settings
- ❌ Hardcoded log level
- ❌ No configuration options
- ❌ Always JSON (no plain text option)

### After (`infra/observability/logging.py`)
```python
class ContextFilter(logging.Filter):
    """Logging filter that adds service context to all log records."""
    
    def __init__(self, settings: SettingsProtocol):
        super().__init__()
        self.settings = settings
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = self.settings.service_name
        record.environment = self.settings.environment
        record.version = self.settings.service_version
        record.request_id = get_request_id()
        return True

class StructuredFormatter(JsonFormatter):
    """JSON formatter for structured logging."""
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Ensure consistent field naming
        if "levelname" in log_record:
            log_record["level"] = log_record.pop("levelname")

def setup_logging(settings: SettingsProtocol) -> logging.Logger:
    """Configure structured logging for the application."""
    logger = logging.getLogger()
    logger.handlers.clear()
    
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    handler = logging.StreamHandler(sys.stdout)
    
    # Configure formatter based on settings
    if settings.enable_json_logging:
        formatter = StructuredFormatter("...")
    else:
        formatter = logging.Formatter("...")
    
    handler.setFormatter(formatter)
    
    if settings.enable_json_logging:
        handler.addFilter(ContextFilter(settings))
    
    logger.addHandler(handler)
    return logger

def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
```

**Improvements:**
- ✅ Dependency injection (settings parameter)
- ✅ Configurable log level from settings
- ✅ Optional JSON vs plain text logging
- ✅ Returns configured logger
- ✅ Utility function for getting loggers
- ✅ Custom formatter class for consistency
- ✅ Better documentation

## Models & Registry

### Before (`temp/http/models.py` & `service_registry.py`)
```python
# models.py
class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    ...

@dataclass(frozen=True)
class ServiceEndpoint:
    service: str
    url: str
    method: HttpMethod
    request: Type[BaseModel] | None
    response: Type[BaseModel]

# service_registry.py
SERVICE_ENDPOINTS = {
    "census.customer_by_id": ServiceEndpoint(...),
}
```

**Issues:**
- ❌ Global dictionary for endpoints
- ❌ No validation
- ❌ No way to list endpoints
- ❌ No exception classes
- ❌ Limited HttpMethod enum

### After (`infra/http/`)

**models.py:**
```python
class HttpMethod(str, Enum):
    """HTTP methods supported for service endpoints."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

@dataclass(frozen=True)
class ServiceEndpoint:
    """Definition of a service endpoint."""
    service: str
    path: str  # Renamed from 'url' for clarity
    method: HttpMethod
    request_model: Type[BaseModel] | None  # Renamed
    response_model: Type[BaseModel]  # Renamed
    timeout: float | None = None  # New field
    
    def __post_init__(self) -> None:
        """Validate endpoint definition."""
        if not self.service:
            raise ValueError("service cannot be empty")
        ...

class ServiceError(Exception):
    """Base exception for service communication errors."""
    ...

class ServiceNotFoundError(ServiceError): ...
class ServiceTimeoutError(ServiceError): ...
class ServiceUnavailableError(ServiceError): ...
```

**registry.py:**
```python
class EndpointRegistry:
    """Registry for managing service endpoint definitions."""
    
    def __init__(self) -> None:
        self._endpoints: Dict[str, ServiceEndpoint] = {}
    
    def register(self, key: str, endpoint: ServiceEndpoint) -> None: ...
    def get(self, key: str) -> ServiceEndpoint: ...
    def has(self, key: str) -> bool: ...
    def list_keys(self) -> list[str]: ...
    def list_by_service(self, service: str) -> Dict[str, ServiceEndpoint]: ...
    def unregister(self, key: str) -> None: ...
    def clear(self) -> None: ...
    def bulk_register(self, endpoints: Dict[str, ServiceEndpoint]) -> None: ...

# Global registry pattern
_global_registry = EndpointRegistry()

def get_global_registry() -> EndpointRegistry:
    """Get the global endpoint registry instance."""
    return _global_registry
```

**Improvements:**
- ✅ Proper class-based registry
- ✅ Validation on registration
- ✅ Multiple utility methods
- ✅ Exception hierarchy for errors
- ✅ More HTTP methods supported
- ✅ Per-endpoint timeout support
- ✅ Global registry option
- ✅ Bulk operations support
- ✅ Better naming (path vs url, *_model)

## Summary of Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Reusability** | Service-specific | Generic base classes |
| **Type Safety** | Basic | Comprehensive type hints |
| **Testing** | Hard to test (global state) | Easy to test (DI) |
| **Documentation** | Minimal | Extensive with examples |
| **Error Handling** | Basic | Comprehensive hierarchy |
| **Validation** | Limited | Full Pydantic validation |
| **Configuration** | Few options | Many configurable options |
| **Organization** | Mixed concerns | Clear separation |
| **Performance** | No caching | Caching where appropriate |
| **Observability** | Basic | Full tracing support |
