"""Liveness/readiness router helpers.

Health endpoints are a near-universal microservice concern: liveness answers
"is the process alive" (never depends on downstream state — a flapping
dependency shouldn't get a healthy process killed), while readiness answers
"can this instance currently serve traffic" (does depend on downstream
state — a DB outage should pull the instance out of a load balancer).
"""

import inspect
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

HealthCheck = Callable[[], bool | Awaitable[bool]]


async def _run_check(check: HealthCheck) -> bool:
    try:
        outcome = check()
        if inspect.isawaitable(outcome):
            outcome = await outcome
        return bool(outcome)
    except Exception:
        logger.exception("Health check raised an exception; treating as unhealthy")
        return False


def create_health_router(
    *,
    checks: dict[str, HealthCheck] | None = None,
    liveness_path: str = "/healthz",
    readiness_path: str = "/readyz",
) -> APIRouter:
    """Build an `APIRouter` exposing liveness and readiness endpoints.

    Args:
        checks: Named readiness checks. Each callable returns (or awaits to)
            a bool; a raised exception counts as unhealthy. Not consulted by
            the liveness endpoint.
        liveness_path: Path for the liveness endpoint.
        readiness_path: Path for the readiness endpoint.

    Returns:
        An `APIRouter` with the two endpoints, excluded from the OpenAPI
        schema (these aren't part of the service's public API).
    """
    router = APIRouter(include_in_schema=False)
    checks = checks or {}

    @router.get(liveness_path)
    async def liveness() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @router.get(readiness_path)
    async def readiness() -> JSONResponse:
        results = {name: await _run_check(check) for name, check in checks.items()}
        healthy = all(results.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ok" if healthy else "degraded",
                "checks": {name: "ok" if ok else "error" for name, ok in results.items()},
            },
        )

    return router
