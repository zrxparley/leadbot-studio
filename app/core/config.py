from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = Path(os.getenv("LEADBOT_ENV_FILE", PROJECT_ROOT / ".env")).expanduser()


class Settings(BaseSettings):
    app_name: str = "LeadBot Studio"
    env: str = "dev"
    database_url: str = "sqlite:///./leadbot_studio.db"
    timezone: str = "Asia/Shanghai"
    leadbot_manifest_path: str = "app/data/leadbot_studio_manifest.json"
    leadbot_draft_provider: str = "auto"
    leadbot_draft_model: str = "gpt-5.4"
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
