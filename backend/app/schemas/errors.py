"""Minimal error envelope schema for explicit API error responses.

All explicit route errors return:
    {"error": {"code": "...", "message": "...", "details": {}}}

FastAPI/Pydantic 422 validation errors remain in the default FastAPI format.
"""

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorEnvelope(BaseModel):
    error: ErrorBody
