from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes_health import router as health_router
from app.config import settings
from app.observability.logging import configure_logging
from app.observability.middleware import RequestTraceMiddleware


def create_app() -> FastAPI:
    configure_logging(settings.log_level, json_logs=settings.environment == "production")
    app = FastAPI(title="SQL Agent API", version="0.1.0")
    app.add_middleware(RequestTraceMiddleware)
    app.include_router(health_router)
    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA at / when a dist directory is configured (production image)."""
    dist = settings.web_dist_dir
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")


app = create_app()
