from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> repo root is four levels up.
_REPO_ROOT = Path(__file__).resolve().parents[3]


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

    # LLM: single provider and key for now. Per-node routing is wired as config
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    @property
    def sample_db_path(self) -> Path:
        return self.data_dir / self.sample_db_filename


settings = Settings()
