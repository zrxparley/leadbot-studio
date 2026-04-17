from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LeadBotProposalRecord
from app.studio.schemas import (
    LeadBotDraftApplyRequest,
    LeadBotDraftBundle,
    LeadBotProposalActionRequest,
    LeadBotProposalActionResult,
    LeadBotProposalCreateRequest,
    LeadBotProposalRecord as LeadBotProposalRecordSchema,
)
from app.studio.service import StudioManifestService


class LeadBotProposalNotFoundError(ValueError):
    """Raised when a proposal id cannot be found."""


class LeadBotProposalTransitionError(ValueError):
    """Raised when a proposal action is invalid for the current proposal state."""


class LeadBotProposalService:
    def __init__(
        self,
        db: Session,
        manifest_service: StudioManifestService | None = None,
    ) -> None:
        self.db = db
        self.manifest_service = manifest_service or StudioManifestService()

    def create_proposal(
        self,
        request: LeadBotProposalCreateRequest | dict[str, Any],
    ) -> LeadBotProposalRecordSchema:
        proposal_request = (
            request
            if isinstance(request, LeadBotProposalCreateRequest)
            else LeadBotProposalCreateRequest.model_validate(request)
        )
        draft = self.manifest_service.draft_studio_from_brief(proposal_request)
        record = LeadBotProposalRecord(
            proposal_id=f"proposal-{uuid4().hex[:10]}",
            title=proposal_request.title,
            brief=proposal_request.brief,
            operator=proposal_request.operator,
            status="pending",
            draft_json=json.dumps(draft.model_dump(mode="json"), ensure_ascii=False),
            reviewer_note=None,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._to_schema(record)

    def list_proposals(self) -> list[LeadBotProposalRecordSchema]:
        statement = select(LeadBotProposalRecord).order_by(LeadBotProposalRecord.created_at.desc())
        return [self._to_schema(item) for item in self.db.scalars(statement).all()]

    def get_proposal(self, proposal_id: str) -> LeadBotProposalRecordSchema:
        return self._to_schema(self._get_record(proposal_id))

    def act_on_proposal(
        self,
        proposal_id: str,
        request: LeadBotProposalActionRequest | dict[str, Any],
    ) -> LeadBotProposalActionResult:
        action_request = (
            request
            if isinstance(request, LeadBotProposalActionRequest)
            else LeadBotProposalActionRequest.model_validate(request)
        )
        record = self._get_record(proposal_id)
        if record.status in {"applied", "rejected"} and action_request.action != "revise":
            raise LeadBotProposalTransitionError(
                f"Proposal '{proposal_id}' is already '{record.status}'."
            )

        apply_result = None
        if action_request.action == "approve":
            draft = LeadBotDraftBundle.model_validate(json.loads(record.draft_json))
            apply_result = self.manifest_service.apply_draft_bundle(
                LeadBotDraftApplyRequest(
                    draft=draft,
                    replace_existing=action_request.replace_existing,
                    sync_removed_entities=action_request.sync_removed_entities,
                )
            )
            record.status = "applied"
        elif action_request.action == "reject":
            record.status = "rejected"
        else:
            record.status = "revision_requested"
        record.reviewer_note = action_request.note
        self.db.commit()
        self.db.refresh(record)
        return LeadBotProposalActionResult(
            proposal=self._to_schema(record),
            apply_result=apply_result,
        )

    def _get_record(self, proposal_id: str) -> LeadBotProposalRecord:
        statement = select(LeadBotProposalRecord).where(
            LeadBotProposalRecord.proposal_id == proposal_id
        )
        record = self.db.scalar(statement)
        if record is None:
            raise LeadBotProposalNotFoundError(proposal_id)
        return record

    @staticmethod
    def _to_schema(record: LeadBotProposalRecord) -> LeadBotProposalRecordSchema:
        payload = record.to_dict()
        return LeadBotProposalRecordSchema.model_validate(payload)
