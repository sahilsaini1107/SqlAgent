# syntax=docker/dockerfile:1

# --- build the frontend ---
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# --- api runtime ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS api
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    ENVIRONMENT=production \
    DATA_DIR=/app/data \
    WEB_DIST_DIR=/app/web-dist \
    PORT=8000
WORKDIR /app

# Install dependencies first for better layer caching.
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --no-dev --frozen

# Application code, sample data, and the built frontend.
COPY apps/api/ ./
COPY data/ /app/data/
COPY --from=web /web/dist /app/web-dist

# Generate the sample database at build time (reproducible from the schema and seed generator).
RUN /app/.venv/bin/python -m app.db.build

# Drop privileges.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# Hosts such as Render inject PORT; it defaults to 8000 elsewhere. Behind their proxy, trust
# forwarded headers so request URLs and client addresses are correct.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD /app/.venv/bin/python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/health').status == 200 else 1)"
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
