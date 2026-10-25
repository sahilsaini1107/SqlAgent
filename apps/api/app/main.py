from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_schema import router as schema_router
from app.config import settings
from app.observability.logging import configure_logging, get_logger, trace_id_var
from app.observability.middleware import RequestTraceMiddleware

logger = get_logger("app")


def create_app() -> FastAPI:
    configure_logging(settings.log_level, json_logs=settings.environment == "production")
    app = FastAPI(title="SQL Agent API", version=__version__)
    app.add_middleware(RequestTraceMiddleware)
    _allow_frontend_origins(app)
    _install_error_handler(app)
    app.include_router(health_router)
    app.include_router(schema_router)
    app.include_router(chat_router)
    _mount_frontend(app)
    return app


def _install_error_handler(app: FastAPI) -> None:
    """Return a sanitized 500 with the trace id for any unhandled error, so internal details
    (tracebacks, schema, provider messages) never reach the client."""

    @app.exception_handler(Exception)
    async def _on_error(request: Request, exc: Exception) -> JSONResponse:
        trace_id = trace_id_var.get()
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "trace_id": trace_id},
        )


def _allow_frontend_origins(app: FastAPI) -> None:
    """Let a separately hosted frontend (e.g. on Vercel) call the API from the browser."""
    origins = settings.cors_origin_list
    if not origins and not settings.cors_origin_regex:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA at / when a dist directory is configured (production image)."""
    dist = settings.web_dist_dir
    if dist is not None and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")


app = create_app()
