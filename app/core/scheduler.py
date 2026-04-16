from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.jobs.daily_briefing import DailyBriefingJob
from app.jobs.weekly_lead_summary import WeeklyLeadSummaryJob


class SchedulerService:
    def __init__(self) -> None:
        settings = get_settings()
        self.scheduler = BackgroundScheduler(timezone=settings.timezone)
        self._configured = False

    def start(self) -> None:
        if not self._configured:
            self._configure_jobs()
            self._configured = True
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def _configure_jobs(self) -> None:
        self.scheduler.add_job(
            self._run_daily_briefing,
            CronTrigger(hour=8, minute=0),
            id="daily-briefing",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_weekly_summary,
            CronTrigger(day_of_week="fri", hour=17, minute=0),
            id="weekly-lead-summary",
            replace_existing=True,
        )

    @staticmethod
    def _run_daily_briefing() -> None:
        with SessionLocal() as db:
            DailyBriefingJob(db).run()

    @staticmethod
    def _run_weekly_summary() -> None:
        with SessionLocal() as db:
            WeeklyLeadSummaryJob(db).run()


scheduler_service = SchedulerService()

