from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Lead, MaterialPrice, NewsItem, Report
from app.services.reporter import ReportBuilder


class ReportGenerationSkill:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.builder = ReportBuilder()

    def generate_daily_briefing(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
        news_items: Sequence[NewsItem],
        top_leads: Sequence[Lead],
        material_prices: Sequence[MaterialPrice],
    ) -> Report:
        markdown = self.builder.build_daily_briefing(
            period_start=period_start,
            period_end=period_end,
            news_items=news_items,
            top_leads=top_leads,
            material_prices=material_prices,
        )
        report = Report(
            report_type="daily_briefing",
            period_start=period_start,
            period_end=period_end,
            content_markdown=markdown,
            content_html=markdown.replace("\n", "<br>"),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def generate_weekly_lead_summary(
        self, *, period_start: datetime, period_end: datetime, leads: Sequence[Lead]
    ) -> Report:
        markdown = self.builder.build_weekly_lead_summary(
            period_start=period_start,
            period_end=period_end,
            leads=leads,
        )
        report = Report(
            report_type="weekly_lead_summary",
            period_start=period_start,
            period_end=period_end,
            content_markdown=markdown,
            content_html=markdown.replace("\n", "<br>"),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

