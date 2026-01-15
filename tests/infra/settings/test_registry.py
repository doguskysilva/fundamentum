from fundamentum.infra.settings.registry import ServiceRegistry
from pydantic_settings import BaseSettings

def test_list_all_registered_services():
    class TestSettings(BaseSettings):
        service_a_base_url: str = "http://service-a.local"
        service_b_base_url: str = "http://service-b.local"
        service_c_base_url: str = "http://service-c.local"
        unrelated_setting: int = 42

    service_registry = ServiceRegistry(TestSettings())
    
    assert ['service_a', 'service_b', 'service_c'] == service_registry.list_services()

def test_get_base_url_existing_service():
    class TestSettings(BaseSettings):
        census_base_url: str = "http://census.local"
        hermes_base_url: str = "http://hermes.local"

    service_registry = ServiceRegistry(TestSettings())
    
    assert "http://census.local" == service_registry.get_base_url("census")
    assert "http://hermes.local" == service_registry.get_base_url("hermes")

def test_get_base_url_nonexistent_service():
    class TestSettings(BaseSettings):
        census_base_url: str = "http://census.local"

    service_registry = ServiceRegistry(TestSettings())
    
    try:
        service_registry.get_base_url("hermes")
    except ValueError as e:
        assert str(e) == "Service 'hermes' is not configured. Available services: census"

def test_caching_mechanism():
    class TestSettings(BaseSettings):
        census_base_url: str = "http://census.local"

    service_registry = ServiceRegistry(TestSettings())
    
    # First call should populate the cache
    url_first_call = service_registry.get_base_url("census")
    assert url_first_call == "http://census.local"
    
    # Modify the settings to see if cache is used
    service_registry._settings.census_base_url = "http://new-census.local"
    
    # Second call should return cached value, not the modified one
    url_second_call = service_registry.get_base_url("census")
    assert url_second_call == "http://census.local"

def test_clear_cache():
    class TestSettings(BaseSettings):
        census_base_url: str = "http://census.local"

    service_registry = ServiceRegistry(TestSettings())
    
    # Populate the cache
    url_first_call = service_registry.get_base_url("census")
    assert url_first_call == "http://census.local"
    
    # Modify the settings
    service_registry._settings.census_base_url = "http://new-census.local"
    
    # Clear the cache
    service_registry.clear_cache()
    
    # Next call should reflect the updated setting
    url_after_clearing_cache = service_registry.get_base_url("census")
    assert url_after_clearing_cache == "http://new-census.local"