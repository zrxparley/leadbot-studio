from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
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
        import json

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
