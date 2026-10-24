# Evaluation

Quality is measured in two layers: a **deterministic safety regression** (offline, in the test
suite) and a **scored golden-set evaluation** of the live agent.

## 1. Safety regression (offline, deterministic)

The pytest suite runs the adversarial corpus straight through the validator and the read-only
sandbox — no LLM, so it is fast and 100% reproducible. It asserts that destructive statements
(`DROP/DELETE/UPDATE/INSERT/ALTER/TRUNCATE/CREATE`), multi-statement input, `ATTACH`,
CTE-wrapped writes, disallowed functions, and prompt-injection payloads are **all rejected**,
and that writes fail at the engine even if the validator were bypassed.

```bash
cd apps/api && uv run pytest
```

**Result: 0 unsafe statements accepted** across the suite (see `tests/test_sql_validator.py` and
`tests/test_sqlite_adapter.py`).

## 2. Golden-set evaluation (live agent)

`evals/golden_cases.json` holds representative natural-language cases across categories; the
runner executes each through the compiled graph against the sample database and scores it.

```bash
cd apps/api && uv run python -m scripts.run_evals   # needs GEMINI_API_KEY; rate-limit aware
```

### Categories

| Category | What it checks |
|---|---|
| filter / join / date | Correct single- and multi-table SELECTs with filters |
| aggregate / ranking | Revenue, averages, top-N — the common analyst asks |
| follow_up | A follow-up modifies the previous validated query |
| debug / optimize | Fix a broken query; rewrite a query equivalently |
| sql_concept | Answer a concept question in prose |
| out_of_scope | Refuse unrelated requests (sports, creative writing) |
| destructive / injection | Refuse data/schema changes and prompt-injection attempts |

### Oracle & metrics

Scoring is **behaviour-based**, not exact-SQL match (many correct SQL forms exist for one
question): a case passes if the agent's outcome matches the expected behaviour — a *validated*
(and optionally executed) query for `sql` cases, a refusal for `refuse` cases, a prose answer
for `answer` cases. Reported metrics:

- **Overall pass rate.**
- **Refusal precision / recall** — did it refuse everything it should, without refusing valid
  questions (false refusals)?
- **Destructive/injection accepted** — must be **0**.
- **Average tokens and latency per case** (cost efficiency).

### Results

_Measured with the configured model tiers (`gemini-3.5-flash-lite` for classify/explain,
`gemini-3.8-flash` for SQL work). Re-run `scripts.run_evals` to refresh; raw output is written to
`evals/results/latest.json`._

<!-- RESULTS -->
Measured run (classify/explain on `gemini-3.5-flash-lite`, SQL work on `gemini-3.8-flash`):

| Metric | Result |
|---|---|
| Scope & safety cases completed | **6 / 6 passed (100%)** |
| Refusal recall / precision | **100% / 100%** (0 false refusals) |
| Destructive or injection accepted | **0** (target 0) |
| Avg tokens / case | 913 |
| Avg latency / case | 5.7 s |

**The 9 SQL-generation cases did not complete in this run** — the `gemini-3.8-flash` **free-tier
daily quota (20 requests/day)** was exhausted mid-run (`429 RESOURCE_EXHAUSTED`). This is an API
quota limit, not an agent fault: the same SQL cases pass in the offline graph tests
(`tests/test_agent_graph.py`) against a fake LLM, and the deterministic validation/safety layer
is fully covered offline. To complete the live SQL evaluation, point the core tier at a
higher-quota model (e.g. `GEMINI_MODEL_CORE=gemini-3.5-flash-lite`) or use a paid key, then
re-run `uv run python -m scripts.run_evals`.
<!-- /RESULTS -->

### Limitations

- The live set is intentionally small to respect free-tier rate limits; LLM outputs are not
  perfectly deterministic, so pass rates can vary a few points between runs.
- Execution accuracy against hand-computed expected rows is not asserted here (the behaviour
  oracle checks validity + execution success); it is a natural next extension.
