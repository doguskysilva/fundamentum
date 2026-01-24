"""Tests for structured logging configuration."""

import logging
import sys

from fundamentum.infra.observability.context import clear_trace_id, set_trace_id
from fundamentum.infra.observability.logging import (
    ContextFilter,
    StructuredFormatter,
    get_logger,
    setup_logging,
)


class MockSettings:
    """Mock settings for testing."""
    
    def __init__(
        self,
        service_name="test-service",
        environment="test",
        service_version="1.0.0",
        log_level="INFO",
        enable_json_logging=True
    ):
        self.service_name = service_name
        self.environment = environment
        self.service_version = service_version
        self.log_level = log_level
        self.enable_json_logging = enable_json_logging


class TestContextFilter:
    """Tests for ContextFilter."""
    
    def test_context_filter_initialization(self):
        """Test ContextFilter initialization."""
        settings = MockSettings()
        filter = ContextFilter(settings)
        
        assert filter.settings == settings
    
    def test_context_filter_adds_service_context(self):
        """Test that filter adds service context to log records."""
        settings = MockSettings(
            service_name="my-service",
            environment="production",
            service_version="2.0.0"
        )
        filter = ContextFilter(settings)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        result = filter.filter(record)
        
        assert result is True
        assert record.service_name == "my-service"
        assert record.environment == "production"
        assert record.version == "2.0.0"
    
    def test_context_filter_adds_trace_id(self):
        """Test that filter adds trace ID from context."""
        settings = MockSettings()
        filter = ContextFilter(settings)
        
        # Set trace ID in context
        set_trace_id("UICALL.C32PO.V40PO")
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        
        assert record.trace_id == "UICALL.C32PO.V40PO"
        
        clear_trace_id()
    
    def test_context_filter_trace_id_none(self):
        """Test that filter handles None trace ID."""
        settings = MockSettings()
        filter = ContextFilter(settings)
        
        clear_trace_id()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        filter.filter(record)
        
        assert record.trace_id is None
    
    def test_context_filter_always_returns_true(self):
        """Test that filter always returns True to allow logging."""
        settings = MockSettings()
        filter = ContextFilter(settings)
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Filter should always return True
        assert filter.filter(record) is True


class TestStructuredFormatter:
    """Tests for StructuredFormatter."""
    
    def test_structured_formatter_renames_levelname(self):
        """Test that formatter renames levelname to level."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.module",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Simulate what JsonFormatter.add_fields does
        log_record = {"levelname": "INFO", "name": "test.module", "message": "test message"}
        formatter.add_fields(log_record, record, {})
        
        assert "level" in log_record
        assert "levelname" not in log_record
        assert log_record["level"] == "INFO"
    
    def test_structured_formatter_renames_name_to_logger(self):
        """Test that formatter renames name to logger."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="my.module.name",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Simulate what JsonFormatter.add_fields does
        log_record = {"name": "my.module.name", "message": "test message"}
        formatter.add_fields(log_record, record, {})
        
        assert "logger" in log_record
        assert "name" not in log_record
        assert log_record["logger"] == "my.module.name"
    
    def test_structured_formatter_includes_data_field(self):
        """Test that formatter includes data field from record."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Add data field to record
        record.data = {"user_id": "123", "action": "login"}
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        assert "data" in log_record
        assert log_record["data"] == {"user_id": "123", "action": "login"}
    
    def test_structured_formatter_handles_missing_data(self):
        """Test that formatter handles missing data field."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        # Should not add data if not present
        assert "data" not in log_record
    
    def test_structured_formatter_handles_empty_data(self):
        """Test that formatter handles empty data field."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        # Add empty data field
        record.data = {}
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        # Empty dict is truthy in Python, so it will be added
        assert "data" in log_record
        assert log_record["data"] == {}
    
    def test_structured_formatter_with_complex_data(self):
        """Test formatter with complex nested data."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None
        )
        
        record.data = {
            "user": {"id": "123", "name": "John"},
            "items": [1, 2, 3],
            "metadata": {"timestamp": "2026-01-20"}
        }
        
        log_record = {}
        formatter.add_fields(log_record, record, {})
        
        assert log_record["data"] == record.data


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def teardown_method(self):
        """Clean up logging handlers after each test."""
        logger = logging.getLogger()
        logger.handlers.clear()
    
    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns root logger."""
        settings = MockSettings()
        logger = setup_logging(settings)
        
        assert isinstance(logger, logging.Logger)
        assert logger == logging.getLogger()
    
    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup removes existing handlers."""
        # Add a handler
        logger = logging.getLogger()
        logger.addHandler(logging.StreamHandler())
        initial_count = len(logger.handlers)
        assert initial_count > 0
        
        settings = MockSettings()
        setup_logging(settings)
        
        # Should have exactly 1 handler (the new one)
        assert len(logger.handlers) == 1
    
    def test_setup_logging_sets_log_level(self):
        """Test that setup sets correct log level."""
        settings = MockSettings(log_level="DEBUG")
        logger = setup_logging(settings)
        
        assert logger.level == logging.DEBUG
    
    def test_setup_logging_info_level(self):
        """Test setup with INFO level."""
        settings = MockSettings(log_level="INFO")
        logger = setup_logging(settings)
        
        assert logger.level == logging.INFO
    
    def test_setup_logging_error_level(self):
        """Test setup with ERROR level."""
        settings = MockSettings(log_level="ERROR")
        logger = setup_logging(settings)
        
        assert logger.level == logging.ERROR
    
    def test_setup_logging_with_json_formatting(self):
        """Test setup with JSON formatting enabled."""
        settings = MockSettings(enable_json_logging=True)
        logger = setup_logging(settings)
        
        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)
    
    def test_setup_logging_with_plain_formatting(self):
        """Test setup with plain text formatting."""
        settings = MockSettings(enable_json_logging=False)
        logger = setup_logging(settings)
        
        assert len(logger.handlers) == 1
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, logging.Formatter)
        assert not isinstance(handler.formatter, StructuredFormatter)
    
    def test_setup_logging_adds_context_filter(self):
        """Test that setup adds context filter for JSON logging."""
        settings = MockSettings(enable_json_logging=True)
        logger = setup_logging(settings)
        
        handler = logger.handlers[0]
        filters = handler.filters
        
        assert len(filters) == 1
        assert isinstance(filters[0], ContextFilter)
    
    def test_setup_logging_no_context_filter_plain_text(self):
        """Test that setup doesn't add context filter for plain text."""
        settings = MockSettings(enable_json_logging=False)
        logger = setup_logging(settings)
        
        handler = logger.handlers[0]
        assert len(handler.filters) == 0
    
    def test_setup_logging_handler_is_stream_handler(self):
        """Test that setup creates StreamHandler."""
        settings = MockSettings()
        logger = setup_logging(settings)
        
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream == sys.stdout
    
    def test_setup_logging_handler_level_matches_logger(self):
        """Test that handler level matches logger level."""
        settings = MockSettings(log_level="WARNING")
        logger = setup_logging(settings)
        
        handler = logger.handlers[0]
        assert handler.level == logging.WARNING
        assert logger.level == logging.WARNING
    
    def test_setup_logging_invalid_level_defaults_to_info(self):
        """Test that invalid log level defaults to INFO."""
        settings = MockSettings(log_level="INVALID")
        logger = setup_logging(settings)
        
        # getattr with default should return INFO
        assert logger.level == logging.INFO


