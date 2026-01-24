from typing import Literal

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class BaseServiceSettings(BaseSettings):
    """Base settings class for microservices.
    
    Provides common configuration fields that all services should have:
    - Service identification (name, version)
    - Environment information
    - Observability settings
    
    Subclass this to add service-specific configuration.
    
    Example:
        >>> class MyServiceSettings(BaseServiceSettings):
        ...     database_url: str = Field(default="sqlite:///./test.db")
        ...     
        >>> settings = MyServiceSettings(service_name="my-service")
    """
    
    model_config = ConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service identification
    service_name: str = Field(
        ...,
        description="Name of the microservice",
        examples=["census", "hermes", "nuntius"],
    )
    
    service_version: str = Field(
        default="dev",
        description="Service version (commit hash or tag)",
        examples=["a1b2c3d", "v1.0.0", "dev"],
    )
    
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
        examples=["development", "staging", "production"],
    )
    
    # Observability
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        examples=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    
    enable_json_logging: bool = Field(
        default=True,
        description="Enable JSON formatted logging for structured logs",
    )
    
    # HTTP Client settings
    http_timeout: float = Field(
        default=10.0,
        description="Default HTTP client timeout in seconds",
        gt=0,
    )
    
    http_retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed HTTP requests",
        ge=0,
    )
