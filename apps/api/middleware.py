import logging
import time
import uuid

from core.observability import observation_context
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_LOGGER = logging.getLogger("colearni.api")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that reads an incoming X-Request-ID or generates one.
    The ID is propagated through the application's observation context and
    returned in the response headers.  Also logs request/response summary.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and wrap it in an observation context."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()

        with observation_context(request_id=request_id):
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["x-request-id"] = request_id
            _LOGGER.info(
                "%s %s %d %.0fms rid=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                request_id,
            )
            return response

