"""Tests for graph windowing (word-budget based)."""

from __future__ import annotations

from types import SimpleNamespace


def _fake_chunk(id: int, text: str):
    return SimpleNamespace(id=id, text=text)


def _import():
    # Lazy import avoids the circular import that occurs at collection time
    # (test → pipeline → adapters.db → core → domain.ingestion → pipeline).
    from domain.graph.pipeline import _make_graph_windows  # noqa: PLC0415

    return _make_graph_windows


class TestMakeGraphWindows:
    def test_single_chunk_under_budget(self):
        """One chunk smaller than budget -> one window."""
        _make_graph_windows = _import()
        chunks = [_fake_chunk(1, "Hello world")]
        windows = _make_graph_windows(chunks, 8000)
        assert len(windows) == 1
        assert windows[0] == (1, "Hello world")

    def test_chunks_split_at_word_budget(self):
        """Chunks exceeding word budget get split into multiple windows."""
        _make_graph_windows = _import()
        chunks = [
            _fake_chunk(1, "chunk one"),
            _fake_chunk(2, "chunk two"),
            _fake_chunk(3, "chunk three"),
        ]
        # Budget 3 words: chunk1 (2 words) fits, chunk2 would push to 4 -> split
        windows = _make_graph_windows(chunks, 3)
        assert len(windows) >= 2
        assert windows[0][0] == 1
        assert windows[1][0] == 2

    def test_zero_budget_one_window_per_chunk(self):
        """Budget=0 means each chunk is its own window (no batching)."""
        _make_graph_windows = _import()
        chunks = [_fake_chunk(1, "a"), _fake_chunk(2, "b")]
        windows = _make_graph_windows(chunks, 0)
        assert len(windows) == 2
        assert windows[0] == (1, "a")
        assert windows[1] == (2, "b")

    def test_char_unit_uses_len(self):
        """When size_unit is not 'words', character length is used."""
        _make_graph_windows = _import()
        chunks = [
            _fake_chunk(1, "abcd"),  # 4 chars
            _fake_chunk(2, "efgh"),  # 4 chars
        ]
        # Budget 5 chars: chunk1 (4) fits, chunk2 would push to 8 -> split
        windows = _make_graph_windows(chunks, 5, "chars")
        assert len(windows) == 2
        assert windows[0] == (1, "abcd")
        assert windows[1] == (2, "efgh")
