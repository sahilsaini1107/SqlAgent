from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import __version__
from app.dependencies import get_runtime
from app.runtime import Runtime

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe used by the load balancer and the keep-warm ping."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=ReadyResponse)
def ready(runtime: Runtime = Depends(get_runtime)) -> ReadyResponse:
    """Readiness probe: confirms the sample database is queryable and the conversation store is
    writable, so the balancer only routes traffic once the app can actually serve a request."""
    checks: dict[str, str] = {}
    try:
        runtime.catalog.table_names()
        checks["sample_db"] = "ok"
    except Exception as err:  # noqa: BLE001 — surface the reason in the probe body
        checks["sample_db"] = f"error: {err}"
    try:
        conversation_id = runtime.session_store.create_conversation()
        runtime.session_store.delete_conversation(conversation_id)
        checks["app_db"] = "ok"
    except Exception as err:  # noqa: BLE001
        checks["app_db"] = f"error: {err}"

    if any(v != "ok" for v in checks.values()):
        raise HTTPException(
            status_code=503, detail={"status": "unavailable", "checks": checks}
        )
    return ReadyResponse(status="ok", version=__version__, checks=checks)
