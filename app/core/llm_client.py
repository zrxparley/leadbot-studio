from app.core.config import get_settings


class LLMClient:
    """Thin placeholder around the future production LLM integration."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def summarize(self, text: str, max_chars: int = 180) -> str:
        cleaned = " ".join(text.split())
        if not cleaned:
            return "No content available."
        if len(cleaned) <= max_chars:
            return cleaned
        return f"{cleaned[: max_chars - 3]}..."

    def classify_news(self, text: str) -> list[str]:
        lowered = text.lower()
        tags: list[str] = []
        if any(keyword in lowered for keyword in ["nickel", "steel", "zinc", "price"]):
            tags.append("raw-material")
        if any(keyword in lowered for keyword in ["policy", "anti-dumping", "tariff"]):
            tags.append("policy")
        if any(keyword in lowered for keyword in ["filtration", "mesh", "screen"]):
            tags.append("demand")
        return tags or ["industry"]

    def generate_report(self, prompt: str) -> str:
        return prompt

