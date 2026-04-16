from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import Report, TaskRun
from app.services.notifier import NotifierFactory
from app.skills.market_monitoring import MarketMonitoringSkill
from app.skills.report_generation import ReportGenerationSkill


class DailyBriefingJob:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.monitoring_skill = MarketMonitoringSkill(db)
        self.report_skill = ReportGenerationSkill(db)
        self.notifier = NotifierFactory().create()
        self.last_lead_archive_path: str | None = None

    def run(self, triggered_at: datetime | None = None) -> Report:
        started_at = triggered_at or datetime.now()
        task_run = TaskRun(job_name="daily_briefing", started_at=started_at)
        self.db.add(task_run)
        self.db.commit()

        try:
            monitoring_result = self.monitoring_skill.run(
                as_of=started_at,
                lead_run_name="daily_briefing",
            )
            self.last_lead_archive_path = monitoring_result.get("lead_archive_path")
            report = self.report_skill.generate_daily_briefing(
                period_start=started_at - timedelta(days=1),
                period_end=started_at,
                news_items=monitoring_result["news_items"],
                top_leads=monitoring_result["top_leads"],
                material_prices=monitoring_result["material_prices"],
            )
            self.notifier.send(
                title="全球丝网市场动态日报",
                markdown=report.content_markdown,
            )
            report.delivery_status = "sent"
            task_run.status = "completed"
            task_run.items_processed = len(monitoring_result["news_items"]) + len(
                monitoring_result["top_leads"]
            )
            task_run.finished_at = datetime.now()
            self.db.commit()
            return report
        except Exception as exc:  # pragma: no cover - defensive logging path
            task_run.status = "failed"
            task_run.error_message = str(exc)
            task_run.finished_at = datetime.now()
            self.db.commit()
            raise
