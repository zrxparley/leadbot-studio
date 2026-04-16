from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import Report, TaskRun
from app.services.notifier import NotifierFactory
from app.skills.lead_generation import LeadGenerationSkill
from app.skills.report_generation import ReportGenerationSkill


class WeeklyLeadSummaryJob:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.lead_skill = LeadGenerationSkill(db)
        self.report_skill = ReportGenerationSkill(db)
        self.notifier = NotifierFactory().create()
        self.last_lead_archive_path: str | None = None

    def run(self, triggered_at: datetime | None = None) -> Report:
        started_at = triggered_at or datetime.now()
        task_run = TaskRun(job_name="weekly_lead_summary", started_at=started_at)
        self.db.add(task_run)
        self.db.commit()

        try:
            leads = self.lead_skill.run(as_of=started_at, run_name="weekly_lead_summary")
            self.last_lead_archive_path = self.lead_skill.last_archive_path
            report = self.report_skill.generate_weekly_lead_summary(
                period_start=started_at - timedelta(days=7),
                period_end=started_at,
                leads=leads,
            )
            self.notifier.send(
                title="本周潜在线索汇总",
                markdown=report.content_markdown,
            )
            report.delivery_status = "sent"
            task_run.status = "completed"
            task_run.items_processed = len(leads)
            task_run.finished_at = datetime.now()
            self.db.commit()
            return report
        except Exception as exc:  # pragma: no cover - defensive logging path
            task_run.status = "failed"
            task_run.error_message = str(exc)
            task_run.finished_at = datetime.now()
            self.db.commit()
            raise
