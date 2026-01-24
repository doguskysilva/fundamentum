from fundamentum.infra.http.models import ServiceEndpoint
from fundamentum.infra.http.testing.transport import MockHttpTransport
from fundamentum.infra.settings.registry import ServiceRegistry


def mock_endpoint(
    *,
    transport: MockHttpTransport,
    endpoint_key: str,
    endpoint: ServiceEndpoint,
    service_registry: ServiceRegistry,
    path_params: dict[str, str] | None = None,
    status_code: int = 200,
    json_body: dict | list | None = None,
) -> None:
    """
    Register a mock response for a logical service endpoint.
    """

    base_url = service_registry.get_base_url(endpoint.service)
    path = endpoint.path

    if path_params:
        for key, value in path_params.items():
            path = path.replace(f"{{{key}}}", str(value))

    url = f"{base_url}{path}"

    transport.register_response(
        method=endpoint.method.value,
        url=url,
        status_code=status_code,
        json_body=json_body,
    )
