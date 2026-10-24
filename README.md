# SQL Agent

A schema-grounded, **read-only** natural-language → SQL assistant. It turns plain-English
questions into validated SQL against a known database schema, explains the query, and can
run it safely. It specialises in SQL/database tasks and politely refuses anything else.

Built with **LangGraph** (agent orchestration), **FastAPI** (backend), **SQLGlot**
(deterministic SQL validation), **SQLite** (sample database), and **React + TypeScript**
(frontend).

> **Safety first:** the model proposes SQL; deterministic code and a read-only database
> layer decide. Destructive statements (`DELETE/UPDATE/INSERT/DROP/ALTER/TRUNCATE`) are
> never generated or executed.

## Status

Early development. See milestones in the engineering plan.

## Repository layout

```
apps/api/   FastAPI backend + LangGraph agent
apps/web/   React + TypeScript frontend
data/       sample schema and seed
evals/      golden evaluation set
```

## Development

### Backend

```bash
cd apps/api
uv sync
uv run python -m app.db.build   # generate data/sample.sqlite (deterministic, ~2 s)
uv run uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health
```

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

Run checks:

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```

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
