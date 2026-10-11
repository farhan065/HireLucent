"""Tests for the backend's MCP client."""

import pytest

from app.rag import mcp_client


@pytest.fixture(autouse=True)
def forget_cached_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_client, "_tool_definitions", None)


def test_no_tools_are_offered_when_the_server_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unreachable() -> list:
        raise ConnectionError("server down")

    monkeypatch.setattr(mcp_client, "_list_tools", unreachable)

    assert mcp_client.tool_definitions() == []


def test_tools_are_fetched_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    fetches = []

    async def listed() -> list[dict]:
        fetches.append(1)
        return [{"type": "function", "function": {"name": "search_jd_references"}}]

    monkeypatch.setattr(mcp_client, "_list_tools", listed)

    first = mcp_client.tool_definitions()
    second = mcp_client.tool_definitions()

    assert first == second
    assert len(fetches) == 1


def test_a_failed_fetch_is_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unreachable() -> list:
        raise ConnectionError("server down")

    async def listed() -> list[dict]:
        return [{"type": "function", "function": {"name": "search_jd_references"}}]

    monkeypatch.setattr(mcp_client, "_list_tools", unreachable)
    assert mcp_client.tool_definitions() == []

    monkeypatch.setattr(mcp_client, "_list_tools", listed)
    assert len(mcp_client.tool_definitions()) == 1
