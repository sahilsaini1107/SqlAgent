from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import suppress
from typing import Any

import sqlglot
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.context import format_history, is_rewritten
from app.dependencies import get_graph, get_session_store
from app.infra.session_store import SessionStore
from app.observability.logging import get_logger, trace_id_var
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
logger = get_logger("app.chat")

_STREAM_ERROR = "The assistant hit an unexpected error while answering. Please try again."


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _run_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _discard_run(graph: Any, run_id: str) -> None:
    """Drop a completed run's checkpoints so the checkpoint DB doesn't grow unbounded. A run that
    crashes or is interrupted is *not* discarded, so it survives for resume."""
    checkpointer = getattr(graph, "checkpointer", None)
    if checkpointer is not None:
        with suppress(Exception):  # cleanup is best-effort; never fail a served turn over it
            checkpointer.delete_thread(run_id)


def _resolve_conversation(store: SessionStore, conversation_id: str | None) -> str:
    if conversation_id is None:
        return store.create_conversation()
    if not store.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return conversation_id


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _usage_view(usages: list[dict[str, Any]]) -> UsageView:
    # Telemetry is best-effort; a malformed record must never crash the user-facing response.
    calls = [
        UsageCall(
            node=str(u.get("node", "")),
            model=str(u.get("model", "")),
            input_tokens=_int(u.get("input_tokens", 0)),
            output_tokens=_int(u.get("output_tokens", 0)),
            latency_ms=_float(u.get("latency_ms", 0.0)),
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


def _transpile(sql: str, dialect: str) -> tuple[str, bool]:
    """Render the validated (SQLite) SQL in the requested dialect.

    Returns ``(sql, ok)``. On a transpile failure it falls back to the original SQLite text and
    returns ``ok=False`` so the caller can tell the client the dialect wasn't applied rather
    than silently mislabelling SQLite SQL as e.g. Postgres.
    """
    if dialect == "sqlite":
        return sql, True
    try:
        return sqlglot.transpile(sql, read="sqlite", write=dialect, pretty=True)[0], True
    except Exception as err:
        logger.warning(
            "dialect transpile failed", extra={"dialect": dialect, "error": str(err)}
        )
        return sql, False


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    graph: Any = Depends(get_graph),
    store: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    conversation_id = _resolve_conversation(store, req.conversation_id)
    previous_sql = store.last_validated_sql(conversation_id)
    history = format_history(store.get_history(conversation_id))

    # Each turn runs under its own checkpoint thread: durable during the run, and discarded on
    # success. A fresh thread per turn means no state from the previous turn can bleed in.
    run_id = uuid.uuid4().hex
    state: dict[str, Any] = graph.invoke(
        {
            "user_input": req.message,
            "execution_requested": req.execute,
            "previous_valid_sql": previous_sql,
            "conversation_history": history,
        },
        config=_run_config(run_id),
    )

    response = _to_response(
        conversation_id, state, trace_id_var.get(), req.dialect, user_input=req.message
    )
    _persist_turn(
        store, conversation_id, req.message, response, canonical_sql=state.get("final_sql")
    )
    _discard_run(graph, run_id)
    return response


@router.post("/chat/stream")
def chat_stream(
    req: ChatRequest,
    graph: Any = Depends(get_graph),
    store: SessionStore = Depends(get_session_store),
) -> StreamingResponse:
    conversation_id = _resolve_conversation(store, req.conversation_id)
    trace_id = trace_id_var.get()  # captured here; the context resets before the body streams
    dialect = req.dialect

    # Resume an interrupted run from its last checkpoint, or start a fresh run. On resume we pass
    # no input so the graph continues from where it stopped; the client re-supplies the turn
    # context (conversation_id/message/dialect) in the request.
    if req.resume_run_id:
        run_id = req.resume_run_id
        snapshot = graph.get_state(_run_config(run_id))
        if not getattr(snapshot, "values", None):
            raise HTTPException(status_code=404, detail="run not found or already completed")
        stream_input = None
    else:
        run_id = uuid.uuid4().hex
        previous_sql = store.last_validated_sql(conversation_id)
        history = format_history(store.get_history(conversation_id))
        stream_input = {
            "user_input": req.message,
            "execution_requested": req.execute,
            "previous_valid_sql": previous_sql,
            "conversation_history": history,
        }
    config = _run_config(run_id)

    def event_stream() -> Iterator[str]:
        yield _sse(
            "start",
            {"conversation_id": conversation_id, "trace_id": trace_id, "run_id": run_id},
        )
        final_state: dict[str, Any] = {}
        try:
            for state in graph.stream(stream_input, config=config, stream_mode="values"):
                final_state = state
                status = state.get("status")
                if status:
                    yield _sse("stage", {"status": status})
        except GeneratorExit:  # client disconnected — keep the checkpoint so the run can resume
            logger.info(
                "chat stream disconnected",
                extra={"conversation_id": conversation_id, "run_id": run_id},
            )
            raise
        except Exception:
            logger.exception(
                "chat stream failed",
                extra={"conversation_id": conversation_id, "run_id": run_id},
            )
            yield _sse("error", {"trace_id": trace_id, "run_id": run_id, "message": _STREAM_ERROR})
            return
        if not final_state:  # resumed a run that had already completed — read the saved state
            saved = graph.get_state(config)
            final_state = getattr(saved, "values", {}) or {}
        response = _to_response(
            conversation_id, final_state, trace_id, dialect, user_input=req.message
        )
        _persist_turn(
            store,
            conversation_id,
            req.message,
            response,
            canonical_sql=final_state.get("final_sql"),
        )
        _discard_run(graph, run_id)
        yield _sse("result", response.model_dump())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _persist_turn(
    store: SessionStore,
    conversation_id: str,
    user_message: str,
    response: ChatResponse,
    *,
    canonical_sql: str | None,
) -> None:
    # Persist the user message and the assistant reply together, at the end of the turn, so a
    # failure never leaves an orphaned user message. The canonical SQLite SQL (not the
    # transpiled display SQL) is stored so follow-ups re-validate and execute cleanly.
    store.add_turn(
        conversation_id,
        user_content=user_message,
        assistant_content=(
            response.explanation
            or response.refusal
            or response.clarification
            or response.error
        ),
        assistant_sql=canonical_sql,
        assistant_status=response.status,
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
    conversation_id: str,
    state: dict[str, Any],
    trace_id: str,
    dialect: str = "sqlite",
    *,
    user_input: str = "",
) -> ChatResponse:
    issues = state.get("validation_issues", [])
    resolved = state.get("resolved_request") or ""
    result = state.get("query_result")
    final_sql = state.get("final_sql")
    rendered_sql: str | None = None
    rendered_dialect = dialect
    if final_sql:
        rendered_sql, ok = _transpile(final_sql, dialect)
        # If the requested dialect couldn't be produced, report the SQL as the SQLite it
        # actually is rather than mislabelling it.
        rendered_dialect = dialect if ok else "sqlite"
    return ChatResponse(
        conversation_id=conversation_id,
        trace_id=trace_id,
        intent=state.get("intent"),
        status=state.get("status", "unknown"),
        sql=rendered_sql,
        explanation=state.get("explanation"),
        assumptions=state.get("assumptions", []),
        clarification=state.get("clarification"),
        refusal=state.get("refusal"),
        error=state.get("error"),
        validation=ValidationView(
            passed=not issues,
            issues=issues,
            warnings=state.get("warnings", []),
        ),
        result=ResultView(**result) if result else None,
        dialect=rendered_dialect,
        plan=state.get("query_plan"),
        usage=_usage_view(state.get("usages", [])),
        interpreted_as=resolved if user_input and is_rewritten(user_input, resolved) else None,
    )
