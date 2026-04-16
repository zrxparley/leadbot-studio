from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.competitor_registry import load_competitor_targets
from app.core.config import get_settings
from app.db.models import Lead, NewsItem, Report
from app.db.session import get_db
from app.jobs.daily_briefing import DailyBriefingJob
from app.jobs.weekly_lead_summary import WeeklyLeadSummaryJob
from app.skills.lead_generation import LeadGenerationSkill
from app.skills.market_monitoring import MarketMonitoringSkill

router = APIRouter()
settings = get_settings()


def _lead_status_priority(status: str) -> int:
    priorities = {
        "buyer_candidate": 4,
        "channel_candidate": 3,
        "buyer_review": 2,
        "unknown": 1,
        "supplier_noise": 0,
    }
    return priorities.get(status, 0)


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/jobs/daily-briefing/run")
def run_daily_briefing(db: Session = Depends(get_db)) -> dict[str, str]:
    job = DailyBriefingJob(db)
    report = job.run(triggered_at=datetime.now())
    return {
        "status": "completed",
        "report_id": str(report.id),
        "lead_archive_path": job.last_lead_archive_path or "",
    }


@router.post("/jobs/weekly-lead-summary/run")
def run_weekly_lead_summary(db: Session = Depends(get_db)) -> dict[str, str]:
    job = WeeklyLeadSummaryJob(db)
    report = job.run(triggered_at=datetime.now())
    return {
        "status": "completed",
        "report_id": str(report.id),
        "lead_archive_path": job.last_lead_archive_path or "",
    }


@router.post("/skills/market-monitoring/run")
def run_market_monitoring(db: Session = Depends(get_db)) -> dict[str, int | str]:
    result = MarketMonitoringSkill(db).run(
        as_of=datetime.now(),
        lead_run_name="api_market_monitoring",
    )
    return {
        "news_items": len(result["news_items"]),
        "material_prices": len(result["material_prices"]),
        "top_leads": len(result["top_leads"]),
        "lead_archive_path": result.get("lead_archive_path") or "",
    }


@router.post("/skills/lead-generation/run")
def run_lead_generation(db: Session = Depends(get_db)) -> dict[str, int | str]:
    skill = LeadGenerationSkill(db)
    leads = skill.run(as_of=datetime.now(), run_name="api_lead_generation")
    return {
        "leads": len(leads),
        "duplicates_skipped": skill.last_run_stats.get("duplicates_skipped", 0),
        "lead_archive_path": skill.last_archive_path or "",
    }


@router.get("/leads")
def list_leads(
    exclude_noise: bool = Query(default=True),
    fresh_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> list[dict]:
    leads = db.scalars(select(Lead)).all()
    if exclude_noise:
        leads = [lead for lead in leads if lead.status != "supplier_noise"]
    if fresh_only:
        cutoff = datetime.now() - timedelta(days=settings.lead_max_age_days)
        leads = [
            lead
            for lead in leads
            if lead.demand_posted_at and lead.demand_posted_at >= cutoff
        ]
    leads = sorted(
        leads,
        key=lambda lead: (
            _lead_status_priority(lead.status),
            lead.score,
            lead.demand_posted_at or lead.discovered_at,
        ),
        reverse=True,
    )
    return [lead.to_dict() for lead in leads]


@router.get("/news")
def list_news(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(select(NewsItem).order_by(NewsItem.published_at.desc())).all()
    return [item.to_dict() for item in items]


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)) -> list[dict]:
    reports = db.scalars(select(Report).order_by(Report.generated_at.desc())).all()
    return [report.to_dict() for report in reports]


@router.get("/competitors/targets")
def list_competitor_targets() -> list[dict[str, str]]:
    return [
        {
            "name": target.name,
            "website": target.website,
            "focus": target.focus,
            "country": target.country,
            "notes": target.notes or "",
        }
        for target in load_competitor_targets()
    ]
