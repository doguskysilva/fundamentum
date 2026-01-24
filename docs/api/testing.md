# Testing Module

HTTP mocking utilities for testing with MockTransport and mock endpoints.

## Components

- **MockHttpTransport** - Wraps httpx.MockTransport
- **mock_endpoint** - Create mock responses

## Basic Usage

```python
import pytest
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint

@pytest.fixture
def mock_transport():
    return MockHttpTransport([
        mock_endpoint(
            "https://api.example.com/users/123",
            "GET",
            response_json={"id": "123", "name": "John"}
        ),
    ])

async def test_api_call(mock_transport):
    async with httpx.AsyncClient(transport=mock_transport) as client:
        response = await client.get("https://api.example.com/users/123")
        assert response.status_code == 200
        assert response.json()["name"] == "John"
```

## MockHttpTransport

```python
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint

# Single endpoint
transport = MockHttpTransport([
    mock_endpoint(
        "https://api.example.com/users",
        "GET",
        response_json={"users": []}
    ),
])

# Multiple endpoints
transport = MockHttpTransport([
    mock_endpoint("https://api.example.com/users/123", "GET", response_json={"id": "123"}),
    mock_endpoint("https://api.example.com/users", "POST", status_code=201),
])

# Use with client
async with httpx.AsyncClient(transport=transport) as client:
    response = await client.get("https://api.example.com/users/123")
```

## mock_endpoint

```python
from fundamentum.infra.http.testing import mock_endpoint

# JSON response
endpoint = mock_endpoint(
    "https://api.example.com/users",
    "GET",
    response_json={"users": []}
)

# Text response
endpoint = mock_endpoint(
    "https://api.example.com/data",
    "GET",
    response_text="Hello, World!"
)

# Custom status code
endpoint = mock_endpoint(
    "https://api.example.com/users",
    "POST",
    status_code=201,
    response_json={"id": "123"}
)

# Custom headers
endpoint = mock_endpoint(
    "https://api.example.com/users",
    "GET",
    headers={"X-Custom-Header": "value"},
    response_json={}
)
```

## ServiceClient Testing

```python
import pytest
from fundamentum.infra.http import ServiceClient
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint

@pytest.fixture
def census_client():
    transport = MockHttpTransport([
        mock_endpoint(
            "https://census.test/api/customers/123",
            "GET",
            response_json={"id": "123", "name": "John"}
        ),
    ])
    
    client = ServiceClient(
        service_name="census",
        base_url="https://census.test",
        timeout=30.0,
        transport=transport,
    )
    
    return client

async def test_get_customer(census_client):
    response = await census_client.get("/api/customers/123")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "123"
    assert data["name"] == "John"
```

## Error Responses

```python
# 404 Not Found
transport = MockHttpTransport([
    mock_endpoint(
        "https://api.example.com/users/999",
        "GET",
        status_code=404,
        response_json={"error": "User not found"}
    ),
])

# 500 Server Error
transport = MockHttpTransport([
    mock_endpoint(
        "https://api.example.com/users",
        "POST",
        status_code=500,
        response_json={"error": "Internal server error"}
    ),
])

# Test error handling
async def test_not_found():
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://api.example.com/users/999")
        assert response.status_code == 404
```

## Multiple Requests

```python
# Mock multiple endpoints
transport = MockHttpTransport([
    mock_endpoint(
        "https://api.example.com/users/123",
        "GET",
        response_json={"id": "123", "name": "John"}
    ),
    mock_endpoint(
        "https://api.example.com/posts/456",
        "GET",
        response_json={"id": "456", "title": "Hello"}
    ),
])

async def test_multiple_calls():
    async with httpx.AsyncClient(transport=transport) as client:
        user_response = await client.get("https://api.example.com/users/123")
        post_response = await client.get("https://api.example.com/posts/456")
        
        assert user_response.json()["name"] == "John"
        assert post_response.json()["title"] == "Hello"
```

## Complete Example

```python
import pytest
from fundamentum.infra.http import ServiceClient, ServiceRegistry
from fundamentum.infra.http.testing import MockHttpTransport, mock_endpoint

@pytest.fixture
def registry():
    return ServiceRegistry()

@pytest.fixture
def mock_census_transport():
    return MockHttpTransport([
        mock_endpoint(
            "https://census.test/api/customers/123",
            "GET",
            response_json={"id": "123", "name": "John", "email": "john@example.com"}
        ),
        mock_endpoint(
            "https://census.test/api/customers",
            "POST",
            status_code=201,
            response_json={"id": "456", "name": "Jane"}
        ),
    ])

@pytest.fixture
def census_client(registry, mock_census_transport):
    client = ServiceClient(
        service_name="census",
        base_url="https://census.test",
        transport=mock_census_transport,
    )
    registry.register(client)
    return client

async def test_get_customer(census_client):
    response = await census_client.get("/api/customers/123")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == "123"
    assert data["name"] == "John"

async def test_create_customer(census_client):
    payload = {"name": "Jane", "email": "jane@example.com"}
    response = await census_client.post("/api/customers", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "456"
    assert data["name"] == "Jane"
```

## API Reference

**Classes:**
- `MockHttpTransport(handlers)` - HTTP mock transport for testing
- `mock_endpoint(url, method, ...)` - Create mock HTTP endpoint

**Parameters:**
- `url: str` - Full URL to mock
- `method: str` - HTTP method (GET, POST, etc.)
- `status_code: int` - Response status (default: 200)
- `response_json: dict` - JSON response body
- `response_text: str` - Text response body
- `headers: dict` - Response headers
