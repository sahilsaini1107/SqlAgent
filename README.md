# SQL Agent

A schema-grounded, **read-only** natural-language → SQL assistant. It turns plain-English
questions into validated SQL against a known database schema, explains the query, and can
run it safely. It specialises in SQL/database tasks and politely refuses anything else.

Built with **LangGraph** (agent orchestration), **FastAPI** (backend), **SQLGlot**
(deterministic SQL validation), **SQLite** (sample database), **Gemini** (`langchain-google-genai`),
and **React + TypeScript** (frontend).

> **Safety first:** the model proposes SQL; deterministic code and a read-only database
> layer decide. Destructive statements (`DELETE/UPDATE/INSERT/DROP/ALTER/TRUNCATE`) are
> never generated or executed.

## Live demo

- **App:** _<deployed link — add after deploying; see `docs/DEPLOY.md`>_
- **Demo video:** _<3–5 min walkthrough — add link>_

## Features

**Core**
- Natural language → SQL, grounded in the provided schema.
- Deterministic validation before anything is returned: tables, columns, joins, syntax, and a
  strict read-only policy (see `docs/architecture.md`).
- Plain-English explanation of every generated query.
- SQL **optimization** (equivalent, cleaner rewrite + advisory index notes) and **debugging**
  (fix a pasted query and explain the change).
- Conversation context — follow-ups modify the last *validated* query ("only California").
- Refuses out-of-scope and destructive requests; asks for clarification when ambiguous.
- UI: chat, SQL panel, explanation panel, results table, conversation history, loading/error
  states, and copy-SQL — all required panels.

**Bonus (implemented)**
- Query execution against the sample database, with row cap + timeout.
- SQL **syntax highlighting**, **streaming** responses, **dark mode**.
- **CSV / SQL download**, result latency surfaced.
- Prompt-injection handling (user text treated as data; enforced by the code gate + DB layer).
- **Dockerized** deployment; unit, integration, and adversarial tests.

**Roadmap:** multiple SQL dialects (PostgreSQL) behind the existing `DatabaseAdapter` boundary.

## How it works

```
user → classify → (refuse | clarify | answer | optimize | generate)
generate/optimize → validate → (repair ≤2 → validate) → execute? → explain → respond
```

A typed LangGraph `StateGraph` routes each request. The LLM only ever produces a *candidate*
query; the **validation gate** (SQLGlot AST + schema binding + join checks + real-engine
`EXPLAIN`) and the **read-only SQLite sandbox** (`mode=ro` + `query_only` + authorizer +
timeout + row cap) are independent, deterministic layers that sit after the model. Per-node
telemetry (model, tokens, latency) is recorded for traceability, and nodes are routed across
Gemini tiers for cost efficiency (cheap tier for classify/explain, stronger tier for SQL work).

Full details: **`docs/architecture.md`** (diagrams + trust boundaries) and **`docs/prompts.md`**
(every prompt and its output schema).

## Quick start (local)

Prerequisites: **Python 3.12**, **Node 22**, and [**uv**](https://docs.astral.sh/uv/).

### Backend

```bash
cd apps/api
uv sync
uv run python -m app.db.build   # generate data/sample.sqlite (deterministic)
uv run uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health   ·   API docs at /docs
```

### Frontend

```bash
cd apps/web
npm install
npm run dev     # http://localhost:5173 — proxies /api and /health to the backend
```

Set `GEMINI_API_KEY` in `.env` first (see Configuration) or chat requests will fail.

### Sample database

`data/schema.sql` models an international online retailer in 28 tables, and
`app/db/seed.py` fills it by simulating Jan 2023 – Sep 2026 of trading with a fixed seed, so
every build is identical. Roughly 2,500 customers, 8,000 orders, 16,000 order lines, 160
products in 400 variants, 17,000 carts, 1,000 returns and 1,200 support tickets (~10 MB).

| Area | Tables |
|---|---|
| Catalogue | `categories` (3-level tree), `brands`, `products`, `product_variants`, `product_price_history` |
| Supply chain | `suppliers`, `warehouses`, `inventory`, `purchase_orders`, `purchase_order_items` |
| Customers & marketing | `customers` (tier, segment, acquisition channel, referrals), `addresses`, `marketing_campaigns`, `coupons` |
| Orders | `orders`, `order_items`, `order_status_history`, `order_coupons`, `payments`, `shipments`, `returns`, `return_items` |
| Behaviour & service | `carts`, `cart_items`, `wishlist_items`, `reviews`, `support_tickets` |
| Finance | `exchange_rates` (monthly, USD/EUR/GBP/CAD/AUD) |

The data is internally consistent: line prices follow each product's price history and the
month's exchange rate, order totals add up, demand has growth and seasonality (Black Friday,
holidays, summer), late deliveries drive support tickets, and loyalty tiers come from lifetime
spend. Column comments in `schema.sql` (allowed values, currencies, formulas) are passed to the
agent with the schema. Rebuild after changing the schema or generator.

