import asyncio
import logging
import random
import time
from typing import Any, TypeVar, overload

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

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
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.observability.context import get_trace_id, get_traceparent
from fundamentum.infra.observability.helpers import (
    log_http_error,
    log_http_request,
    log_http_response,
)
from fundamentum.infra.observability.metrics import record_request
from fundamentum.infra.settings.registry import ServiceRegistry

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Safe to retry automatically: no side effects beyond the first successful
# application. POST/PATCH are excluded by default since retrying them risks
# duplicating a non-idempotent effect (e.g. double-creating a resource).
_IDEMPOTENT_METHODS = frozenset(
    {HttpMethod.GET, HttpMethod.PUT, HttpMethod.DELETE, HttpMethod.HEAD, HttpMethod.OPTIONS}
)
_METHODS_WITH_BODY = frozenset({HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH})

# Cap on computed backoff before jitter, in seconds.
_MAX_BACKOFF_SECONDS = 8.0


class ServiceClient:
    """Async HTTP client for inter-service communication.

    Features:
    - Automatic service URL resolution
    - Request ID propagation for distributed tracing (X-Trace-ID and W3C
      traceparent)
    - Retry with exponential backoff + jitter for idempotent methods, on
      connection errors, timeouts, and 5xx responses
    - Comprehensive error handling and logging
    - Request/response validation with Pydantic models
    - Timeout management
    - A single pooled connection reused across requests (see `aclose()`)
    """

    def __init__(
        self,
        service_registry: ServiceRegistry,
        endpoint_registry: EndpointRegistry,
        timeout: float = 10.0,
        max_retries: int = 3,
        service_name: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        limits: httpx.Limits | None = None,
    ):
        """Initialize the service client.

        Args:
            service_registry: Registry for resolving service base URLs
            endpoint_registry: Registry for endpoint definitions
            timeout: Default timeout for requests in seconds
            max_retries: Maximum retry attempts for idempotent requests that
                hit a transient failure (connection error, timeout, 5xx)
            service_name: Name of the calling service (for X-Service-Name header)
            transport: Optional custom transport (used by testing helpers to
                inject `httpx.MockTransport`)
            limits: Optional connection pool limits for the underlying
                `httpx.AsyncClient`
        """
        self.service_registry = service_registry
        self.endpoint_registry = endpoint_registry
        self.timeout = timeout
        self.max_retries = max_retries
        self.service_name = service_name
        self._client = httpx.AsyncClient(
            timeout=timeout, transport=transport, limits=limits or httpx.Limits()
        )
        self._adapters: dict[Any, TypeAdapter] = {}

    async def aclose(self) -> None:
        """Close the underlying connection pool. Call once at service shutdown."""
        await self._client.aclose()

    async def __aenter__(self) -> ServiceClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    def _get_adapter(self, response_model: Any) -> TypeAdapter:
        """Return a cached `TypeAdapter` for a response model.

        `TypeAdapter` validates `BaseModel`, `list[BaseModel]`, and plain
        types uniformly — unlike `BaseModel.model_validate`, which only
        exists on `BaseModel` subclasses and crashes on `list[...]`.
        """
        adapter = self._adapters.get(response_model)
        if adapter is None:
            adapter = TypeAdapter(response_model)
            self._adapters[response_model] = adapter
        return adapter

    def _build_url(
        self,
        endpoint: ServiceEndpoint,
        path_params: dict[str, Any] | None = None,
    ) -> str:
        """Build full URL from endpoint and path parameters.

        Args:
            endpoint: Service endpoint definition
            path_params: Path parameters to replace in URL

        Returns:
            Complete URL with base URL and resolved path parameters

        Raises:
            UnresolvedPathParameterError: If the path still contains
                unresolved `{param}` placeholders after substitution
        """
        base_url = self.service_registry.get_base_url(endpoint.service)
        path = endpoint.path

        if path_params:
            for key, value in path_params.items():
                placeholder = f"{{{key}}}"
                if placeholder not in path:
                    logger.warning(
                        "Path parameter '%s' not found in endpoint path",
                        key,
                        extra={"path": path, "params": path_params},
                    )
                path = path.replace(placeholder, str(value))

        if "{" in path and "}" in path:
            raise UnresolvedPathParameterError(
                f"Endpoint '{endpoint.service}{endpoint.path}' has unresolved "
                f"path parameters: '{path}'. A malformed URL was never sent.",
                endpoint=endpoint.path,
            )

        return f"{base_url}{path}"

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with tracing information.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        trace_id = get_trace_id()
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        traceparent = get_traceparent()
        if traceparent:
            headers["traceparent"] = traceparent

        if self.service_name:
            headers["X-Service-Name"] = self.service_name

        return headers

    @staticmethod
    def _is_retryable_method(method: HttpMethod) -> bool:
        return method in _IDEMPOTENT_METHODS

    @staticmethod
    def _backoff_seconds(attempt: int, retry_after: str | None) -> float:
        """Compute how long to sleep before the next retry attempt.

        Honors a `Retry-After` header (in seconds) when present; otherwise
        uses exponential backoff with jitter, capped at
        `_MAX_BACKOFF_SECONDS`.
        """
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass

        base = min(2**attempt, _MAX_BACKOFF_SECONDS)
        return base + random.uniform(0, base * 0.25)

    async def request(
        self,
        endpoint_key: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: BaseModel | None = None,
    ) -> Any:
        """Make an HTTP request to a service endpoint.

        Args:
            endpoint_key: Endpoint identifier in the registry
            path_params: Path parameters to replace in URL
            query_params: Query string parameters
            body: Request body (Pydantic model)

        Returns:
            Validated response data (a model instance, list of model
            instances, or None for empty bodies — matching the endpoint's
            declared `response_model`)

        Raises:
            KeyError: If endpoint_key is not found in registry
            RequestValidationError: If body doesn't match the declared request_model
            UnresolvedPathParameterError: If a required path parameter was never
                supplied
            ServiceNotFoundError: If resource is not found (404)
            ServiceTimeoutError: If request times out (after retries are exhausted)
            ServiceUnavailableError: If service returns 5xx or is unreachable
                (after retries are exhausted)
            ServiceError: For other HTTP errors
            ValidationError: If response doesn't match expected model
        """
        endpoint = self.endpoint_registry.get(endpoint_key)
        url = self._build_url(endpoint, path_params)
        headers = self._build_headers()
        timeout = endpoint.timeout if endpoint.timeout is not None else self.timeout

        if body and endpoint.request_model and not isinstance(body, endpoint.request_model):
            raise RequestValidationError(
                f"Request body type {type(body)} doesn't match "
                f"expected type {endpoint.request_model}",
                endpoint=endpoint_key,
            )

        request_kwargs: dict[str, Any] = {"params": query_params, "headers": headers}
        if endpoint.method in _METHODS_WITH_BODY:
            request_kwargs["json"] = body.model_dump() if body else None

        retryable = self._is_retryable_method(endpoint.method)
        attempt = 0

        while True:
            log_http_request(
                logger,
                url_name=endpoint_key,
                peer_service=endpoint.service,
                url=url,
                method=endpoint.method.value,
            )
            start_time = time.time()

            try:
                response = await self._client.request(
                    endpoint.method.value, url, timeout=timeout, **request_kwargs
                )
            except httpx.TimeoutException as e:
                if retryable and attempt < self.max_retries:
                    await asyncio.sleep(self._backoff_seconds(attempt, None))
                    attempt += 1
                    continue
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error=f"Request timed out after {timeout}s",
                    error_type="ServiceTimeoutError",
                    timeout=timeout,
                    url=url,
                    attempts=attempt + 1,
                )
                raise ServiceTimeoutError(
                    f"Request to {url} timed out after {timeout}s ({attempt + 1} attempt(s))",
                    endpoint=endpoint_key,
                ) from e
            except httpx.TransportError as e:
                if retryable and attempt < self.max_retries:
                    await asyncio.sleep(self._backoff_seconds(attempt, None))
                    attempt += 1
                    continue
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error=str(e),
                    error_type=type(e).__name__,
                    url=url,
                    attempts=attempt + 1,
                )
                raise ServiceUnavailableError(
                    f"Connection to {url} failed: {e} ({attempt + 1} attempt(s))",
                    endpoint=endpoint_key,
                ) from e

            if response.status_code == 404:
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error=f"Resource not found at {url}",
                    error_type="ServiceNotFoundError",
                    status_code=404,
                    url=url,
                )
                raise ServiceNotFoundError(
                    f"Resource not found at {url}",
                    endpoint=endpoint_key,
                )

            if response.status_code >= 500:
                if retryable and attempt < self.max_retries:
                    await asyncio.sleep(
                        self._backoff_seconds(attempt, response.headers.get("Retry-After"))
                    )
                    attempt += 1
                    continue
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error=f"Service unavailable: HTTP {response.status_code}",
                    error_type="ServiceUnavailableError",
                    status_code=response.status_code,
                    url=url,
                    attempts=attempt + 1,
                )
                raise ServiceUnavailableError(
                    f"Service unavailable: HTTP {response.status_code} ({attempt + 1} attempt(s))",
                    endpoint=endpoint_key,
                    status_code=response.status_code,
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error=f"HTTP error {e.response.status_code}",
                    error_type="HTTPStatusError",
                    status_code=e.response.status_code,
                    response_body=e.response.text[:500],
                    url=url,
                )
                raise ServiceError(
                    f"HTTP error {e.response.status_code}: {e.response.text[:200]}",
                    endpoint=endpoint_key,
                    status_code=e.response.status_code,
                ) from e

            duration_ms = int((time.time() - start_time) * 1000)
            log_http_response(
                logger,
                url_name=endpoint_key,
                peer_service=endpoint.service,
                status_code=response.status_code,
                method=endpoint.method.value,
                duration_ms=duration_ms,
                url=url,
            )
            record_request(
                peer_service=endpoint.service,
                method=endpoint.method.value,
                url_name=endpoint_key,
                status_code=response.status_code,
                duration_ms=duration_ms,
                direction="outbound",
            )

            if not response.content:
                return None

            response_data = response.json()
            try:
                return self._get_adapter(endpoint.response_model).validate_python(response_data)
            except ValidationError as e:
                log_http_error(
                    logger,
                    url_name=endpoint_key,
                    peer_service=endpoint.service,
                    method=endpoint.method.value,
                    error="Response validation failed",
                    error_type="ValidationError",
                    validation_errors=e.errors(),
                    url=url,
                )
                raise

    @overload
    async def get(
        self,
        endpoint_key: str,
        *,
        response_type: type[T],
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> T: ...

    @overload
    async def get(
        self,
        endpoint_key: str,
        *,
        response_type: None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def get(
        self,
        endpoint_key: str,
        *,
        response_type: type[T] | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a GET request to a service endpoint.

        Args:
            endpoint_key: Endpoint identifier
            response_type: Optional type hint matching the endpoint's declared
                `response_model` — purely a static-typing aid, so callers get
                a concrete return type instead of `Any`. It doesn't change
                validation, which always uses the endpoint's own
                `response_model`.
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

    @overload
    async def post(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: type[T],
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> T: ...

    @overload
    async def post(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def post(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: type[T] | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a POST request to a service endpoint.

        Args:
            endpoint_key: Endpoint identifier
            body: Request body (Pydantic model)
            response_type: See `get()` — static-typing aid only.
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

    @overload
    async def put(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: type[T],
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> T: ...

    @overload
    async def put(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def put(
        self,
        endpoint_key: str,
        body: BaseModel,
        *,
        response_type: type[T] | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a PUT request to a service endpoint.

        Args:
            endpoint_key: Endpoint identifier
            body: Request body (Pydantic model)
            response_type: See `get()` — static-typing aid only.
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

    @overload
    async def delete(
        self,
        endpoint_key: str,
        *,
        response_type: type[T],
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> T: ...

    @overload
    async def delete(
        self,
        endpoint_key: str,
        *,
        response_type: None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def delete(
        self,
        endpoint_key: str,
        *,
        response_type: type[T] | None = None,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> Any:
        """Make a DELETE request to a service endpoint.

        Args:
            endpoint_key: Endpoint identifier
            response_type: See `get()` — static-typing aid only.
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
