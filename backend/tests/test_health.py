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
    """Response must contain status, version, db, llm_provider, and llm_model fields."""
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "version", "db", "llm_provider", "llm_model"}


@pytest.mark.anyio
async def test_health_llm_fields(client):
    """llm_provider and llm_model must be non-empty strings."""
    response = await client.get("/health")
    data = response.json()
    assert isinstance(data["llm_provider"], str) and len(data["llm_provider"]) > 0
    assert isinstance(data["llm_model"], str) and len(data["llm_model"]) > 0
