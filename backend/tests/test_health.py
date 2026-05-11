import pytest


@pytest.mark.anyio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.anyio
async def test_health_includes_version(client):
    response = await client.get("/health")
    data = response.json()
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


@pytest.mark.anyio
async def test_health_db_field_present(client):
    """DB field must be present and be 'ok' or 'error' — no live DB required."""
    response = await client.get("/health")
    data = response.json()
    assert data["db"] in ("ok", "error")


@pytest.mark.anyio
async def test_health_shape(client):
    """Response must only contain status, version, and db fields."""
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "version", "db"}
