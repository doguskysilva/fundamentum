import secrets
import string
from contextvars import ContextVar

# Context variable for trace ID propagation across async calls
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Character set for generating trace segments (alphanumeric for readability)
_TRACE_CHARS = string.ascii_uppercase + string.digits


def get_trace_id() -> str | None:
    """Get the current trace ID from context.
    
    Returns:
        Current trace ID or None if not in a request context
        
    Example:
        >>> from fundamentum.infra.observability.context import get_trace_id
        >>> trace_id = get_trace_id()
        >>> logger.info("Processing", extra={"trace_id": trace_id})
    """
    return trace_id_ctx.get()


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID in context.
    
    Useful for background tasks or async operations that need
    to maintain the trace ID from the original request.
    
    Args:
        trace_id: Trace ID to set in context
        
    Example:
        >>> from fundamentum.infra.observability.context import set_trace_id
        >>> set_trace_id("abc-123-def")
        >>> # Now all logs will include this trace ID
    """
    trace_id_ctx.set(trace_id)


def clear_trace_id() -> None:
    """Clear the trace ID from context.
    
    Useful for cleanup or testing purposes.
    """
    trace_id_ctx.set(None)


def generate_trace_segment() -> str:
    """Generate a unique 5-character trace segment.
    
    Uses cryptographically secure random generation to create
    a unique identifier segment for trace chains.
    
    Returns:
        5-character alphanumeric string (uppercase)
        
    Example:
        >>> segment = generate_trace_segment()
        >>> len(segment)
        5
        >>> segment  # e.g., 'C32PO', 'V40PO', 'A1B2C'
    """
    return ''.join(secrets.choice(_TRACE_CHARS) for _ in range(5))


def append_trace_segment(trace_id: str | None, segment: str | None = None) -> str:
    """Append a new segment to an existing trace ID.
    
    If trace_id is None or empty, creates a new trace with the segment.
    If segment is None, generates a random 5-character segment.
    
    Args:
        trace_id: Existing trace ID (e.g., 'UICALL.C32PO')
        segment: Segment to append (defaults to auto-generated)
        
    Returns:
        New trace ID with appended segment
        
    Example:
        >>> append_trace_segment('UICALL.C32PO', 'V40PO')
        'UICALL.C32PO.V40PO'
        >>> append_trace_segment(None, 'START')
        'START'
        >>> append_trace_segment('UICALL.C32PO')  # auto-generates segment
        'UICALL.C32PO.A1B2C'
    """
    if segment is None:
        segment = generate_trace_segment()
    
    if not trace_id:
        return segment
    
    return f"{trace_id}.{segment}"


def increment_trace_id(incoming_trace_id: str | None = None, segment: str | None = None) -> str:
    """Increment trace ID by appending a new segment.
    
    This is the main function services should use when receiving requests
    to add their segment to the trace chain.
    
    Args:
        incoming_trace_id: Trace ID from incoming request header
        segment: Custom segment to append (auto-generated if None)
        
    Returns:
        Incremented trace ID
        
    Example:
        >>> # Service receives trace from upstream
        >>> incoming = 'UICALL.C32PO'
        >>> new_trace = increment_trace_id(incoming)
        >>> new_trace  # e.g., 'UICALL.C32PO.V40PO'
    """
    return append_trace_segment(incoming_trace_id, segment)
