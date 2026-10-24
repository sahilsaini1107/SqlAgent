from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

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


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    graph: Any = Depends(get_graph),
    store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    if req.conversation_id is None:
        conversation_id = store.create_conversation()
    else:
        conversation_id = req.conversation_id
        if not store.conversation_exists(conversation_id):
            raise HTTPException(status_code=404, detail="conversation not found")

    previous_sql = store.last_validated_sql(conversation_id)
    store.add_message(conversation_id, "user", content=req.message)

    state: dict[str, Any] = graph.invoke(
        {
            "user_input": req.message,
            "execution_requested": req.execute,
            "previous_valid_sql": previous_sql,
        }
    )

    response = _to_response(conversation_id, state)
    store.add_message(
        conversation_id,
        "assistant",
        content=response.explanation or response.refusal or response.clarification,
        sql=response.sql,
        status=response.status,
    )
    return response


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


def _to_response(conversation_id: str, state: dict[str, Any]) -> ChatResponse:
    issues = state.get("validation_issues", [])
    result = state.get("query_result")
    return ChatResponse(
        conversation_id=conversation_id,
        trace_id=trace_id_var.get(),
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
