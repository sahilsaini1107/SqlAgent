from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_graph, get_session_store
from app.infra.session_store import SessionStore
from app.observability.logging import trace_id_var
from app.schemas.requests import ChatRequest
from app.schemas.responses import (
    ChatResponse,
    ConversationHistory,
    MessageView,
    ResultView,
    ValidationView,
)

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _resolve_conversation(store: SessionStore, conversation_id: str | None) -> str:
    if conversation_id is None:
        return store.create_conversation()
    if not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation_id


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    graph: Any = Depends(get_graph),
    store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    conversation_id = _resolve_conversation(store, req.conversation_id)
    previous_sql = store.last_validated_sql(conversation_id)
    store.add_message(conversation_id, "user", content=req.message)

    state: dict[str, Any] = graph.invoke(
        {
            "user_input": req.message,
            "execution_requested": req.execute,
            "previous_valid_sql": previous_sql,
        }
    )

    response = _to_response(conversation_id, state, trace_id_var.get())
    _persist_assistant(store, conversation_id, response)
    return response


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest,
    graph: Any = Depends(get_graph),
    store: SessionStore = Depends(get_session_store),
) -> StreamingResponse:
    conversation_id = _resolve_conversation(store, req.conversation_id)
    previous_sql = store.last_validated_sql(conversation_id)
    store.add_message(conversation_id, "user", content=req.message)
    trace_id = trace_id_var.get()  # captured here; the context resets before the body streams
    inputs = {
        "user_input": req.message,
        "execution_requested": req.execute,
        "previous_valid_sql": previous_sql,
    }

    def event_stream() -> Iterator[str]:
        yield _sse("start", {"conversation_id": conversation_id, "trace_id": trace_id})
        final_state: dict[str, Any] = {}
        for state in graph.stream(inputs, stream_mode="values"):
            final_state = state
            status = state.get("status")
            if status:
                yield _sse("stage", {"status": status})
        response = _to_response(conversation_id, final_state, trace_id)
        _persist_assistant(store, conversation_id, response)
        yield _sse("result", response.model_dump())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _persist_assistant(
    store: SessionStore, conversation_id: str, response: ChatResponse
) -> None:
    store.add_message(
        conversation_id,
        "assistant",
        content=response.explanation or response.refusal or response.clarification,
        sql=response.sql,
        status=response.status,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationHistory)
def get_conversation(
    conversation_id: str,
    store: SessionStore = Depends(get_session_store),
) -> ConversationHistory:
    if not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    messages = [MessageView(**row) for row in store.get_history(conversation_id)]
    return ConversationHistory(conversation_id=conversation_id, messages=messages)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    store: SessionStore = Depends(get_session_store),
) -> None:
    store.delete_conversation(conversation_id)


def _to_response(conversation_id: str, state: dict[str, Any], trace_id: str) -> ChatResponse:
    issues = state.get("validation_issues", [])
    result = state.get("query_result")
    return ChatResponse(
        conversation_id=conversation_id,
        trace_id=trace_id,
        intent=state.get("intent"),
        status=state.get("status", "unknown"),
        sql=state.get("final_sql"),
        explanation=state.get("explanation"),
        assumptions=state.get("assumptions", []),
        clarification=state.get("clarification"),
        refusal=state.get("refusal"),
        validation=ValidationView(
            passed=not issues,
            issues=issues,
            warnings=state.get("warnings", []),
        ),
        result=ResultView(**result) if result else None,
    )
