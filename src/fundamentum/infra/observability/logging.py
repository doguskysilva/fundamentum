"""Structured logging configuration and utilities.

This module provides JSON logging setup with automatic context injection
for microservices observability.
"""

import logging
import sys
from typing import Any

from pythonjsonlogger.json import JsonFormatter

from fundamentum.infra.observability.context import get_trace_id
from fundamentum.infra.settings.protocols import SettingsProtocol


class ContextFilter(logging.Filter):
    """Logging filter that adds service context to all log records.
    
    Automatically adds:
    - service_name: Name of the microservice
    - environment: Deployment environment
    - version: Service version
    - trace_id: Current trace ID from context (if available)
    """
    
    def __init__(self, settings: SettingsProtocol):
        """Initialize the context filter with settings.
        
        Args:
            settings: Settings object containing service information
        """
        super().__init__()
        self.settings = settings
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to the log record.
        
        Args:
            record: Log record to enhance
            
        Returns:
            True to allow the record to be logged
        """
        record.service_name = self.settings.service_name
        record.environment = self.settings.environment
        record.version = self.settings.service_version
        record.trace_id = get_trace_id()
        return True


class StructuredFormatter(JsonFormatter):
    """JSON formatter for structured logging.
    
    Formats log records as JSON with consistent field naming and structure.
    Supports the following structure:
    - level: Log level (INFO, ERROR, etc.)
    - logger: Name of the logger (file calling the log)
    - trace_id: Trace ID for request tracking
    - data: Dictionary containing implementation-specific details
    """
    
    def add_fields(
        self, 
        log_record: dict[str, Any], 
        record: logging.LogRecord, 
        message_dict: dict[str, Any]
    ) -> None:
        """Add fields to the log record JSON.
        
        Args:
            log_record: Dictionary to add fields to
            record: Source log record
            message_dict: Additional message dictionary
        """
        super().add_fields(log_record, record, message_dict)
        
        # Ensure consistent field naming
        if "levelname" in log_record:
            log_record["level"] = log_record.pop("levelname")
        
        if "name" in log_record:
            log_record["logger"] = log_record.pop("name")
        
        # Add service context fields
        if hasattr(record, 'service_name'):
            log_record["service"] = record.service_name
        
        if hasattr(record, 'version'):
            log_record["version"] = record.version
        
        if hasattr(record, 'environment'):
            log_record["environment"] = record.environment
        
        # Extract data field from extra if present
        if hasattr(record, 'data') and record.data:
            log_record["data"] = record.data


def setup_logging(settings: SettingsProtocol) -> logging.Logger:
    """Configure structured logging for the application.
    
    Sets up:
    - JSON or plain text formatting based on settings
    - Log level from settings
    - Context filter for service information
    - Handler for stdout
    
    Args:
        settings: Settings object with logging configuration
        
    Returns:
        Configured root logger
    """
    # Get root logger
    logger = logging.getLogger()
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Set log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Configure formatter
    if settings.enable_json_logging:
        formatter = StructuredFormatter(
            "%(asctime)s %(levelname)s %(name)s %(trace_id)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    handler.setFormatter(formatter)
    
    # Add context filter for structured logging
    if settings.enable_json_logging:
        context_filter = ContextFilter(settings)
        handler.addFilter(context_filter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name (defaults to caller's module)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
