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
uv run uvicorn app.main:app --reload
# -> http://127.0.0.1:8000/health
```

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
| `GEMINI_MODEL` | Model id (default `gemini-2.5-flash`) |
| `ENVIRONMENT` | `development` / `production` |
| `LOG_LEVEL` | Log level |
