"""Tests for testing helpers and mock transport."""

import asyncio
import pytest
import httpx
from pydantic import BaseModel
from types import SimpleNamespace

from fundamentum.infra.http.testing.transport import MockHttpTransport
from fundamentum.infra.http.testing.helpers import mock_endpoint
from fundamentum.infra.http.models import HttpMethod, ServiceEndpoint
from fundamentum.infra.http.client import ServiceClient
from fundamentum.infra.http.registry import EndpointRegistry
from fundamentum.infra.settings.registry import ServiceRegistry


def run(coro):
    """Helper to run async coroutines in sync tests."""
    return asyncio.run(coro)


# Test Models
class UserResponse(BaseModel):
    id: str
    name: str
    email: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class CreateUserRequest(BaseModel):
    name: str
    email: str


# Fixtures
@pytest.fixture
def mock_transport():
    """Create a fresh MockHttpTransport instance."""
    return MockHttpTransport()


@pytest.fixture
def service_registry():
    """Create a service registry with test services."""
    settings = SimpleNamespace(
        census_base_url="https://census.test",
        hermes_base_url="https://hermes.test",
    )
    return ServiceRegistry(settings)


@pytest.fixture
def endpoint_registry():
    """Create an endpoint registry with test endpoints."""
    registry = EndpointRegistry()
    
    # Register test endpoints
    registry.register(
        "census.get_user",
        ServiceEndpoint(
            service="census",
            path="/api/users/{user_id}",
            method=HttpMethod.GET,
            request_model=None,
            response_model=UserResponse,
        ),
    )
    
    registry.register(
        "census.list_users",
        ServiceEndpoint(
            service="census",
            path="/api/users",
            method=HttpMethod.GET,
            request_model=None,
            response_model=UserListResponse,
        ),
    )
    
    registry.register(
        "census.create_user",
        ServiceEndpoint(
            service="census",
            path="/api/users",
            method=HttpMethod.POST,
            request_model=CreateUserRequest,
            response_model=UserResponse,
        ),
    )
    
    return registry


@pytest.fixture
def client_with_mock_transport(service_registry, endpoint_registry, mock_transport):
    """Create a ServiceClient with mock transport."""
    client = ServiceClient(
        service_registry=service_registry,
        endpoint_registry=endpoint_registry,
        transport=mock_transport.build(),
    )
    return client


# MockHttpTransport Tests
class TestMockHttpTransport:
    """Tests for MockHttpTransport class."""
    
    def test_register_simple_response(self, mock_transport):
        """Test registering a simple mock response."""
        mock_transport.register_response(
            method="GET",
            url="https://api.test/users/123",
            status_code=200,
            json_body={"id": "123", "name": "John"},
        )
        
        transport = mock_transport.build()
        request = httpx.Request("GET", "https://api.test/users/123")
        response = transport.handle_request(request)
        
        assert response.status_code == 200
        assert response.json() == {"id": "123", "name": "John"}
    
    def test_register_multiple_responses(self, mock_transport):
        """Test registering multiple mock responses for different URLs."""
        mock_transport.register_response(
            method="GET",
            url="https://api.test/users/1",
            json_body={"id": "1", "name": "Alice"},
        )
        mock_transport.register_response(
            method="GET",
            url="https://api.test/users/2",
            json_body={"id": "2", "name": "Bob"},
        )
        
        transport = mock_transport.build()
        
        response1 = transport.handle_request(
            httpx.Request("GET", "https://api.test/users/1")
        )
        response2 = transport.handle_request(
            httpx.Request("GET", "https://api.test/users/2")
        )
        
        assert response1.json()["name"] == "Alice"
        assert response2.json()["name"] == "Bob"
    
    def test_register_different_methods(self, mock_transport):
        """Test registering responses for different HTTP methods on same URL."""
        mock_transport.register_response(
            method="GET",
            url="https://api.test/resource",
            json_body={"action": "retrieved"},
        )
        mock_transport.register_response(
            method="POST",
            url="https://api.test/resource",
            status_code=201,
            json_body={"action": "created"},
        )
        
        transport = mock_transport.build()
        
        get_response = transport.handle_request(
            httpx.Request("GET", "https://api.test/resource")
        )
        post_response = transport.handle_request(
            httpx.Request("POST", "https://api.test/resource")
        )
        
        assert get_response.json()["action"] == "retrieved"
        assert post_response.status_code == 201
        assert post_response.json()["action"] == "created"
    
    def test_register_custom_status_code(self, mock_transport):
        """Test registering a response with custom status code."""
        mock_transport.register_response(
            method="GET",
            url="https://api.test/not-found",
            status_code=404,
            json_body={"error": "Not found"},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://api.test/not-found")
        )
        
        assert response.status_code == 404
        assert response.json()["error"] == "Not found"
    
    def test_register_list_response(self, mock_transport):
        """Test registering a response with list body."""
        users = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]
        mock_transport.register_response(
            method="GET",
            url="https://api.test/users",
            json_body=users,
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://api.test/users")
        )
        
        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["name"] == "Alice"
    
    def test_unregistered_request_raises_error(self, mock_transport):
        """Test that requesting an unregistered URL raises RuntimeError."""
        mock_transport.register_response(
            method="GET",
            url="https://api.test/registered",
            json_body={"ok": True},
        )
        
        transport = mock_transport.build()
        
        with pytest.raises(RuntimeError, match="No mock registered for GET"):
            transport.handle_request(
                httpx.Request("GET", "https://api.test/unregistered")
            )
    
    def test_case_insensitive_method(self, mock_transport):
        """Test that HTTP methods are case-insensitive."""
        mock_transport.register_response(
            method="get",  # lowercase
            url="https://api.test/resource",
            json_body={"ok": True},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://api.test/resource")  # uppercase
        )
        
        assert response.status_code == 200
        assert response.json()["ok"] is True
    
    def test_empty_json_body(self, mock_transport):
        """Test registering a response with no body."""
        mock_transport.register_response(
            method="DELETE",
            url="https://api.test/resource/123",
            status_code=204,
            json_body=None,
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("DELETE", "https://api.test/resource/123")
        )
        
        assert response.status_code == 204


