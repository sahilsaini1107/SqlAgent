# Deployment

The app can be deployed full-stack on **Vercel** (frontend + Python serverless API), or as a
single **Docker** container on a persistent host (Render/Fly/Railway). Vercel is the primary
target; read the constraints below first.

## Option A — Vercel (FastAPI preset, one function)

Files in the repo: `index.py` (entrypoint), `vercel.json`, `requirements.txt` (exported from
the uv lockfile), `.python-version` (3.12), `.vercelignore`.

### How it fits together
- Vercel's **FastAPI** framework preset finds the `app` in the root `index.py` and routes
  every request to it. `index.py` adds `apps/api` to the path, points the conversation DB at
  `/tmp`, and points `WEB_DIST_DIR` at the built frontend, so the API and the SPA share one
  origin (no rewrites).
- `vercel.json`'s build command runs after `requirements.txt` is installed and before the
  function is bundled: it generates `data/sample.sqlite` (`app.db.build`) and builds the Vite
  frontend. `includeFiles` bundles the sample DB, the backend package, and `apps/web/dist`.

### Steps
1. Commit and push to GitHub, then import the repo in Vercel (or redeploy an existing project).
2. **Project settings:** Framework Preset = **FastAPI**, Root Directory = repo root. Leave the
   build and output settings to `vercel.json`.
3. **Environment variables** (Production and Preview):
   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | your key |
   | `GEMINI_MODEL` | e.g. `gemini-3.5-flash-lite` |
   | `GEMINI_MODEL_CORE` | e.g. `gemini-3.8-flash` |
   | `GEMINI_MODEL_PRO` | e.g. `gemini-3.8-flash` |
   | `ENVIRONMENT` | `production` |
4. Deploy, then check `/health`, the root page, and a chat request.

### Constraints to know
- **Function duration.** A turn makes several Gemini calls (classify → generate → validate →
  maybe repair → explain). Fluid compute's default limit is generous, but a slow model call
  can still hit it; add `"maxDuration"` under `functions."index.py"` in `vercel.json` to tune.
- **Read-only filesystem.** Only `/tmp` is writable, so conversation history is **per-instance
  and ephemeral**. The UI keeps its own history and starts a fresh server conversation when
  the old one is gone; the sample query DB is read-only and bundled, so queries are unaffected.
- **Cold starts.** LangGraph + LangChain + google-genai + SQLGlot is sizeable, so the first
  request after idle is slower.

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
