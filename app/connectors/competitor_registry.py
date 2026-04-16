import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CompetitorTarget:
    name: str
    website: str
    focus: str
    country: str
    notes: str | None = None
    enabled: bool = True


def _registry_path(filename: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / filename


def load_competitor_targets() -> list[CompetitorTarget]:
    path = _registry_path("competitor_targets.json")
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding="utf-8"))
    targets: list[CompetitorTarget] = []
    for item in payload:
        targets.append(
            CompetitorTarget(
                name=item["name"],
                website=item["website"],
                focus=item["focus"],
                country=item["country"],
                notes=item.get("notes"),
                enabled=item.get("enabled", True),
            )
        )
    return [target for target in targets if target.enabled]
