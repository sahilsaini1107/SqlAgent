"""Rate-limit-aware live smoke test against the real Gemini agent and the sample database.

Runs a small, representative set of prompts through the compiled graph (not the HTTP server),
pacing requests to stay within free-tier limits and backing off on rate-limit errors.

    uv run python scripts/smoke_live.py

Requires a valid GEMINI_API_KEY in .env. Consumes a small amount of quota (~8 prompts).
"""

from __future__ import annotations

import time
from typing import Any

from app.agents.factory import default_client_for
from app.agents.graph import build_agent_graph
from app.config import settings
from app.domain.query_policy import QueryLimits
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter

DELAY_S = 7.0          # pacing between prompts (stay well under free-tier RPM)
BACKOFF_S = 30.0       # extra wait after a rate-limit error
MAX_RETRIES = 1

# (label, prompt, execute, is_follow_up)
PROMPTS: list[tuple[str, str, bool, bool]] = [
    ("filter", "Show all active products in the Electronics department", False, False),
    ("join", "How many customers have a shipping address in California?", True, False),
    ("aggregate", "Top 5 products by total revenue in USD", True, False),
    ("follow_up", "Actually just show the top 3", True, True),
    ("window", "Best-selling product in each department by revenue", True, False),
    ("time_series", "Monthly revenue in USD for 2025 with month-over-month growth", True, False),
    ("out_of_scope", "Who won the FIFA World Cup in 2022?", False, False),
    ("destructive", "Delete every cancelled order", False, False),
]


def _is_rate_limit(error: Exception) -> bool:
    text = str(error).lower()
    return any(token in text for token in ("429", "rate limit", "quota", "resource_exhausted"))


def _run(graph: Any, message: str, execute: bool, previous_sql: str | None) -> dict[str, Any]:
    inputs = {
        "user_input": message,
        "execution_requested": execute,
        "previous_valid_sql": previous_sql,
    }
    for attempt in range(MAX_RETRIES + 1):
        try:
            return dict(graph.invoke(inputs))
        except Exception as err:  # noqa: BLE001 - smoke harness surfaces any failure
            if _is_rate_limit(err) and attempt < MAX_RETRIES:
                print(f"    rate-limited; backing off {BACKOFF_S:.0f}s...")
                time.sleep(BACKOFF_S)
                continue
            raise
    return {}


def main() -> int:
    if not settings.gemini_api_key:
        print("GEMINI_API_KEY is not set — skipping live smoke test.")
        return 1

    catalog = SchemaCatalog.from_sqlite(settings.sample_db_path)
    adapter = SqliteReadOnlyAdapter(settings.sample_db_path)
    validator = SqlValidator(catalog, execute_check=adapter.explain)
    graph = build_agent_graph(
        client_for=default_client_for(),
        schema_summary=catalog.compact_summary(),
        validator=validator,
        adapter=adapter,
        limits=QueryLimits(max_rows=settings.max_rows, timeout_ms=settings.query_timeout_ms),
    )

    print(f"Model tiers: default={settings.gemini_model} core={settings.gemini_model_core}")
    print(f"Schema: {len(catalog.table_names())} tables\n")

    previous_sql: str | None = None
    failures = 0
    for index, (label, prompt, execute, is_follow_up) in enumerate(PROMPTS):
        print(f"[{label}] {prompt}")
        try:
            state = _run(graph, prompt, execute, previous_sql if is_follow_up else None)
        except Exception as err:  # noqa: BLE001
            print(f"    ERROR: {err}\n")
            failures += 1
            time.sleep(DELAY_S)
            continue

        status = state.get("status")
        intent = state.get("intent")
        sql = state.get("final_sql")
        usages = state.get("usages", [])
        tokens = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usages)
        print(f"    intent={intent} status={status} tokens~{tokens}")
        if sql:
            print(f"    sql: {' '.join(sql.split())[:120]}")
            previous_sql = sql
        if state.get("query_result"):
            print(f"    rows: {state['query_result']['row_count']}")
        if state.get("refusal"):
            print(f"    refusal: {state['refusal'][:80]}")
        if state.get("clarification"):
            print(f"    clarification: {state['clarification'][:80]}")
        print()

        if index < len(PROMPTS) - 1:
            time.sleep(DELAY_S)

    print(f"Done. {len(PROMPTS) - failures}/{len(PROMPTS)} prompts completed without error.")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
