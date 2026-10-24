from pathlib import Path

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

    # Execution limits for the read-only sandbox.
    max_rows: int = 1000
    query_timeout_ms: int = 5000

    # Built frontend to serve at / (set in the container image; unset in local dev).
    web_dist_dir: Path | None = None

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

    @property
    def sample_db_path(self) -> Path:
        return self.data_dir / self.sample_db_filename

    @property
    def app_db_path(self) -> Path:
        return self.data_dir / self.app_db_filename


settings = Settings()
