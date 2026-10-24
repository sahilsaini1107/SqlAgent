from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import sqlglot
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
    UsageCall,
    UsageView,
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


def _usage_view(usages: list[dict[str, Any]]) -> UsageView:
    calls = [
        UsageCall(
            node=str(u.get("node", "")),
            model=str(u.get("model", "")),
            input_tokens=int(u.get("input_tokens", 0)),
            output_tokens=int(u.get("output_tokens", 0)),
            latency_ms=float(u.get("latency_ms", 0.0)),
        )
        for u in usages
    ]
    input_tokens = sum(c.input_tokens for c in calls)
    output_tokens = sum(c.output_tokens for c in calls)
    return UsageView(
        calls=calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        llm_calls=len(calls),
    )


def _transpile(sql: str, dialect: str) -> str:
    """Render the validated (SQLite) SQL in the requested dialect. Falls back to the original."""
    if dialect == "sqlite":
        return sql
    try:
        return sqlglot.transpile(sql, read="sqlite", write=dialect, pretty=True)[0]
    except Exception:
        return sql


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

    response = _to_response(conversation_id, state, trace_id_var.get(), req.dialect)
    _persist_assistant(store, conversation_id, response, canonical_sql=state.get("final_sql"))
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
    dialect = req.dialect
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
        response = _to_response(conversation_id, final_state, trace_id, dialect)
        _persist_assistant(
            store, conversation_id, response, canonical_sql=final_state.get("final_sql")
        )
        yield _sse("result", response.model_dump())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _persist_assistant(
    store: SessionStore,
    conversation_id: str,
    response: ChatResponse,
    *,
    canonical_sql: str | None,
) -> None:
    # Persist the canonical SQLite SQL (not the transpiled display SQL) so follow-ups are
    # grounded in a query the agent can re-validate and execute.
    store.add_message(
        conversation_id,
        "assistant",
        content=response.explanation or response.refusal or response.clarification,
        sql=canonical_sql,
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


def _to_response(
    conversation_id: str, state: dict[str, Any], trace_id: str, dialect: str = "sqlite"
) -> ChatResponse:
    issues = state.get("validation_issues", [])
    result = state.get("query_result")
    final_sql = state.get("final_sql")
    return ChatResponse(
        conversation_id=conversation_id,
        trace_id=trace_id,
        intent=state.get("intent"),
        status=state.get("status", "unknown"),
        sql=_transpile(final_sql, dialect) if final_sql else None,
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
        dialect=dialect,
        plan=state.get("query_plan"),
        usage=_usage_view(state.get("usages", [])),
    )
