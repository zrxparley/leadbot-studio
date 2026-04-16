from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LeadBot Studio"
    env: str = "dev"
    database_url: str = "sqlite:///./market_insight.db"
    timezone: str = "Asia/Shanghai"
    enable_scheduler: bool = False
    dingtalk_webhook: str | None = None
    llm_api_key: str | None = None
    leadbot_manifest_path: str = "app/data/leadbot_studio_manifest.json"
    lead_archive_root: str = "artifacts/lead_runs"
    lead_search_max_results: int = 5
    lead_query_limit: int = 14
    lead_daily_min_records: int = 10
    lead_max_age_days: int = 365
    lead_search_timeout_seconds: int = 12
    lead_page_timeout_seconds: int = 8
    lead_browser_wait_milliseconds: int = 5000
    lead_target_countries: list[str] = Field(
        default_factory=lambda: [
            "Germany",
            "Vietnam",
            "Singapore",
            "Malaysia",
            "Philippines",
            "Indonesia",
            "Thailand",
            "United Arab Emirates",
            "Saudi Arabia",
            "Qatar",
            "Oman",
            "Bahrain",
            "Australia",
            "Canada",
            "South Africa",
            "Mongolia",
            "Kyrgyzstan",
            "Multiple destinations",
        ]
    )
    lead_target_keywords: list[str] = Field(
        default_factory=lambda: [
            "wire mesh",
            "filter mesh",
            "stainless steel mesh",
            "316L",
            "fence mesh",
            "chain link",
            "welded mesh",
            "hinged mesh",
            "barbed wire",
            "razor wire",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("lead_target_countries", "lead_target_keywords", mode="before")
    @classmethod
    def split_csv_lists(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
