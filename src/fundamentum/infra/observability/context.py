import secrets
import string
from contextvars import ContextVar

# Context variable for trace ID propagation across async calls
trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)

# Context variable for the W3C traceparent header, kept separate from the
# homegrown chained trace_id above so each scheme can be read independently.
traceparent_ctx: ContextVar[str | None] = ContextVar("traceparent", default=None)

# Character set for generating trace segments (alphanumeric for readability)
_TRACE_CHARS = string.ascii_uppercase + string.digits


def get_trace_id() -> str | None:
    """Get the current trace ID from context.

    Returns:
        Current trace ID or None if not in a request context
    """
    return trace_id_ctx.get()


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID in context.

    Useful for background tasks or async operations that need
    to maintain the trace ID from the original request.

    Args:
        trace_id: Trace ID to set in context
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
    """
    return "".join(secrets.choice(_TRACE_CHARS) for _ in range(5))


def append_trace_segment(trace_id: str | None, segment: str | None = None) -> str:
    """Append a new segment to an existing trace ID.

    If trace_id is None or empty, creates a new trace with the segment.
    If segment is None, generates a random 5-character segment.

    Args:
        trace_id: Existing trace ID (e.g., 'UICALL.C32PO')
        segment: Segment to append (defaults to auto-generated)

    Returns:
        New trace ID with appended segment
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
    """
    return append_trace_segment(incoming_trace_id, segment)


def get_traceparent() -> str | None:
    """Get the current W3C traceparent header value from context.

    Returns:
        Current traceparent value or None if not in a request context
    """
    return traceparent_ctx.get()


def set_traceparent(traceparent: str) -> None:
    """Set the W3C traceparent header value in context.

    Args:
        traceparent: traceparent value to set in context
    """
    traceparent_ctx.set(traceparent)


def clear_traceparent() -> None:
    """Clear the traceparent value from context.

    Useful for cleanup or testing purposes.
    """
    traceparent_ctx.set(None)


def parse_traceparent(header: str) -> tuple[str, str] | None:
    """Parse a W3C traceparent header into its (trace-id, parent-id) parts.

    See https://www.w3.org/TR/trace-context/#traceparent-header. Only the
    trace-id and parent-id are extracted; version and flags are not
    validated beyond basic shape, since this library doesn't act as a full
    tracing SDK.

    Args:
        header: Raw traceparent header value (e.g. '00-<32 hex>-<16 hex>-01')

    Returns:
        (trace_id, parent_id) tuple, or None if the header is malformed
    """
    parts = header.strip().split("-")
    if len(parts) != 4:
        return None

    _version, trace_id, parent_id, _flags = parts
    if len(trace_id) != 32 or trace_id == "0" * 32:
        return None
    if len(parent_id) != 16 or parent_id == "0" * 16:
        return None

    return trace_id, parent_id


def generate_traceparent(incoming_traceparent: str | None = None) -> str:
    """Build the outgoing W3C traceparent header for this hop.

    Reuses the trace-id from an incoming traceparent (if present and valid)
    so the whole call chain shares one trace-id, per the W3C Trace Context
    spec — only a fresh parent-id (this hop's span) is generated each time.
    If no valid incoming header is given, a new trace-id is started.

    Args:
        incoming_traceparent: traceparent header from the incoming request,
            if any

    Returns:
        traceparent header value to set on outgoing requests/responses
    """
    trace_id = None
    if incoming_traceparent:
        parsed = parse_traceparent(incoming_traceparent)
        if parsed:
            trace_id = parsed[0]

    if trace_id is None:
        trace_id = secrets.token_hex(16)

    span_id = secrets.token_hex(8)
    return f"00-{trace_id}-{span_id}-01"
