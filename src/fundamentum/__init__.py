"""Fundamentum - Common infrastructure library for microservices.

This package provides reusable infrastructure components for building
microservices, including:

- Settings management with environment variable support
- Structured logging with JSON formatting
- Observability middleware for request tracking
- HTTP client for inter-service communication
- Service registry and endpoint management

Example:
    >>> from fundamentum.infra.settings.base import BaseServiceSettings
    >>> from fundamentum.infra.observability.logging import setup_logging
    >>> 
    >>> settings = BaseServiceSettings(service_name="my-service")
    >>> logger = setup_logging(settings)
    >>> logger.info("Service started")
"""

__version__ = "0.1.0"

__all__ = [
    "__version__",
]
