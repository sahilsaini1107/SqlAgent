# Deployment

**Live:** <https://sql-agent-api-pza5.onrender.com>

The app runs as a single **Render** web service built from the repo's `Dockerfile`. The image
builds the React frontend, installs the API, generates the sample database, and serves the SPA
and the API from one origin, so no CORS or separate frontend host is needed.

## Render (primary)

The repo ships a Blueprint, `render.yaml`: a free Docker web service with a `/health` check that
redeploys on every push to `main`.

1. In Render: **New → Blueprint**, connect the GitHub repo, branch `main`, and select
   `render.yaml`.
2. Render prompts for the secrets marked `sync: false`:
   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | your Gemini API key |
   | `CORS_ORIGINS` | only needed if the frontend is hosted elsewhere (see below); otherwise any placeholder |

   Model tiers and `ENVIRONMENT=production` are preset in the Blueprint.
3. Apply. The first build takes several minutes (frontend, Python dependencies, sample DB).
   The service is live when the logs show `Uvicorn running on http://0.0.0.0:10000`.
4. Check `/health` returns `{"status":"ok", ...}`, then open the root URL.

To change a setting later: **service → Environment**, edit, then **Save, rebuild and deploy**.

### Free-tier behaviour
- The service **sleeps after ~15 minutes idle**. The next visit wakes it, which takes up to a
  minute before the page loads.
- The filesystem is **ephemeral**: server-side conversation context (`app.sqlite`) resets on
  restart or redeploy. The UI keeps its own chat history and starts a fresh server
  conversation when the old one is gone. The sample query DB is rebuilt into every image.
- A turn makes several Gemini calls (classify → generate → validate → maybe repair →
  explain); SQL generation on the core tier is the slowest step. `GEMINI_MODEL_CORE` can be
  pointed at a faster model from the Environment settings.

## Optional: frontend on Vercel

Hosting the frontend on Vercel makes the page load instantly from the CDN even while the
Render instance is asleep (the sidebar shows "Connecting…" until the API wakes). The browser
then calls Render directly.

1. In Vercel: **Add New → Project**, import the repo. **Root Directory: `apps/web`**; Framework
   Preset **Vite** (also pinned in `apps/web/vercel.json`).
2. Environment variable `VITE_API_BASE` = the Render URL, no trailing slash. It is read at
   **build** time, so redeploy after changing it.
3. On Render, set `CORS_ORIGINS` to the Vercel URL (comma-separate several). To allow Vercel
   preview deployments too, add `CORS_ORIGIN_REGEX`, e.g. `https://sql-agent-[a-z0-9-]+\.vercel\.app`.

## Post-deploy checklist
- [x] `/health` returns `{"status":"ok"}`.
- [x] The site loads and the sidebar shows **Connected**.
- [x] A data question returns validated SQL, results and an explanation.
- [x] An out-of-scope request is refused.
- [ ] Tested in a private window and on a mobile viewport, including a cold start.

## Troubleshooting
- **Build fails:** open the failed deploy under **Events** and read the end of the build log.
- **"No open ports detected" / health check timeout:** the app crashed on startup; look for a
  Python traceback in **Logs**.
- **First request hangs ~1 minute:** the free instance was asleep.
- **CORS error (Vercel setup only):** `CORS_ORIGINS` must exactly match the site's origin
  (scheme + host, no path or trailing slash).

## Running the image locally

```bash
docker build -t sql-agent .
docker run -p 8000:8000 -e GEMINI_API_KEY=... sql-agent
# open http://localhost:8000
```
