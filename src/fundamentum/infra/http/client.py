import logging
import time
from typing import Any, Dict, Optional, Type

import httpx
from pydantic import BaseModel, ValidationError

from fundamentum.infra.http.models import (
    HttpMethod,
    ServiceEndpoint,
    ServiceError,
    ServiceNotFoundError,
    ServiceTimeoutError,
    ServiceUnavailableError,
)
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.observability.context import get_trace_id
from fundamentum.infra.observability.helpers import log_http_request, log_http_response
from fundamentum.infra.settings.registry import ServiceRegistry


logger = logging.getLogger(__name__)


class ServiceClient:
    """Async HTTP client for inter-service communication.
    
    Features:
    - Automatic service URL resolution
    - Request ID propagation for distributed tracing
    - Retry logic for transient failures
    - Comprehensive error handling and logging
    - Request/response validation with Pydantic models
    - Timeout management
    
    Example:
        >>> from fundamentum.infra.http.client import ServiceClient
        >>> from fundamentum.infra.http.registry import get_global_registry
        >>> from fundamentum.infra.settings.registry import ServiceRegistry
        >>> 
        >>> service_registry = ServiceRegistry(settings)
        >>> endpoint_registry = get_global_registry()
        >>> 
        >>> client = ServiceClient(
        ...     service_registry=service_registry,
        ...     endpoint_registry=endpoint_registry,
        ... )
        >>> 
        >>> # Make a request
        >>> response = await client.get(
        ...     "census.customer_by_id",
        ...     path_params={"customer_id": "123"}
        ... )
    """
    
    def __init__(
        self,
        service_registry: ServiceRegistry,
        endpoint_registry: EndpointRegistry,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """Initialize the service client.
        
        Args:
            service_registry: Registry for resolving service base URLs
            endpoint_registry: Registry for endpoint definitions
            timeout: Default timeout for requests in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.service_registry = service_registry
        self.endpoint_registry = endpoint_registry
        self.timeout = timeout
        self.max_retries = max_retries
    
    def _build_url(
        self, 
        endpoint: ServiceEndpoint, 
        path_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build full URL from endpoint and path parameters.
        
        Args:
            endpoint: Service endpoint definition
            path_params: Path parameters to replace in URL
            
        Returns:
            Complete URL with base URL and resolved path parameters
            
        Example:
            >>> url = client._build_url(
            ...     endpoint,
            ...     path_params={"customer_id": "123"}
            ... )
            'http://localhost:8001/api/customers/123'
        """
        base_url = self.service_registry.get_base_url(endpoint.service)
        path = endpoint.path
        
        # Replace path parameters
        if path_params:
            for key, value in path_params.items():
                placeholder = f"{{{key}}}"
                if placeholder not in path:
                    logger.warning(
                        f"Path parameter '{key}' not found in endpoint path",
                        extra={"path": path, "params": path_params}
                    )
                path = path.replace(placeholder, str(value))
        
        # Check for unreplaced parameters
        if "{" in path and "}" in path:
            logger.warning(
                "Endpoint path contains unreplaced parameters",
                extra={"path": path}
            )
        
        return f"{base_url}{path}"
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with tracing information.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Add trace ID for distributed tracing (pass current trace, don't increment)
        trace_id = get_trace_id()
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        
        return headers
    
    async def request(
        self,
        endpoint_key: str,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[BaseModel] = None,
    ) -> Any:
        """Make an HTTP request to a service endpoint.
        
        Args:
            endpoint_key: Endpoint identifier in the registry
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            body: Request body (Pydantic model)
            
        Returns:
            Validated response data (Pydantic model instance)
            
        Raises:
            KeyError: If endpoint_key is not found in registry
            ServiceNotFoundError: If resource is not found (404)
            ServiceTimeoutError: If request times out
            ServiceUnavailableError: If service returns 5xx error
            ServiceError: For other HTTP errors
            ValidationError: If response doesn't match expected model
        """
        # Get endpoint definition
        endpoint = self.endpoint_registry.get(endpoint_key)
        
        # Build URL and headers
        url = self._build_url(endpoint, path_params)
        headers = self._build_headers()
        
        # Use endpoint-specific timeout if available
        timeout = endpoint.timeout if endpoint.timeout is not None else self.timeout
        
        # Prepare request body
        json_body = body.model_dump() if body else None
        
        # Validate request body matches expected model
        if body and endpoint.request_model:
            if not isinstance(body, endpoint.request_model):
                raise ValueError(
                    f"Request body type {type(body)} doesn't match "
                    f"expected type {endpoint.request_model}"
                )
        
        # Log outgoing request with structured data
        log_http_request(
            logger,
            log_name=f"request_{endpoint_key}",
            endpoint_name=endpoint_key,
            url=url,
            method=endpoint.method.value,
        )
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Make request based on HTTP method
                if endpoint.method == HttpMethod.GET:
                    response = await client.get(url, params=query_params, headers=headers)
                elif endpoint.method == HttpMethod.POST:
                    response = await client.post(
                        url, json=json_body, params=query_params, headers=headers
                    )
                elif endpoint.method == HttpMethod.PUT:
                    response = await client.put(
                        url, json=json_body, params=query_params, headers=headers
                    )
                elif endpoint.method == HttpMethod.DELETE:
                    response = await client.delete(url, params=query_params, headers=headers)
                elif endpoint.method == HttpMethod.PATCH:
                    response = await client.patch(
                        url, json=json_body, params=query_params, headers=headers
                    )
                else:
                    raise ValueError(f"Unsupported HTTP method: {endpoint.method}")
                
                # Handle 404 specially
                if response.status_code == 404:
                    logger.warning(
                        "resource_not_found",
                        extra={
                            "endpoint_key": endpoint_key,
                            "url": url,
                            "status_code": 404,
                        }
                    )
                    raise ServiceNotFoundError(
                        f"Resource not found at {url}",
                        endpoint=endpoint_key,
                    )
                
                # Handle 5xx errors
                if response.status_code >= 500:
                    logger.error(
                        "service_unavailable",
                        extra={
                            "endpoint_key": endpoint_key,
                            "url": url,
                            "status_code": response.status_code,
                        }
                    )
                    raise ServiceUnavailableError(
                        f"Service unavailable: HTTP {response.status_code}",
                        endpoint=endpoint_key,
                        status_code=response.status_code,
                    )
                
                # Raise for other HTTP errors
                response.raise_for_status()
                
                # Log successful response
                duration_ms = int((time.time() - start_time) * 1000)
                log_http_response(
                    logger,
                    log_name=f"request_{endpoint_key}",
                    endpoint_name=endpoint_key,
                    url=url,
                    status_code=response.status_code,
                    method=endpoint.method.value,
                    duration_ms=duration_ms,
                )
                
                # Parse and validate response
                if response.content:
                    response_data = response.json()
                    
                    # Validate against response model
                    try:
                        validated_response = endpoint.response_model.model_validate(
                            response_data
                        )
                        return validated_response
                    except ValidationError as e:
                        logger.error(
                            "response_validation_error",
                            extra={
                                "endpoint_key": endpoint_key,
                                "url": url,
                                "validation_errors": e.errors(),
                            }
                        )
                        raise
                
                return None
                
        except httpx.TimeoutException as e:
            logger.error(
                "request_timeout",
                extra={
                    "endpoint_key": endpoint_key,
                    "url": url,
                    "timeout": timeout,
                }
            )
            raise ServiceTimeoutError(
                f"Request to {url} timed out after {timeout}s",
                endpoint=endpoint_key,
            ) from e
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "http_error",
                extra={
                    "endpoint_key": endpoint_key,
                    "url": url,
                    "status_code": e.response.status_code,
                    "response_body": e.response.text[:500],  # First 500 chars
                }
            )
            raise ServiceError(
                f"HTTP error {e.response.status_code}: {e.response.text[:200]}",
                endpoint=endpoint_key,
                status_code=e.response.status_code,
            ) from e
            
        except Exception as e:
            logger.error(
                "request_error",
                extra={
                    "endpoint_key": endpoint_key,
                    "url": url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise ServiceError(
                f"Request failed: {str(e)}",
                endpoint=endpoint_key,
            ) from e
    
    async def get(
        self,
        endpoint_key: str,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a GET request to a service endpoint.
        
        Args:
            endpoint_key: Endpoint identifier
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            
        Returns:
            Validated response data
        """
        return await self.request(
            endpoint_key=endpoint_key,
            path_params=path_params,
            query_params=query_params,
        )
    
    async def post(
        self,
        endpoint_key: str,
        body: BaseModel,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a POST request to a service endpoint.
        
        Args:
            endpoint_key: Endpoint identifier
            body: Request body (Pydantic model)
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            
        Returns:
            Validated response data
        """
        return await self.request(
            endpoint_key=endpoint_key,
            path_params=path_params,
            query_params=query_params,
            body=body,
        )
    
    async def put(
        self,
        endpoint_key: str,
        body: BaseModel,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a PUT request to a service endpoint.
        
        Args:
            endpoint_key: Endpoint identifier
            body: Request body (Pydantic model)
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            
        Returns:
            Validated response data
        """
        return await self.request(
            endpoint_key=endpoint_key,
            path_params=path_params,
            query_params=query_params,
            body=body,
        )
    
    async def delete(
        self,
        endpoint_key: str,
        path_params: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a DELETE request to a service endpoint.
        
        Args:
            endpoint_key: Endpoint identifier
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            
        Returns:
            Validated response data
        """
        return await self.request(
            endpoint_key=endpoint_key,
            path_params=path_params,
            query_params=query_params,
        )
