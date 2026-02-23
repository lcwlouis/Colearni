"""Health payload helpers."""


def get_health_payload() -> dict[str, str]:
    """Return the liveness payload."""
    return {"status": "ok"}
