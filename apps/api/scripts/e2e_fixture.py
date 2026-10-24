"""LOCAL TEST ONLY: real API/graph/database with a deterministic model substitute.

Run from apps/api with WEB_DIST_DIR and an isolated APP_DB_DIR configured:
    python -m uvicorn scripts.e2e_fixture:app --port 8012
Never use this entry point for a deployment or model-accuracy evaluation.
"""

from __future__ import annotations

import time

from app.agents.contracts import Classification, Explanation, GeneratedSQL
from app.agents.graph import build_agent_graph
from app.agents.llm import LLMUsage, StructuredResult
from app.config import settings
from app.dependencies import get_graph
from app.domain.schema_catalog import SchemaCatalog
from app.domain.sql_validator import SqlValidator
from app.infra.sqlite_adapter import SqliteReadOnlyAdapter
from app.main import app


class FixtureLLM:
    def structured(self, *, system, user, schema):
        time.sleep(0.15)
        text = user.lower()
        if "simulate provider failure" in text:
            raise RuntimeError("Simulated provider failure for browser acceptance testing")
        if "slow request" in text:
            time.sleep(3)
        if schema is Classification:
            intent = "generate"
            if "world cup" in text:
                intent = "out_of_scope"
            elif "delete" in text:
                intent = "destructive"
            elif "ambiguous" in text:
                intent = "clarify"
            elif "optimize" in text:
                intent = "optimize"
            elif "fix" in text:
                intent = "debug"
            return StructuredResult(Classification(intent=intent, confidence=1), self.usage())
        if schema is GeneratedSQL:
            sql = "SELECT id, name FROM warehouses ORDER BY id"
            if "first three" in text:
                sql += " LIMIT 3"
            if "invalid model output" in text:
                sql = "DROP TABLE customers"
            return StructuredResult(GeneratedSQL(sql=sql), self.usage())
        if schema is Explanation:
            return StructuredResult(
                Explanation(explanation="This query lists warehouse IDs and names in ID order."),
                self.usage(),
            )
        raise AssertionError(schema)

    @staticmethod
    def usage():
        return LLMUsage(
            model="SCRIPTED-E2E-FIXTURE", input_tokens=0, output_tokens=0, latency_ms=150,
        )


catalog = SchemaCatalog.from_sqlite(settings.sample_db_path)
adapter = SqliteReadOnlyAdapter(settings.sample_db_path)
graph = build_agent_graph(
    client_for=lambda _: FixtureLLM(),
    schema_summary=catalog.compact_summary(),
    validator=SqlValidator(catalog, execute_check=adapter.explain),
    adapter=adapter,
)
app.dependency_overrides[get_graph] = lambda: graph
