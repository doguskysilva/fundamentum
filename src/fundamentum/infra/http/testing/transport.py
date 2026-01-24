from collections.abc import Callable

import httpx


class MockHttpTransport:
    """
    HTTPX mock transport for simulating inter-service HTTP calls.
    """

    def __init__(self) -> None:
        self._handlers: dict[
            tuple[str, str],
            Callable[[httpx.Request], httpx.Response],
        ] = {}

    def register_response(
        self,
        *,
        method: str,
        url: str,
        status_code: int = 200,
        json_body: dict | list | None = None,
    ) -> None:
        key = (method.upper(), url)

        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=status_code,
                json=json_body,
            )

        self._handlers[key] = handler

    def build(self) -> httpx.MockTransport:
        def dispatch(request: httpx.Request) -> httpx.Response:
            key = (request.method, str(request.url))
            if key not in self._handlers:
                raise RuntimeError(
                    f"No mock registered for {request.method} {request.url}"
                )
            return self._handlers[key](request)

        return httpx.MockTransport(dispatch)