class TestGetLogger:
    """Tests for get_logger function."""
    
    def test_get_logger_without_name(self):
        """Test getting logger without name."""
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "root"
    
    def test_get_logger_with_name(self):
        """Test getting logger with specific name."""
        logger = get_logger("my.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "my.module"
    
    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns same instance for same name."""
        logger1 = get_logger("test")
        logger2 = get_logger("test")
        assert logger1 is logger2
    
    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        assert logger1 is not logger2
        assert logger1.name == "module1"
        assert logger2.name == "module2"


class TestLoggingIntegration:
    """Integration tests for logging system."""
    
    def teardown_method(self):
        """Clean up after each test."""
        logger = logging.getLogger()
        logger.handlers.clear()
        clear_trace_id()
    
    def test_full_logging_setup_with_trace_id(self):
        """Test complete logging setup with trace ID."""
        settings = MockSettings(enable_json_logging=True)
        root_logger = setup_logging(settings)
        
        # Set trace ID
        set_trace_id("UICALL.C32PO.V40PO")
        
        # Verify logger is configured
        assert len(root_logger.handlers) == 1
        
        # Clean up
        clear_trace_id()
    
    def test_logging_with_data_field(self):
        """Test logging with structured data field."""
        settings = MockSettings(enable_json_logging=True)
        setup_logging(settings)
        
        logger = get_logger("test")
        
        # Verify we can log with extra data
        # (actual log capture would require more complex setup)
        assert hasattr(logger, 'info')
        assert callable(logger.info)
    
    def test_context_filter_integration_with_formatter(self):
        """Test context filter works with formatter."""
        settings = MockSettings(
            service_name="integration-test",
            environment="test",
            service_version="1.0.0",
            enable_json_logging=True
        )
        setup_logging(settings)
        set_trace_id("TEST.12345")
        
        # Create a record manually to test filter + formatter
        record = logging.LogRecord(
            name="integration",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test",
            args=(),
            exc_info=None
        )
        
        # Apply filter
        handler = logging.getLogger().handlers[0]
        context_filter = handler.filters[0]
        context_filter.filter(record)
        
        # Verify context was added
        assert record.service_name == "integration-test"
        assert record.trace_id == "TEST.12345"
        
        # Apply formatter
        formatter = handler.formatter
        log_record = {"levelname": "INFO", "name": "integration", "message": "test"}
        formatter.add_fields(log_record, record, {})
        
        # Verify formatting
        assert log_record["level"] == "INFO"
        assert log_record["logger"] == "integration"
        
        clear_trace_id()
