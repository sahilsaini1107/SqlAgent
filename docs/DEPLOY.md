# Deployment

The app can be deployed full-stack on **Vercel** (frontend + Python serverless API), or as a
single **Docker** container on a persistent host (Render/Fly/Railway). Vercel is the primary
target; read the constraints below first.

## Option A — Vercel (frontend + serverless API)

Files already in the repo: `vercel.json`, `api/index.py` (ASGI entry), `requirements.txt`
(exported from the uv lockfile), `.vercelignore`.

### How it fits together
- `vercel.json` builds the sample database (`app.db.build`) and the Vite frontend, serves the
  SPA from `apps/web/dist`, and rewrites `/api/*` and `/health` to the Python function.
- `api/index.py` adds `apps/api` to the path, points the conversation DB at `/tmp`, and exposes
  the FastAPI ASGI `app`. The sample DB is bundled read-only via `includeFiles`.

### Steps
1. Push the repo to GitHub and "Import Project" in Vercel.
2. **Project settings:** Root Directory = repo root; leave Build/Output to `vercel.json`.
   Set the Python runtime to **3.12** (the code uses 3.12 features).
3. **Environment variables:**
   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | your key |
   | `GEMINI_MODEL` | e.g. `gemini-3.5-flash-lite` |
   | `GEMINI_MODEL_CORE` | e.g. `gemini-3.8-flash` |
   | `GEMINI_MODEL_PRO` | e.g. `gemini-3.8-flash` |
   | `ENVIRONMENT` | `production` |
   | `APP_DB_DIR` | `/tmp` (also defaulted in `api/index.py`) |
4. Deploy, then smoke-test `/(health)` and a `/api/chat` request.

### Constraints to know (important)
- **Function timeout.** The agent makes several Gemini calls per turn (classify → generate →
  validate → maybe repair → explain). On the **Hobby plan the limit is 10s**, which this can
  exceed — use **Pro (60s)** or expect occasional timeouts. Keep execution enabled but lean on
  the cheaper model tiers.
- **Read-only filesystem.** Only `/tmp` is writable, so conversation history lives in `/tmp`:
  it is **per-instance and ephemeral** (lost on cold start / across instances). The sample query
  DB is read-only and bundled, so queries are unaffected.
- **Streaming.** Python serverless responses may be buffered, so SSE can arrive in one chunk —
  the UI still renders the final result correctly, it just may not show live stage updates.
- **Bundle size / cold starts.** LangGraph + LangChain + google-genai + SQLGlot is sizeable;
  first-request cold starts are slower.

## Option B — Docker on a container host (more robust)

A persistent host avoids every serverless constraint above (no timeout cap, writable disk,
true streaming). The repo ships a multi-stage `Dockerfile` (non-root, builds the sample DB,
serves the SPA + API on one origin).

```bash
docker build -t sql-agent .
docker run -p 8000:8000 -e GEMINI_API_KEY=... -e ENVIRONMENT=production sql-agent
# open http://localhost:8000
```

On Render/Fly/Railway: point the service at the Dockerfile, set `GEMINI_API_KEY` (+ model env
vars), expose port 8000, and use `/health` as the health check.

## Option C — Hybrid (Vercel frontend + container backend)

If the serverless API proves too constrained, keep the **frontend on Vercel** and run the
**backend as a container** (Option B). This needs two small changes:
- Frontend: call the backend via an env base URL (`VITE_API_BASE`) instead of same-origin `/api`.
- Backend: enable CORS for the Vercel origin.

Both are localized changes; open an issue/PR if you go this route and they can be added quickly.

## Post-deploy checklist
- [ ] `/health` returns `{"status":"ok"}` from the public URL.
- [ ] A natural-language query returns validated SQL + explanation.
- [ ] A destructive request and an out-of-scope request are refused.
- [ ] Tested in a private/incognito window and on a mobile viewport, including a cold start.
- [ ] README updated with the live link.
