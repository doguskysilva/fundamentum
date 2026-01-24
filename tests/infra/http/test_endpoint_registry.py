import pytest
from pydantic import BaseModel

from fundamentum.infra.http.models import HttpMethod, ServiceEndpoint
from fundamentum.infra.http.registry import EndpointRegistry


@pytest.fixture
def registry():
    return EndpointRegistry()


@pytest.fixture
def census_endpoint():
    return ServiceEndpoint(
        service="census",
        path="/api/customers/{customer_id}",
        method=HttpMethod.GET,
        request_model=None,
        response_model=BaseModel,
    )


@pytest.fixture
def hermes_endpoint():
    
    return ServiceEndpoint(
        service="hermes",
        path="/api/orders/{order_id}",
        method=HttpMethod.POST,
        request_model=None,
        response_model=BaseModel,
    )


class TestEndpointRegistry:
    """Test suite for EndpointRegistry."""

    def test_register_and_get_endpoint(self, registry, census_endpoint):
        registry.register("census.customer_by_id", census_endpoint)
        retrieved_endpoint = registry.get("census.customer_by_id")
        assert retrieved_endpoint == census_endpoint

    def test_register_existing_endpoint_raises_error(self, registry, census_endpoint):
        registry.register("census.customer_by_id", census_endpoint)

        with pytest.raises(
            ValueError, match="Endpoint 'census.customer_by_id' is already registered"
        ):
            registry.register("census.customer_by_id", census_endpoint)

    def test_get_nonexistent_endpoint_raises_error(self, registry):
        with pytest.raises(
            KeyError, match="Endpoint 'nonexistent.endpoint' not found"
        ):
            registry.get("nonexistent.endpoint")

    def test_has_endpoint(self, registry, census_endpoint):
        registry.register("census.customer_by_id", census_endpoint)

        assert registry.has("census.customer_by_id")
        assert not registry.has("nonexistent.endpoint")

    def test_list_keys(self, registry, census_endpoint, hermes_endpoint):
        registry.register("census.customer_by_id", census_endpoint)
        registry.register("hermes.create_order", hermes_endpoint)

        keys = registry.list_keys()

        assert set(keys) == {"census.customer_by_id", "hermes.create_order"}

    def test_list_by_service(self, registry, census_endpoint):
        endpoint_create = ServiceEndpoint(
            service="census",
            path="/api/customers",
            method=HttpMethod.POST,
            request_model=None,
            response_model=BaseModel,
        )

        hermes_endpoint = ServiceEndpoint(
            service="hermes",
            path="/api/orders",
            method=HttpMethod.POST,
            request_model=None,
            response_model=[BaseModel],
        )

        registry.register("census.customer_by_id", census_endpoint)
        registry.register("census.create_customer", endpoint_create)
        registry.register("hermes.create_order", hermes_endpoint)

        census_endpoints = registry.list_by_service("census")
        hermes_endpoints = registry.list_by_service("hermes")

        assert set(census_endpoints) == {
            "census.customer_by_id",
            "census.create_customer",
        }
        assert set(hermes_endpoints) == {"hermes.create_order"}

    def test_unregister_endpoint(self, registry, census_endpoint):
        registry.register("census.customer_by_id", census_endpoint)
        assert registry.has("census.customer_by_id")

        registry.unregister("census.customer_by_id")
        assert not registry.has("census.customer_by_id")
    
    def test_unregister_nonexistent_endpoint_raises_error(self, registry):
        with pytest.raises(
            KeyError, match="Endpoint 'nonexistent.endpoint' not found"
        ):
            registry.unregister("nonexistent.endpoint")

    def test_clear_registry(self, registry, census_endpoint, hermes_endpoint):
        registry.register("census.customer_by_id", census_endpoint)
        registry.register("hermes.create_order", hermes_endpoint)

        assert len(registry.list_keys()) == 2

        registry.clear()

        assert len(registry.list_keys()) == 0

    def test_bulk_register(self, registry, census_endpoint, hermes_endpoint):
        endpoints = {
            "census.customer_by_id": census_endpoint,
            "hermes.create_order": hermes_endpoint,
        }

        registry.bulk_register(endpoints)

        assert registry.has("census.customer_by_id")
        assert registry.has("hermes.create_order")

    def test_bulk_register_with_existing_endpoint_raises_error(
        self, registry, census_endpoint, hermes_endpoint
    ):
        registry.register("census.customer_by_id", census_endpoint)

        endpoints = {
            "census.customer_by_id": census_endpoint,
            "hermes.create_order": hermes_endpoint,
        }

        with pytest.raises(
            ValueError, match="Cannot register endpoints: already registered: census.customer_by_id"
        ):
            registry.bulk_register(endpoints)