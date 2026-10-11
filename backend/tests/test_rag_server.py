"""Tests for the RAG MCP server's search tool."""

import pytest

from app.mcp_servers import rag_server


def _match(source: str, distance: float) -> dict:
    return {"text": f"Text of {source}", "metadata": {"source": source}, "distance": distance}


def test_close_matches_are_returned_with_their_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        rag_server.store, "search", lambda *args, **kwargs: [_match("backend.txt", 0.25)]
    )

    assert rag_server.find_jd_references("backend engineer") == [
        {"source": "backend.txt", "similarity": 0.75, "text": "Text of backend.txt"}
    ]


def test_distant_matches_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rag_server.store,
        "search",
        lambda *args, **kwargs: [_match("backend.txt", 0.3), _match("chef.txt", 0.9)],
    )

    references = rag_server.find_jd_references("backend engineer")

    assert [reference["source"] for reference in references] == ["backend.txt"]


def test_search_is_limited_to_the_job_description_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched = []

    def fake_search(collection: str, query: str, limit: int) -> list:
        searched.append(collection)
        return []

    monkeypatch.setattr(rag_server.store, "search", fake_search)

    assert rag_server.find_jd_references("anything") == []
    assert searched == [rag_server.store.JD_REFERENCES]
