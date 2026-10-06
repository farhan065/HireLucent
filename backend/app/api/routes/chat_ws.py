"""Live chat with the recruiting assistant over a WebSocket.

The browser sends JSON messages and receives JSON events:

    browser -> server
        {"type": "auth", "token": "..."}                  first message
        {"type": "message", "thread_id": null, "text": "..."}
        {"type": "approval", "thread_id": "...", "approved": true}

    server -> browser
        {"type": "ready"}                                 signed in
        {"type": "token", "text": "..."}                  a piece of the reply
        {"type": "turn", "status": ..., "reply": ...}     the finished turn
        {"type": "error", "message": "..."}
"""

import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from langgraph.graph.state import CompiledStateGraph
from pydantic import ValidationError
from starlette.concurrency import iterate_in_threadpool

from app.core.errors import INTERNAL_ERROR_MESSAGE, AppError
from app.core.logging import get_logger, log_event
from app.core.security import decode_access_token
from app.graphs.recruiter.graph import get_recruiter_graph
from app.models.enums import UserRole
from app.schemas.chat import SocketMessage
from app.services import chat_service

logger = get_logger(__name__)

router = APIRouter()


async def _sign_in(websocket: WebSocket) -> int | None:
    """Read the first message, which must carry a valid interviewer token."""
    try:
        first = await websocket.receive_json()
    except ValueError:
        return None
    payload = decode_access_token(str(first.get("token", "")))
    if first.get("type") != "auth" or payload is None:
        return None
    if payload.get("role") != UserRole.INTERVIEWER:
        return None
    return int(payload["sub"])


def _events(
    graph: CompiledStateGraph, user_id: int, message: SocketMessage
) -> Iterator[dict[str, Any]]:
    """Choose the chat service call that matches the browser's message."""
    if message.type == "approval":
        return chat_service.stream_approval(
            graph,
            user_id,
            message.thread_id or "",
            bool(message.approved),
            message.feedback,
            message.arguments,
        )
    return chat_service.stream_message(
        graph, user_id, message.thread_id, message.text or ""
    )


@router.websocket("/chat")
async def chat(
    websocket: WebSocket, graph: CompiledStateGraph = Depends(get_recruiter_graph)
) -> None:
    await websocket.accept()
    user_id = await _sign_in(websocket)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.send_json({"type": "ready"})
    log_event(logger, "chat_connected", user_id=user_id)

    try:
        while True:
            try:
                message = SocketMessage.model_validate(await websocket.receive_json())
                # The graph is synchronous, so it runs in a worker thread and
                # its events are passed to the socket as they arrive.
                async for event in iterate_in_threadpool(
                    _events(graph, user_id, message)
                ):
                    await websocket.send_json(event)
            except (ValidationError, ValueError):
                await websocket.send_json(
                    {"type": "error", "message": "That message could not be read."}
                )
            except AppError as exc:
                await websocket.send_json({"type": "error", "message": exc.message})
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                log_event(
                    logger,
                    "chat_failed",
                    level=logging.ERROR,
                    user_id=user_id,
                    error_type=type(exc).__name__,
                )
                await websocket.send_json(
                    {"type": "error", "message": INTERNAL_ERROR_MESSAGE}
                )
    except WebSocketDisconnect:
        log_event(logger, "chat_disconnected", user_id=user_id)