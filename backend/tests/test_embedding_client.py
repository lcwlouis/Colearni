from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.app.agents.embedding_client import EmbeddingClient
from backend.app.settings import Settings


async def test_embedding_client_disabled_returns_none():
    client = EmbeddingClient(provider="disabled")

    assert await client.embed(["hello"]) is None


@pytest.mark.parametrize(
    ("provider", "api_key", "expected_base_url", "expected_api_key"),
    [
        ("openai", "embed-key", None, "embed-key"),
        (
            "gemini",
            "embed-key",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "embed-key",
        ),
        ("ollama", "", "http://localhost:11434/v1", "ollama"),
        ("openai_compatible", "embed-key", "http://localhost:9999/v1", "embed-key"),
    ],
)
def test_from_settings_builds_openai_client_with_expected_base_url(
    provider,
    api_key,
    expected_base_url,
    expected_api_key,
):
    settings = Settings(
        embedding_provider=provider,
        embedding_model="embed-model",
        embedding_api_key=api_key,
        embedding_api_base="http://localhost:9999/v1",
    )
    client = EmbeddingClient.from_settings(settings)

    with patch("openai.AsyncOpenAI") as async_openai:
        client._openai_client()

    kwargs = async_openai.call_args.kwargs
    assert kwargs["api_key"] == expected_api_key
    if expected_base_url is None:
        assert "base_url" not in kwargs
    else:
        assert kwargs["base_url"] == expected_base_url


async def test_embedding_client_embed_returns_vectors():
    openai_client = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=_fake_embeddings_create,
        )
    )
    client = EmbeddingClient(provider="openai", model="model", dimensions=1, client=openai_client)

    assert await client.embed(["a", "b"]) == [[1.0], [2.0]]
    assert _fake_embeddings_create.call_args == {
        "model": "model",
        "input": ["a", "b"],
        "dimensions": 1,
    }


async def test_embedding_client_omits_dimensions_for_ollama():
    openai_client = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=_fake_embeddings_create,
        )
    )
    client = EmbeddingClient(provider="ollama", model="model", dimensions=1, client=openai_client)

    assert await client.embed(["a"]) == [[1.0]]
    assert _fake_embeddings_create.call_args == {"model": "model", "input": ["a"]}


async def test_embedding_client_rejects_mismatched_dimensions():
    async def create_bad_embedding(**_kwargs):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0])])

    openai_client = SimpleNamespace(embeddings=SimpleNamespace(create=create_bad_embedding))
    client = EmbeddingClient(provider="openai", model="model", dimensions=1, client=openai_client)

    with pytest.raises(ValueError, match="returned 2 dimensions"):
        await client.embed(["a"])


async def _fake_embeddings_create(**kwargs):
    _fake_embeddings_create.call_args = kwargs
    input = kwargs["input"]
    return SimpleNamespace(
        data=[SimpleNamespace(embedding=[float(index + 1)]) for index, _ in enumerate(input)]
    )


_fake_embeddings_create.call_args = {}
