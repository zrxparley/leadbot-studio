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

    # Model Integration
    leadbot_draft_provider: str = "auto"  # auto / openai / azure / openai-compatible / none
    leadbot_draft_model: str = "gpt-4o"

    # OpenAI
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # Azure OpenAI (alternative)
    azure_openai_endpoint: str | None = None
    azure_openai_key: str | None = None
    azure_openai_version: str = "2024-05-01-preview"

    model_config = SettingsConfigDict(
        env_file=DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
