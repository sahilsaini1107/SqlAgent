"""The LangGraph agent graph.

    load_context -> classify -> route -> refuse / clarify / generate
    generate -> (clarification? end) : validate
    validate -> pass -> execute (if requested) / end
             -> fail, retries remain -> repair -> validate
             -> fail, exhausted -> end (validation_failed, no SQL returned)

Deterministic routing wraps the LLM nodes, and the deterministic validation gate sits between
the model's candidate SQL and anything a client ever sees. No SQL reaches ``final_sql`` (or
execution) unless the validator approves it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.llm import LLMClient, LLMUsage
from app.agents.nodes.classify import run_classify
from app.agents.nodes.explain import run_answer, run_explain
from app.agents.nodes.generate import run_generate
from app.agents.nodes.optimize import run_optimize
from app.agents.nodes.repair import run_repair
from app.agents.state import AgentState
from app.domain.query_policy import QueryLimits
from app.domain.sql_validator import SqlValidator
from app.infra.db_adapter import DatabaseAdapter
from app.observability.logging import get_logger

logger = get_logger("app.agent")

ClientFor = Callable[[str], LLMClient]

MAX_REPAIR_ATTEMPTS = 2

_REFUSAL_OUT_OF_SCOPE = (
    "I'm designed to assist only with SQL and database-related tasks. "
    "Please ask a question related to the provided database schema."
)
_REFUSAL_DESTRUCTIVE = (
    "I can only generate read-only queries. I won't produce statements that modify data or "
    "schema (for example INSERT, UPDATE, DELETE, DROP, ALTER, or TRUNCATE)."
)


def _safe_plan(adapter: DatabaseAdapter, sql: str) -> list[str] | None:
    try:
        return adapter.explain_plan(sql)
    except Exception:  # cost estimate is best-effort; never fail the request over it
        return None


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


def build_agent_graph(
    *,
    client_for: ClientFor,
    schema_summary: str,
    validator: SqlValidator,
    adapter: DatabaseAdapter | None = None,
    limits: QueryLimits | None = None,
) -> Any:
    query_limits = limits or QueryLimits()

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

    def validate(state: AgentState) -> dict[str, Any]:
        sql = state.get("candidate_sql")
        if not sql:
            return {
                "final_sql": None,
                "status": "validation_failed",
                "validation_issues": [
                    {"code": "PARSE_ERROR", "message": "No SQL produced.", "severity": "error"}
                ],
            }
        result = validator.validate(sql)
        update: dict[str, Any] = {
            "validation_issues": [i.as_dict() for i in result.errors],
            "warnings": [i.as_dict() for i in result.warnings],
        }
        if result.passed:
            update["final_sql"] = result.final_sql
            update["status"] = "validated"
            if adapter is not None and result.final_sql:
                update["query_plan"] = _safe_plan(adapter, result.final_sql)
        else:
            update["final_sql"] = None
            update["status"] = "validation_failed"
        return update

    def optimize(state: AgentState) -> dict[str, Any]:
        data, usage = run_optimize(
            user_input=state["user_input"],
            schema_summary=state.get("schema_summary", schema_summary),
            client=client_for("optimize"),
        )
        record = _usage_record("optimize", usage)
        if data.clarification:
            return {
                "clarification": data.clarification,
                "status": "clarification_required",
                "usages": [record],
            }
        return {
            "candidate_sql": data.sql,
            "assumptions": data.assumptions,
            "status": "generated",
            "usages": [record],
        }

    def answer(state: AgentState) -> dict[str, Any]:
        data, usage = run_answer(
            user_input=state["user_input"],
            schema_summary=state.get("schema_summary", schema_summary),
            client=client_for("explain"),
        )
        return {
            "explanation": data.explanation,
            "status": "answered",
            "usages": [_usage_record("answer", usage)],
        }

    def explain(state: AgentState) -> dict[str, Any]:
        final_sql = state.get("final_sql")
        if not final_sql:
            return {}
        data, usage = run_explain(
            final_sql=final_sql,
            schema_summary=state.get("schema_summary", schema_summary),
            client=client_for("explain"),
        )
        return {"explanation": data.explanation, "usages": [_usage_record("explain", usage)]}

    def repair(state: AgentState) -> dict[str, Any]:
        data, usage = run_repair(
            user_input=state["user_input"],
            schema_summary=state.get("schema_summary", schema_summary),
            failed_sql=state.get("candidate_sql") or "",
            issues=state.get("validation_issues", []),
            client=client_for("repair"),
        )
        return {
            "candidate_sql": data.sql,
            "retry_count": state.get("retry_count", 0) + 1,
            "usages": [_usage_record("repair", usage)],
        }

    def execute(state: AgentState) -> dict[str, Any]:
        assert adapter is not None  # only routed here when an adapter is configured
        final_sql = state.get("final_sql")
        if not final_sql:
            return {"status": "execution_failed", "query_result": None}
        try:
            result = adapter.execute_read_only(final_sql, query_limits)
        except Exception as err:
            logger.warning("execution failed", extra={"error": str(err)})
            return {"status": "execution_failed", "query_result": None}
        return {
            "status": "executed",
            "query_result": {
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
                "truncated": result.truncated,
                "duration_ms": result.duration_ms,
            },
        }

    def refuse(state: AgentState) -> dict[str, Any]:
        intent = state.get("intent", "out_of_scope")
        reason = _REFUSAL_DESTRUCTIVE if intent == "destructive" else _REFUSAL_OUT_OF_SCOPE
        return {"refusal": reason, "status": "refused"}

    def clarify(state: AgentState) -> dict[str, Any]:
        return {"status": "clarification_required"}

    def route_intent(state: AgentState) -> str:
        intent = state.get("intent", "out_of_scope")
        if intent in {"out_of_scope", "destructive"}:
            return "refuse"
        if intent == "clarify":
            return "clarify"
        if intent in {"explain", "sql_concept"}:
            return "answer"
        if intent == "optimize":
            return "optimize"
        return "generate"

    def after_generate(state: AgentState) -> str:
        return "end" if state.get("status") == "clarification_required" else "validate"

    def after_validate(state: AgentState) -> str:
        if state.get("final_sql"):
            if state.get("execution_requested") and adapter is not None:
                return "execute"
            return "explain"
        if state.get("retry_count", 0) < MAX_REPAIR_ATTEMPTS:
            return "repair"
        return "end"

    graph = StateGraph(AgentState)
    graph.add_node("load_context", load_context)
    graph.add_node("classify", classify)
    graph.add_node("generate", generate)
    graph.add_node("optimize", optimize)
    graph.add_node("validate", validate)
    graph.add_node("repair", repair)
    graph.add_node("execute", execute)
    graph.add_node("explain", explain)
    graph.add_node("answer", answer)
    graph.add_node("refuse", refuse)
    graph.add_node("clarify", clarify)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "classify")
    graph.add_conditional_edges(
        "classify",
        route_intent,
        {
            "generate": "generate",
            "optimize": "optimize",
            "answer": "answer",
            "refuse": "refuse",
            "clarify": "clarify",
        },
    )
    graph.add_conditional_edges("generate", after_generate, {"validate": "validate", "end": END})
    graph.add_conditional_edges("optimize", after_generate, {"validate": "validate", "end": END})
    graph.add_conditional_edges(
        "validate",
        after_validate,
        {"execute": "execute", "explain": "explain", "repair": "repair", "end": END},
    )
    graph.add_edge("repair", "validate")
    graph.add_edge("execute", "explain")
    graph.add_edge("explain", END)
    graph.add_edge("answer", END)
    graph.add_edge("refuse", END)
    graph.add_edge("clarify", END)
    return graph.compile()
