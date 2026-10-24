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

    # Built frontend to serve at / (set in the container image; unset in local dev).
    web_dist_dir: Path | None = None

    # LLM: single provider and key for now. Per-node routing is wired as config
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    @property
    def sample_db_path(self) -> Path:
        return self.data_dir / self.sample_db_filename


settings = Settings()
