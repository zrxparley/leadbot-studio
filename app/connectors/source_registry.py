import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class NewsSourceConfig:
    name: str
    type: str
    url: str
    country: str | None = None
    language: str = "en"
    enabled: bool = True


def _registry_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / filename


def load_news_sources() -> list[NewsSourceConfig]:
    path = _registry_path("news_sources.json")
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    sources: list[NewsSourceConfig] = []
    for item in payload:
        sources.append(
            NewsSourceConfig(
                name=item["name"],
                type=item["type"],
                url=item["url"],
                country=item.get("country"),
                language=item.get("language", "en"),
                enabled=item.get("enabled", True),
            )
        )
    return [source for source in sources if source.enabled]

