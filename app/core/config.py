from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LeadBot Studio"
    env: str = "dev"
    database_url: str = "sqlite:///./leadbot_studio.db"
    timezone: str = "Asia/Shanghai"
    leadbot_manifest_path: str = "app/data/leadbot_studio_manifest.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
