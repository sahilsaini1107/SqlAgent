from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.config import settings
from app.observability.logging import configure_logging
from app.observability.middleware import RequestTraceMiddleware


def create_app() -> FastAPI:
    configure_logging(settings.log_level, json_logs=settings.environment == "production")
    app = FastAPI(title="SQL Agent API", version="0.1.0")
    app.add_middleware(RequestTraceMiddleware)
    app.include_router(health_router)
    return app


app = create_app()
