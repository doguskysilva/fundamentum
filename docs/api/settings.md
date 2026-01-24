# Settings Module

Configuration management with environment variable support.

## Components

- **BaseServiceSettings** - Base settings class with common fields
- **ServiceRegistry** - Service URL resolver

## Basic Usage

```python
from fundamentum.infra.settings import BaseServiceSettings
from pydantic import Field

class Settings(BaseServiceSettings):
    # Service URLs
    census_base_url: str = Field(default="http://localhost:8001")
    hermes_base_url: str = Field(default="http://localhost:8002")
    
    # Database
    database_url: str = Field(default="postgresql://localhost/mydb")

# Create instance
settings = Settings(service_name="my-service")
```

## Environment Variables

Settings automatically load from environment variables:

```bash
export SERVICE_NAME="my-service"
export ENVIRONMENT="production"
export LOG_LEVEL="INFO"
export CENSUS_BASE_URL="https://census.prod.example.com"
```

```python
# Loads from environment
settings = Settings()
```

## ServiceRegistry

Resolves service base URLs:

```python
from fundamentum.infra.settings import ServiceRegistry

service_registry = ServiceRegistry(settings)

# Get service URL
census_url = service_registry.get_base_url("census")
# Returns: "http://localhost:8001"
```

## Common Patterns

### Multiple Environments

```python
class Settings(BaseServiceSettings):
    census_base_url: str = Field(default="http://localhost:8001")
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.environment == "production":
            self.census_base_url = "https://census.prod.example.com"
```

### Secrets

```python
from pydantic import SecretStr

class Settings(BaseServiceSettings):
    database_password: SecretStr = Field(default="")
    
# Access secret
password = settings.database_password.get_secret_value()
```

### From .env File

```python
from pydantic_settings import SettingsConfigDict

class Settings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_file=".env")
    
    database_url: str = Field(default="postgresql://localhost/mydb")
```

## API Reference

**BaseServiceSettings**

Built-in fields:
- `service_name: str` (required)
- `service_version: str` (default: "0.1.0")
- `environment: str` (default: "development")
- `log_level: str` (default: "INFO")
- `http_timeout: float` (default: 10.0)

**ServiceRegistry(settings)**
- `get_base_url(service: str) -> str` - Get service URL, raises ValueError if not found
