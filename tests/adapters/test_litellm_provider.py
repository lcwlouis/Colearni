from __future__ import annotations

from typing import Any

import pytest
from adapters.embeddings.litellm_provider import LiteLLMEmbeddingProvider


def test_embed_texts_returns_embeddings_sorted_by_response_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_calls: list[dict[str, object]] = []

    def _fake_embedding(**kwargs: Any) -> dict[str, object]:
        captured_calls.append(dict(kwargs))
        return {
            "data": [
                {"index": 1, "embedding": [0.2, 0.3]},
                {"index": 0, "embedding": [0.0, 0.1]},
            ]
        }

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.litellm.embedding",
        _fake_embedding,
    )
    provider = LiteLLMEmbeddingProvider(
        model="text-embedding-proxy",
        embedding_dim=2,
        timeout_seconds=4.5,
        api_base="http://localhost:4000",
        api_key="proxy-key",
    )
    assert provider.embed_texts(["first", "second"]) == [[0.0, 0.1], [0.2, 0.3]]
    assert captured_calls == [
        {
            "model": "text-embedding-proxy",
            "input": ["first", "second"],
            "timeout": 4.5,
            "api_base": "http://localhost:4000",
            "api_key": "proxy-key",
        }
    ]


def test_embed_texts_raises_on_response_cardinality_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_embedding(**kwargs: Any) -> dict[str, object]:  # noqa: ARG001
        return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.litellm.embedding",
        _fake_embedding,
    )
    provider = LiteLLMEmbeddingProvider(
        "text-embedding-proxy",
        embedding_dim=2,
        timeout_seconds=4.5,
    )
    with pytest.raises(ValueError, match="expected 2, got 1"):
        provider.embed_texts(["first", "second"])


def test_embed_texts_raises_on_dimension_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_embedding(**kwargs: Any) -> dict[str, object]:  # noqa: ARG001
        return {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.litellm.embedding",
        _fake_embedding,
    )
    provider = LiteLLMEmbeddingProvider(
        "text-embedding-proxy",
        embedding_dim=2,
        timeout_seconds=4.5,
    )
    with pytest.raises(ValueError, match="expected 2, got 3"):
        provider.embed_texts(["first"])


def test_embed_texts_raises_on_invalid_data_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_embedding(**kwargs: Any) -> dict[str, object]:  # noqa: ARG001
        return {"data": "invalid"}

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.litellm.embedding",
        _fake_embedding,
    )
    provider = LiteLLMEmbeddingProvider(
        "text-embedding-proxy",
        embedding_dim=2,
        timeout_seconds=4.5,
    )
    with pytest.raises(ValueError, match="missing 'data' list"):
        provider.embed_texts(["first"])


def test_embed_texts_wraps_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_embedding(**kwargs: Any) -> dict[str, object]:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "adapters.embeddings.litellm_provider.litellm.embedding",
        _fake_embedding,
    )
    provider = LiteLLMEmbeddingProvider(
        "text-embedding-proxy",
        embedding_dim=2,
        timeout_seconds=4.5,
    )
    with pytest.raises(RuntimeError, match="LiteLLM embeddings request failed: boom"):
        provider.embed_texts(["first"])
