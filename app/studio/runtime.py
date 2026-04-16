from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WorkflowRunRecord
from app.studio.schemas import WorkflowRunRequest
from app.studio.service import StudioManifestService


class WorkflowRunNotFoundError(ValueError):
    """Raised when a requested workflow run cannot be found."""


class WorkflowRunService:
    def __init__(
        self,
        db: Session,
        manifest_service: StudioManifestService | None = None,
    ) -> None:
        self.db = db
        self.manifest_service = manifest_service or StudioManifestService()

    def create_run(
        self, workflow_id: str, request: WorkflowRunRequest | dict | None = None
    ) -> dict:
        preview = self.manifest_service.create_workflow_dry_run(workflow_id, request)
        record = WorkflowRunRecord(
            run_id=preview.run_id,
            workflow_id=preview.workflow_id,
            workflow_name=preview.workflow_name,
            lead_agent_id=preview.lead_agent_id,
            mode=preview.mode,
            operator=preview.operator,
            status="previewed",
            input_summary=preview.input_summary,
            requested_outputs_json=json.dumps(preview.requested_outputs, ensure_ascii=False),
            next_steps_json=json.dumps(preview.next_steps, ensure_ascii=False),
            blocked_steps_json=json.dumps(preview.blocked_steps, ensure_ascii=False),
            approval_steps_json=json.dumps(preview.approval_steps, ensure_ascii=False),
            step_previews_json=json.dumps(
                [step.model_dump(mode="json") for step in preview.step_previews],
                ensure_ascii=False,
            ),
            metadata_json=json.dumps(preview.metadata, ensure_ascii=False),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record.to_dict()

    def list_runs(self, workflow_id: str | None = None) -> list[dict]:
        statement = select(WorkflowRunRecord).order_by(WorkflowRunRecord.created_at.desc())
        if workflow_id:
            statement = statement.where(WorkflowRunRecord.workflow_id == workflow_id)
        return [record.to_dict() for record in self.db.scalars(statement).all()]

    def get_run(self, run_id: str) -> dict:
        statement = select(WorkflowRunRecord).where(WorkflowRunRecord.run_id == run_id)
        record = self.db.scalar(statement)
        if record is None:
            raise WorkflowRunNotFoundError(run_id)
        return record.to_dict()
