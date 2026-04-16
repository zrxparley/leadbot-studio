from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    type: Mapped[str] = mapped_column(String(50))
    base_url: Mapped[str] = mapped_column(String(300))
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class MaterialPrice(Base, TimestampMixin):
    __tablename__ = "material_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120))
    material_name: Mapped[str] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(120))
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10))
    unit: Mapped[str] = mapped_column(String(30))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_name": self.source_name,
            "material_name": self.material_name,
            "market": self.market,
            "price": self.price,
            "currency": self.currency,
            "unit": self.unit,
            "captured_at": self.captured_at.isoformat(),
        }


class NewsItem(Base, TimestampMixin):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500), unique=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    summary: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    tags: Mapped[str] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    language: Mapped[str] = mapped_column(String(12), default="en")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_name": self.source_name,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "summary": self.summary,
            "tags": self.tags.split(",") if self.tags else [],
            "country": self.country,
            "language": self.language,
        }


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str] = mapped_column(String(300))
    country: Mapped[str] = mapped_column(String(80))
    industry: Mapped[str] = mapped_column(String(120))
    product_interest: Mapped[str] = mapped_column(String(120))
    source_url: Mapped[str] = mapped_column(String(500), unique=True)
    contact_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    demand_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    demand_posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    buyer_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    demand_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    score_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="new")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "company_name": self.company_name,
            "website": self.website,
            "country": self.country,
            "industry": self.industry,
            "product_interest": self.product_interest,
            "source_url": self.source_url,
            "contact_hint": self.contact_hint,
            "demand_summary": self.demand_summary,
            "demand_posted_at": self.demand_posted_at.isoformat() if self.demand_posted_at else None,
            "buyer_contact_name": self.buyer_contact_name,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "demand_type": self.demand_type,
            "score": self.score,
            "score_reason": self.score_reason,
            "status": self.status,
            "discovered_at": self.discovered_at.isoformat(),
        }


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(80))
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    content_markdown: Mapped[str] = mapped_column(Text)
    content_html: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    delivery_status: Mapped[str] = mapped_column(String(40), default="pending")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "report_type": self.report_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "delivery_status": self.delivery_status,
        }


class TaskRun(Base, TimestampMixin):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WorkflowRunRecord(Base, TimestampMixin):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    workflow_id: Mapped[str] = mapped_column(String(120), index=True)
    workflow_name: Mapped[str] = mapped_column(String(255))
    lead_agent_id: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(40), default="dry_run")
    operator: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="previewed")
    input_summary: Mapped[str] = mapped_column(Text)
    requested_outputs_json: Mapped[str] = mapped_column(Text, default="[]")
    next_steps_json: Mapped[str] = mapped_column(Text, default="[]")
    blocked_steps_json: Mapped[str] = mapped_column(Text, default="[]")
    approval_steps_json: Mapped[str] = mapped_column(Text, default="[]")
    step_previews_json: Mapped[str] = mapped_column(Text, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "lead_agent_id": self.lead_agent_id,
            "mode": self.mode,
            "operator": self.operator,
            "status": self.status,
            "input_summary": self.input_summary,
            "requested_outputs": json.loads(self.requested_outputs_json),
            "next_steps": json.loads(self.next_steps_json),
            "blocked_steps": json.loads(self.blocked_steps_json),
            "approval_steps": json.loads(self.approval_steps_json),
            "step_previews": json.loads(self.step_previews_json),
            "metadata": json.loads(self.metadata_json),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
