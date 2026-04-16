from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.mock_sources import MockNewsConnector
from app.connectors.rss_news import RSSNewsConnector
from app.connectors.source_registry import load_news_sources
from app.core.llm_client import LLMClient
from app.db.models import Lead, MaterialPrice, NewsItem
from app.services.classifier import NewsClassifier
from app.services.extractor import build_content_hash
from app.skills.lead_generation import LeadGenerationSkill


class MarketMonitoringSkill:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.fallback_news_connector = MockNewsConnector()
        self.rss_connector = RSSNewsConnector()
        self.news_classifier = NewsClassifier()
        self.llm = LLMClient()
        self.lead_skill = LeadGenerationSkill(db)
        self.last_lead_archive_path: str | None = None

    def run(self, as_of: datetime, *, lead_run_name: str = "market_monitoring") -> dict[str, list]:
        news_items = self._collect_news()
        material_prices = self._collect_mock_material_prices(as_of=as_of)
        top_leads = self._collect_top_leads(as_of=as_of, lead_run_name=lead_run_name)
        return {
            "news_items": news_items,
            "material_prices": material_prices,
            "top_leads": top_leads,
            "lead_archive_path": self.last_lead_archive_path,
        }

    def _collect_news(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        raw_records = self._fetch_news_records()
        for raw_item in raw_records:
            content_hash = build_content_hash(raw_item.title, raw_item.body, raw_item.url)
            existing = self.db.scalar(select(NewsItem).where(NewsItem.content_hash == content_hash))
            if existing:
                items.append(existing)
                continue
            tags = self.news_classifier.classify(raw_item.title, raw_item.body)
            item = NewsItem(
                source_name=raw_item.source_name,
                title=raw_item.title,
                url=raw_item.url,
                published_at=raw_item.published_at,
                summary=self.llm.summarize(raw_item.body),
                content_hash=content_hash,
                tags=",".join(tags),
                country=raw_item.country or "Global",
                language=raw_item.language,
            )
            self.db.add(item)
            self.db.flush()
            items.append(item)
        self.db.commit()
        return items

    def _fetch_news_records(self):
        collected = []
        for source in load_news_sources():
            if source.type != "rss":
                continue
            try:
                collected.extend(self.rss_connector.fetch(source))
            except Exception:
                continue
        if collected:
            return collected
        return self.fallback_news_connector.fetch()

    def _collect_mock_material_prices(self, as_of: datetime) -> list[MaterialPrice]:
        prices = [
            MaterialPrice(
                source_name="mock-lme-feed",
                material_name="Nickel",
                market="LME",
                price=18120.0,
                currency="USD",
                unit="ton",
                captured_at=as_of,
            ),
            MaterialPrice(
                source_name="mock-steel-feed",
                material_name="Stainless Steel",
                market="Asia Export",
                price=2450.0,
                currency="USD",
                unit="ton",
                captured_at=as_of,
            ),
        ]
        for price in prices:
            self.db.add(price)
        self.db.commit()
        return prices

    def _collect_top_leads(self, as_of: datetime, lead_run_name: str) -> list[Lead]:
        leads = self.lead_skill.run(as_of=as_of, run_name=lead_run_name)
        self.last_lead_archive_path = self.lead_skill.last_archive_path
        preferred_statuses = {"buyer_candidate", "channel_candidate", "buyer_review"}
        filtered = [lead for lead in leads if lead.status in preferred_statuses]
        if filtered:
            return sorted(filtered, key=lambda lead: lead.score, reverse=True)[:5]
        return sorted(leads, key=lambda lead: lead.score, reverse=True)[:5]
