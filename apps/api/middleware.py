import logging
import uuid

from core.observability import observation_context
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_LOGGER = logging.getLogger("colearni.api")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that reads an incoming X-Request-ID or generates one.
    The ID is propagated through the application's observation context and
    returned in the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and wrap it in an observation context."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        with observation_context(request_id=request_id):
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response

