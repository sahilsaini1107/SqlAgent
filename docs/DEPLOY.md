# Deployment

The frontend and backend deploy separately:

- **Frontend** (React + Vite, `apps/web`) → **Vercel**, as static files on the CDN.
- **Backend** (FastAPI + LangGraph, `apps/api`) → **Render**, as a Docker web service built from
  the repo's `Dockerfile`.

The browser calls the backend directly: the frontend build bakes in the backend URL
(`VITE_API_BASE`) and the backend allows the frontend's origin via CORS (`CORS_ORIGINS`).

Deploy the backend first, because the frontend build needs its URL.

## 1. Backend on Render

The repo ships a Blueprint, `render.yaml`, describing a free Docker web service with a `/health`
check that redeploys on every push to `main`.

1. In Render: **New → Blueprint**, connect the GitHub repo, and select `render.yaml`.
2. Render prompts for the secrets marked `sync: false`:
   | Name | Value |
   |---|---|
   | `GEMINI_API_KEY` | your Gemini API key |
   | `CORS_ORIGINS` | the Vercel production URL, e.g. `https://sql-agent.vercel.app` (no trailing slash; comma-separate several) |

   If you don't know the Vercel URL yet, enter a placeholder and update it after step 2.
   Model tiers and `ENVIRONMENT=production` are preset in the Blueprint.
3. Apply. The first build takes a few minutes (frontend stage, Python dependencies, sample DB).
4. Check `https://<service>.onrender.com/health` returns `{"status":"ok", ...}`.

Optional: to let Vercel **preview** deployments call the API too, add
`CORS_ORIGIN_REGEX`, e.g. `https://sql-agent-[a-z0-9-]+\.vercel\.app`, in the service's
Environment settings.

### Free-tier behaviour
- The service **sleeps after ~15 minutes idle**; the next request wakes it, which takes up to a
  minute. The UI shows "Connecting…" / "API offline" in the sidebar until `/health` answers.
- The filesystem is **ephemeral**: server-side conversation context (`app.sqlite`) resets on
  restart or redeploy. The UI keeps its own chat history and starts a fresh server
  conversation when the old one is gone. The sample query DB is rebuilt into every image.

## 2. Frontend on Vercel

`apps/web/vercel.json` pins the Vite build (`npm ci`, `npm run build`, output `dist`).

1. In Vercel: **Add New → Project**, import the GitHub repo (or edit the existing project).
2. **Root Directory: `apps/web`**. Framework Preset: **Vite** (also pinned in `vercel.json`).
3. **Environment variable** (Production and Preview):
   | Name | Value |
   |---|---|
   | `VITE_API_BASE` | the Render URL, e.g. `https://sql-agent-api.onrender.com` (no trailing slash) |

   It is read at **build** time, so redeploy after changing it.
4. Deploy, then put the resulting URL in Render's `CORS_ORIGINS` if you used a placeholder.

## Post-deploy checklist
- [ ] `https://<render-service>/health` returns `{"status":"ok"}`.
- [ ] The Vercel site loads and the sidebar shows **Connected**.
- [ ] A data question returns validated SQL, results and an explanation (streaming stages show).
- [ ] An out-of-scope and a destructive request are refused.
- [ ] No CORS errors in the browser console; tested in a private window and on mobile.

## Troubleshooting
- **CORS error in the console:** `CORS_ORIGINS` on Render must exactly match the site's origin
  (scheme + host, no path or trailing slash). Redeploy/restart the Render service after editing.
- **Requests go to the Vercel domain and 404:** `VITE_API_BASE` was missing at build time; set
  it in Vercel and redeploy.
- **First request hangs ~1 minute:** the free Render instance was asleep.

## Alternative: one container

The same `Dockerfile` serves the API and the built SPA from one origin (no CORS needed) on any
container host:

```bash
docker build -t sql-agent .
docker run -p 8000:8000 -e GEMINI_API_KEY=... sql-agent
# open http://localhost:8000
```
