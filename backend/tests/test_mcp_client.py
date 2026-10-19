"""Tests for the MCP registry and its client. No MCP server is contacted."""

import asyncio
from types import SimpleNamespace

import pytest

from app.mcp_clients import client
from app.mcp_clients.client import ToolNotAllowedError
from app.mcp_clients.registry import mcp_servers

SEARCH_TOOL = {"type": "function", "function": {"name": "search_jd_references"}}


@pytest.fixture(autouse=True)
def forget_cached_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, "_agent_tools", {})


# --- The registry ---


def test_only_read_only_servers_are_offered_to_the_agent() -> None:
    servers = mcp_servers()

    assert servers["rag"].offer_to_agent is True
    assert servers["blogger"].offer_to_agent is False
    assert servers["blogger"].allowed_tools == {"create_post"}


def test_a_tool_off_the_allow_list_is_refused_before_any_request() -> None:
    with pytest.raises(ToolNotAllowedError):
        asyncio.run(client.call_tool_async("blogger", "delete_post", {}))


def test_an_unknown_server_is_refused() -> None:
    with pytest.raises(ToolNotAllowedError):
        asyncio.run(client.call_tool_async("shell", "run", {}))


def test_the_answer_check_is_for_the_backend_only() -> None:
    rag = mcp_servers()["rag"]

    assert "verify_answer" in rag.allowed_tools
    assert rag.backend_only == {"verify_answer"}
    with pytest.raises(ToolNotAllowedError):
        client.call_agent_tool("verify_answer", {"question": "q", "answer": "a"})


def test_the_agent_cannot_call_a_publishing_tool() -> None:
    with pytest.raises(ToolNotAllowedError):
        client.call_agent_tool("create_post", {"title": "x"})


# --- Tools offered to the agent ---


def test_only_tools_of_offered_servers_reach_the_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = []

    async def listed(server_name: str) -> list[dict]:
        asked.append(server_name)
        return [SEARCH_TOOL]

    monkeypatch.setattr(client, "_list_tools", listed)

    assert client.agent_tool_definitions() == [SEARCH_TOOL]
    assert asked == ["rag"]


def test_tools_not_on_the_allow_list_are_not_described(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools = [
        SimpleNamespace(name="search_jd_references", description="Search", input_schema={}),
        SimpleNamespace(name="delete_collection", description="Danger", input_schema={}),
        SimpleNamespace(name="verify_answer", description="Backend only", input_schema={}),
    ]

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def list_tools(self):
            return SimpleNamespace(tools=tools)

    monkeypatch.setattr(client, "Client", FakeClient)

    described = asyncio.run(client._list_tools("rag"))

    assert [tool["function"]["name"] for tool in described] == ["search_jd_references"]


def test_no_tools_are_offered_when_the_server_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unreachable(server_name: str) -> list:
        raise ConnectionError("server down")

    monkeypatch.setattr(client, "_list_tools", unreachable)

    assert client.agent_tool_definitions() == []


def test_tools_are_fetched_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    fetches = []

    async def listed(server_name: str) -> list[dict]:
        fetches.append(server_name)
        return [SEARCH_TOOL]

    monkeypatch.setattr(client, "_list_tools", listed)

    first = client.agent_tool_definitions()
    second = client.agent_tool_definitions()

    assert first == second
    assert len(fetches) == 1


def test_a_failed_fetch_is_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unreachable(server_name: str) -> list:
        raise ConnectionError("server down")

    async def listed(server_name: str) -> list[dict]:
        return [SEARCH_TOOL]

    monkeypatch.setattr(client, "_list_tools", unreachable)
    assert client.agent_tool_definitions() == []

    monkeypatch.setattr(client, "_list_tools", listed)
    assert len(client.agent_tool_definitions()) == 1


# --- Calling the agent's tools ---


def test_an_agent_tool_call_goes_to_its_server(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_call(server_name, tool, arguments, timeout=60):
        calls.append((server_name, tool, arguments))
        return SimpleNamespace(is_error=False, structured_content={"result": ["ref"]})

    monkeypatch.setattr(client, "call_tool", fake_call)

    assert client.call_agent_tool("search_jd_references", {"query": "python"}) == ["ref"]
    assert calls == [("rag", "search_jd_references", {"query": "python"})]


def test_a_tool_error_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client,
        "call_tool",
        lambda *args, **kwargs: SimpleNamespace(is_error=True, structured_content=None),
    )

    with pytest.raises(RuntimeError):
        client.call_agent_tool("search_jd_references", {"query": "python"})
