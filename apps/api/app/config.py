import re
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> repo root is four levels up in the dev layout. Guard the
# lookup so a flattened container layout still imports; DATA_DIR / WEB_DIST_DIR are set
# explicitly in the container anyway.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3] if len(_HERE.parents) >= 4 else _HERE.parent


class Settings(BaseSettings):
    """Application configuration, loaded from the environment"""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "info"

    # Sample query database, generated from data/schema.sql + data/seed.sql.
    data_dir: Path = _REPO_ROOT / "data"
    sample_db_filename: str = "sample.sqlite"

    # Application database for conversations/messages (separate from the sample query DB).
    app_db_filename: str = "app.sqlite"
    # LangGraph checkpointer database: per-run graph state for durability/resumability. Lives
    # next to the app DB (so APP_DB_DIR covers it on a read-only serverless filesystem).
    checkpoint_db_filename: str = "checkpoints.sqlite"
    # Writable directory for the app DB. On a read-only serverless filesystem (e.g. Vercel),
    # set APP_DB_DIR=/tmp — conversation history is then per-instance and ephemeral.
    app_db_dir: Path | None = None

    # Execution limits for the read-only sandbox.
    max_rows: int = 1000
    query_timeout_ms: int = 5000

    # Built frontend to serve at / (set in the container image; unset in local dev).
    web_dist_dir: Path | None = None

    # Browser origins allowed to call the API cross-origin (frontend hosted separately, e.g. on
    # Vercel). Comma-separated exact origins, plus an optional regex for preview deployments.
    cors_origins: str = ""
    cors_origin_regex: str | None = None

    # LLM: single provider/key, three tiers. The model_router maps each graph node to one
    # of these tiers (see agents/factory.py). Free-tier design: high-volume routing/prose on
    # Flash-Lite, core SQL work on Flash, Pro reserved for opt-in complex synthesis.
    gemini_api_key: str | None = None
    # Default / high-volume tier: intent classification, descriptive prose.
    gemini_model: str = "gemini-3.5-flash-lite"
    # Core execution tier: SQL generation, repair, optimization.
    gemini_model_core: str = "gemini-3.8-flash"
    # Complex synthesis tier: reserved, opt-in (tight free-tier caps). Route a node here via
    # GEMINI_MODEL_PRO + an override in default_router() when needed.
    gemini_model_pro: str = "gemini-3.8-flash"

    # LLM call resilience. A per-call wall-clock timeout and bounded retries keep a single
    # transient provider error (429/503/network) from failing — or hanging — a request, and the
    # output-token ceiling caps cost/latency on any one call.
    llm_timeout_s: float = 30.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 2048

    @model_validator(mode="after")
    def _check(self) -> "Settings":
        # Fail fast in production rather than surfacing a missing key deep in a request.
        if self.environment == "production" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when ENVIRONMENT=production")
        # An unanchored preview regex (e.g. '.*vercel.app') would authorize look-alike origins
        # like 'evil-vercel.app.attacker.com'; require it to be anchored end-to-end.
        regex = self.cors_origin_regex
        if regex and not (regex.startswith("^") and regex.endswith("$")):
            raise ValueError("CORS_ORIGIN_REGEX must be anchored with ^ and $")
        if regex:
            re.compile(regex)  # surface a bad pattern at startup, not on first request
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sample_db_path(self) -> Path:
        return self.data_dir / self.sample_db_filename

    @property
    def app_db_path(self) -> Path:
        base = self.app_db_dir if self.app_db_dir is not None else self.data_dir
        return base / self.app_db_filename

    @property
    def checkpoint_db_path(self) -> Path:
        base = self.app_db_dir if self.app_db_dir is not None else self.data_dir
        return base / self.checkpoint_db_filename


settings = Settings()
