"""The LangGraph agent graph (M2: classify -> route -> generate / refuse / clarify).

Deterministic routing wraps the LLM nodes. The graph produces a *candidate* SQL query; it is
deliberately not yet validated or executed here — the validation gate and read-only execution
arrive in later milestones, and no SQL is exposed to a client until it passes that gate.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.llm import LLMClient, LLMUsage
from app.agents.nodes.classify import run_classify
from app.agents.nodes.generate import run_generate
from app.agents.state import AgentState
from app.observability.logging import get_logger

logger = get_logger("app.agent")

ClientFor = Callable[[str], LLMClient]

_REFUSAL_OUT_OF_SCOPE = (
    "I'm designed to assist only with SQL and database-related tasks. "
    "Please ask a question related to the provided database schema."
)
_REFUSAL_DESTRUCTIVE = (
    "I can only generate read-only queries. I won't produce statements that modify data or "
    "schema (for example INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE)."
)


def _usage_record(node: str, usage: LLMUsage) -> dict[str, Any]:
    record: dict[str, Any] = {
        "node": node,
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "latency_ms": round(usage.latency_ms, 2),
    }
    logger.info("llm call", extra=record)
    return record


def build_agent_graph(*, client_for: ClientFor, schema_summary: str) -> Any:
    def load_context(state: AgentState) -> dict[str, Any]:
        return {"schema_summary": schema_summary, "status": "classifying"}

    def classify(state: AgentState) -> dict[str, Any]:
        data, usage = run_classify(state["user_input"], client_for("classify"))
        return {"intent": data.intent, "usages": [_usage_record("classify", usage)]}

    def generate(state: AgentState) -> dict[str, Any]:
        data, usage = run_generate(
            user_input=state["user_input"],
            schema_summary=state.get("schema_summary", schema_summary),
            previous_sql=state.get("previous_valid_sql"),
            client=client_for("generate"),
        )
        record = _usage_record("generate", usage)
        if data.clarification:
            return {
                "clarification": data.clarification,
                "assumptions": data.assumptions,
                "status": "clarification_required",
                "usages": [record],
            }
        return {
            "candidate_sql": data.sql,
            "assumptions": data.assumptions,
            "status": "generated",
            "usages": [record],
        }

    def refuse(state: AgentState) -> dict[str, Any]:
        intent = state.get("intent", "out_of_scope")
        reason = _REFUSAL_DESTRUCTIVE if intent == "destructive" else _REFUSAL_OUT_OF_SCOPE
        return {"refusal": reason, "status": "refused"}

    def clarify(state: AgentState) -> dict[str, Any]:
        return {"status": "clarification_required"}

    def route(state: AgentState) -> str:
        intent = state.get("intent", "out_of_scope")
        if intent in {"out_of_scope", "destructive"}:
            return "refuse"
        if intent == "clarify":
            return "clarify"
        return "generate"

    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context)
    graph.add_node("classify", classify)
    graph.add_node("generate", generate)
    graph.add_node("refuse", refuse)
    graph.add_node("clarify", clarify)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "classify")
    graph.add_conditional_edges(
        "classify",
        route,
        {"generate": "generate", "refuse": "refuse", "clarify": "clarify"},
    )
    graph.add_edge("generate", END)
    graph.add_edge("refuse", END)
    graph.add_edge("clarify", END)
    return graph.compile()
