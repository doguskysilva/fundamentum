from fundamentum.infra.settings import BaseServiceSettings

def test_base_service_settings_default_values():
    settings = BaseServiceSettings(service_name="test-service")
    
    assert settings.service_name == "test-service"
    assert settings.service_version == "dev"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.enable_json_logging is True
    assert settings.http_retry_attempts == 3
    assert settings.http_timeout == 10.0

def test_base_service_settings_custom_values():
    settings = BaseServiceSettings(
        service_name="custom-service",
        service_version="v1.2.3",
        environment="production",
        log_level="ERROR",
        enable_json_logging=False,
        http_retry_attempts=5,
        http_timeout=15.0,
    )
    
    assert settings.service_name == "custom-service"
    assert settings.service_version == "v1.2.3"
    assert settings.environment == "production"
    assert settings.log_level == "ERROR"
    assert settings.enable_json_logging is False
    assert settings.http_retry_attempts == 5
    assert settings.http_timeout == 15.0
