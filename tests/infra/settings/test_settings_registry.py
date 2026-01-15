import pytest
from pydantic_settings import BaseSettings

from fundamentum.infra.settings.registry import ServiceRegistry


@pytest.fixture
def basic_settings():
    class TestSettings(BaseSettings):
        census_base_url: str = "http://census.local"
        hermes_base_url: str = "http://hermes.local"
        nuntius_base_url: str = "http://nuntius.local"
        unrelated_setting: int = 42

    return TestSettings()


@pytest.fixture
def registry(basic_settings):
    return ServiceRegistry(basic_settings)


class TestServiceRegistry:

    def test_list_all_registered_services(self):

        class TestSettings(BaseSettings):
            service_a_base_url: str = "http://service-a.local"
            service_b_base_url: str = "http://service-b.local"
            service_c_base_url: str = "http://service-c.local"
            unrelated_setting: int = 42

        service_registry = ServiceRegistry(TestSettings())

        assert service_registry.list_services() == [
            "service_a",
            "service_b",
            "service_c",
        ]

    def test_get_base_url_existing_service(self, registry):
        """Test retrieving base URLs for existing services."""
        assert registry.get_base_url("census") == "http://census.local"
        assert registry.get_base_url("hermes") == "http://hermes.local"
        assert registry.get_base_url("nuntius") == "http://nuntius.local"

    def test_get_base_url_nonexistent_service(self, registry):
        with pytest.raises(
            ValueError,
            match="Service 'invalid_service' is not configured. Available services:",
        ):
            registry.get_base_url("invalid_service")

    def test_caching_mechanism(self, registry):
        # First call should populate the cache
        url_first_call = registry.get_base_url("census")
        assert url_first_call == "http://census.local"

        # Modify the settings to see if cache is used
        registry._settings.census_base_url = "http://new-census.local"

        # Second call should return cached value, not the modified one
        url_second_call = registry.get_base_url("census")
        assert url_second_call == "http://census.local"

    def test_clear_cache(self, registry):
        # Populate the cache
        url_first_call = registry.get_base_url("census")
        assert url_first_call == "http://census.local"

        # Modify the settings
        registry._settings.census_base_url = "http://new-census.local"

        # Clear the cache
        registry.clear_cache()

        # Next call should reflect the updated setting
        url_after_clearing_cache = registry.get_base_url("census")
        assert url_after_clearing_cache == "http://new-census.local"

    def test_case_insensitive_service_name(self, registry):
        assert registry.get_base_url("census") == registry.get_base_url("CENSUS")
        assert registry.get_base_url("Hermes") == "http://hermes.local"