## Configuration

Copy `.env.example` to `.env` and fill in your values. `.env` is git-ignored — never commit
real credentials.

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | Default/high-volume tier — classify, explain (default `gemini-3.5-flash-lite`) |
| `GEMINI_MODEL_CORE` | Core execution tier — generate, repair, optimize (default `gemini-3.8-flash`) |
| `GEMINI_MODEL_PRO` | Complex synthesis tier, reserved/opt-in (default `gemini-3.8-flash`) |
| `ENVIRONMENT` | `development` / `production` |
| `LOG_LEVEL` | Log level |
| `APP_DB_DIR` | Writable dir for the conversation DB (set to `/tmp` on serverless) |

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/schema` | Authorized schema metadata (tables, columns, FKs) |
| `POST` | `/api/chat` | Send a message; returns validated SQL, explanation, and (optional) results |
| `POST` | `/api/chat/stream` | Same, as a Server-Sent Events stream (stage updates + final result) |
| `GET` | `/api/conversations/{id}` | Conversation transcript |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation |

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Top 5 products by total revenue", "execute": true}'
```

The response includes `sql`, `explanation`, `validation` (passed/issues/warnings), optional
`result` (columns/rows/row_count/truncated), `status`, and a `trace_id`.

## Testing & quality

```bash
cd apps/api
uv run pytest          # unit, integration, and adversarial safety tests
uv run ruff check .    # lint
uv run mypy app        # strict type-check
```

The suite includes an **adversarial regression** (DROP/DELETE/…, multi-statement, ATTACH,
CTE-wrapped writes, prompt injection, disallowed functions) with a target of **0 unsafe
statements accepted**, plus a rate-limit-aware live smoke harness at
`apps/api/scripts/smoke_live.py` for checking the real agent against the dataset.

## Deployment

See **`docs/DEPLOY.md`**. Options: full-stack on **Vercel** (SPA + Python serverless API —
scaffold in `vercel.json` / `api/index.py`), or a single **Docker** container on a persistent
host (Render/Fly/Railway) via the multi-stage `Dockerfile`. Note the serverless function-timeout
and read-only-filesystem constraints documented there.

## Project structure

```
apps/api/      FastAPI backend + LangGraph agent
  app/agents/    graph, nodes, prompts, model router, LLM client
  app/domain/    schema catalog, SQL validator, query policy
  app/infra/     read-only SQLite adapter, session store
  app/db/        schema builder + deterministic seed generator
  tests/         unit, integration, adversarial, data-integrity
apps/web/      React + TypeScript + Vite + Tailwind frontend
data/          schema.sql (sample e-commerce schema)
docs/          architecture, prompts, deployment
api/           Vercel serverless entrypoint
```

## Assumptions

- The 28-table e-commerce schema is **synthetic**, standing in for a schema that would
  otherwise be provided; it is never claimed to be an official one.
- "Read-only" means a single `SELECT` / `WITH` / `UNION` of selects; index suggestions are
  advisory text only (never executed).
- SQLite is the MVP dialect; PostgreSQL is a planned extension behind the adapter boundary.
- On serverless hosting, conversation history lives in `/tmp` and is per-instance/ephemeral.
- Safety is **tested**, not formally proven; see the adversarial suite and `docs/architecture.md`.

## Security

Defense in depth: user text is treated as data (never instructions); result rows never return
to the LLM; a deterministic AST gate and an independent read-only database layer (authorizer +
`query_only` + timeout + row cap) both sit after the model; CSV export neutralises spreadsheet
formula injection; secrets live only in environment variables. Details in `docs/architecture.md`.