# mock_endpoint Helper Tests
class TestMockEndpointHelper:
    """Tests for the mock_endpoint helper function."""
    
    def test_mock_simple_endpoint(
        self, mock_transport, service_registry, endpoint_registry
    ):
        """Test mocking a simple endpoint without path parameters."""
        endpoint = endpoint_registry.get("census.list_users")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.list_users",
            endpoint=endpoint,
            service_registry=service_registry,
            json_body={"users": [], "total": 0},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://census.test/api/users")
        )
        
        assert response.status_code == 200
        assert response.json() == {"users": [], "total": 0}
    
    def test_mock_endpoint_with_path_params(
        self, mock_transport, service_registry, endpoint_registry
    ):
        """Test mocking an endpoint with path parameters."""
        endpoint = endpoint_registry.get("census.get_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "123"},
            json_body={"id": "123", "name": "John", "email": "john@test.com"},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://census.test/api/users/123")
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == "123"
        assert response.json()["name"] == "John"
    
    def test_mock_endpoint_with_multiple_path_params(
        self, mock_transport, service_registry, endpoint_registry
    ):
        """Test mocking an endpoint with multiple path parameters."""
        # Register a new endpoint with multiple path params
        endpoint_registry.register(
            "census.get_user_order",
            ServiceEndpoint(
                service="census",
                path="/api/users/{user_id}/orders/{order_id}",
                method=HttpMethod.GET,
                request_model=None,
                response_model=UserResponse,
            ),
        )
        
        endpoint = endpoint_registry.get("census.get_user_order")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user_order",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "456", "order_id": "789"},
            json_body={"id": "789", "name": "Order", "email": "test@test.com"},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://census.test/api/users/456/orders/789")
        )
        
        assert response.status_code == 200
        assert response.json()["id"] == "789"
    
    def test_mock_endpoint_with_custom_status_code(
        self, mock_transport, service_registry, endpoint_registry
    ):
        """Test mocking an endpoint with custom status code."""
        endpoint = endpoint_registry.get("census.get_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "999"},
            status_code=404,
            json_body={"error": "User not found"},
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("GET", "https://census.test/api/users/999")
        )
        
        assert response.status_code == 404
        assert response.json()["error"] == "User not found"
    
    def test_mock_post_endpoint(
        self, mock_transport, service_registry, endpoint_registry
    ):
        """Test mocking a POST endpoint."""
        endpoint = endpoint_registry.get("census.create_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.create_user",
            endpoint=endpoint,
            service_registry=service_registry,
            status_code=201,
            json_body={
                "id": "new123",
                "name": "Jane",
                "email": "jane@test.com",
            },
        )
        
        transport = mock_transport.build()
        response = transport.handle_request(
            httpx.Request("POST", "https://census.test/api/users")
        )
        
        assert response.status_code == 201
        assert response.json()["id"] == "new123"


