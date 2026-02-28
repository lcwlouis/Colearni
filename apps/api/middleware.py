import logging
import time
import uuid

from core.observability import observation_context, start_span
from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

_LOGGER = logging.getLogger("colearni.api")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that reads an incoming X-Request-ID or generates one.
    The ID is propagated through the application's observation context and
    returned in the response headers.  Also logs request/response summary
    and creates an ``http.request`` root span for Phoenix trace trees.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and wrap it in an observation context."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()

        with observation_context(request_id=request_id):
            with start_span(
                "http.request",
                **{
                    "http.method": request.method,
                    "http.route": request.url.path,
                    "request_id": request_id,
                },
            ) as span:
                response = await call_next(request)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if span is not None:
                    span.set_attribute("http.status_code", response.status_code)
                    if response.status_code >= 500:
                        span.set_status(trace.StatusCode.ERROR, f"HTTP {response.status_code}")
                    else:
                        span.set_status(trace.StatusCode.OK)

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