# Integration Tests with ServiceClient
class TestServiceClientWithMockTransport:
    """Integration tests using ServiceClient with mock transport."""
    
    def test_client_get_with_mock(
        self, client_with_mock_transport, mock_transport, endpoint_registry, service_registry
    ):
        """Test ServiceClient GET request with mock transport."""
        endpoint = endpoint_registry.get("census.get_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "123"},
            json_body={"id": "123", "name": "John", "email": "john@test.com"},
        )
        
        # Rebuild client with updated mock transport
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        response = run(client.get("census.get_user", path_params={"user_id": "123"}))
        
        assert isinstance(response, UserResponse)
        assert response.id == "123"
        assert response.name == "John"
        assert response.email == "john@test.com"
    
    def test_client_post_with_mock(
        self, mock_transport, endpoint_registry, service_registry
    ):
        """Test ServiceClient POST request with mock transport."""
        endpoint = endpoint_registry.get("census.create_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.create_user",
            endpoint=endpoint,
            service_registry=service_registry,
            status_code=201,
            json_body={"id": "456", "name": "Jane", "email": "jane@test.com"},
        )
        
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        request_body = CreateUserRequest(name="Jane", email="jane@test.com")
        response = run(
            client.post("census.create_user", body=request_body)
        )
        
        assert isinstance(response, UserResponse)
        assert response.id == "456"
        assert response.name == "Jane"
    
    def test_client_list_response_with_mock(
        self, mock_transport, endpoint_registry, service_registry
    ):
        """Test ServiceClient with list response using mock transport."""
        endpoint = endpoint_registry.get("census.list_users")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.list_users",
            endpoint=endpoint,
            service_registry=service_registry,
            json_body={
                "users": [
                    {"id": "1", "name": "Alice", "email": "alice@test.com"},
                    {"id": "2", "name": "Bob", "email": "bob@test.com"},
                ],
                "total": 2,
            },
        )
        
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        response = run(client.get("census.list_users"))
        
        assert isinstance(response, UserListResponse)
        assert response.total == 2
        assert len(response.users) == 2
        assert response.users[0].name == "Alice"
        assert response.users[1].name == "Bob"
    
    def test_client_404_error_with_mock(
        self, mock_transport, endpoint_registry, service_registry
    ):
        """Test ServiceClient handles 404 errors correctly with mock transport."""
        from fundamentum.infra.http.models import ServiceNotFoundError
        
        endpoint = endpoint_registry.get("census.get_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "999"},
            status_code=404,
            json_body={"error": "Not found"},
        )
        
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        with pytest.raises(ServiceNotFoundError):
            run(client.get("census.get_user", path_params={"user_id": "999"}))
    
    def test_client_500_error_with_mock(
        self, mock_transport, endpoint_registry, service_registry
    ):
        """Test ServiceClient handles 500 errors correctly with mock transport."""
        from fundamentum.infra.http.models import ServiceUnavailableError
        
        endpoint = endpoint_registry.get("census.get_user")
        
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint,
            service_registry=service_registry,
            path_params={"user_id": "123"},
            status_code=500,
            json_body={"error": "Internal server error"},
        )
        
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        with pytest.raises(ServiceUnavailableError):
            run(client.get("census.get_user", path_params={"user_id": "123"}))
    
    def test_multiple_requests_with_mock(
        self, mock_transport, endpoint_registry, service_registry
    ):
        """Test multiple requests in sequence with mock transport."""
        # Mock first endpoint
        endpoint1 = endpoint_registry.get("census.get_user")
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint1,
            service_registry=service_registry,
            path_params={"user_id": "1"},
            json_body={"id": "1", "name": "Alice", "email": "alice@test.com"},
        )
        
        # Mock second endpoint
        endpoint2 = endpoint_registry.get("census.get_user")
        mock_endpoint(
            transport=mock_transport,
            endpoint_key="census.get_user",
            endpoint=endpoint2,
            service_registry=service_registry,
            path_params={"user_id": "2"},
            json_body={"id": "2", "name": "Bob", "email": "bob@test.com"},
        )
        
        client = ServiceClient(
            service_registry=service_registry,
            endpoint_registry=endpoint_registry,
            transport=mock_transport.build(),
        )
        
        response1 = run(client.get("census.get_user", path_params={"user_id": "1"}))
        response2 = run(client.get("census.get_user", path_params={"user_id": "2"}))
        
        assert response1.name == "Alice"
        assert response2.name == "Bob"
