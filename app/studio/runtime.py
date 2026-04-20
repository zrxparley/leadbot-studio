from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import WorkflowRunEventRecord, WorkflowRunRecord
from app.studio.schemas import (
    RunStatus,
    StepStatus,
    WorkflowRunRequest,
    WorkflowRunStepUpdateRequest,
    WorkflowRunUpdateRequest,
)
from app.studio.service import StudioManifestService


class WorkflowRunNotFoundError(ValueError):
    """Raised when a requested workflow run cannot be found."""


class WorkflowRunTransitionError(ValueError):
    """Raised when a workflow run transition is invalid."""


class OpenClawDispatchError(RuntimeError):
    """Raised when dispatching to OpenClaw fails."""


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
        self.db.flush()
        self._append_event(
            run_id=record.run_id,
            workflow_id=record.workflow_id,
            event_type="run_created",
            actor=record.operator,
            target_kind="run",
            target_id=record.run_id,
            from_status=None,
            to_status=record.status,
            note=record.input_summary,
            metadata={"mode": record.mode},
        )
        self.db.commit()
        self.db.refresh(record)
        return record.to_dict()

    def list_runs(self, workflow_id: str | None = None) -> list[dict]:
        statement = select(WorkflowRunRecord).order_by(WorkflowRunRecord.created_at.desc())
        if workflow_id:
            statement = statement.where(WorkflowRunRecord.workflow_id == workflow_id)
        return [record.to_dict() for record in self.db.scalars(statement).all()]

    def get_run(self, run_id: str) -> dict:
        record = self._get_record(run_id)
        return record.to_dict()

    def list_run_events(self, run_id: str) -> list[dict]:
        self._get_record(run_id)
        statement = (
            select(WorkflowRunEventRecord)
            .where(WorkflowRunEventRecord.run_id == run_id)
            .order_by(WorkflowRunEventRecord.created_at.asc(), WorkflowRunEventRecord.id.asc())
        )
        return [event.to_dict() for event in self.db.scalars(statement).all()]

    def update_run(
        self, run_id: str, request: WorkflowRunUpdateRequest | dict[str, Any]
    ) -> dict:
        record = self._get_record(run_id)
        update = (
            request
            if isinstance(request, WorkflowRunUpdateRequest)
            else WorkflowRunUpdateRequest.model_validate(request)
        )

        from_status = record.status
        self._validate_run_transition(from_status, update.status)
        record.status = update.status
        metadata = json.loads(record.metadata_json)
        if update.note:
            metadata["last_run_note"] = update.note
        if update.operator:
            record.operator = update.operator
        record.metadata_json = json.dumps(metadata, ensure_ascii=False)
        self._append_event(
            run_id=record.run_id,
            workflow_id=record.workflow_id,
            event_type="run_status_updated",
            actor=update.operator or record.operator,
            target_kind="run",
            target_id=record.run_id,
            from_status=from_status,
            to_status=record.status,
            note=update.note,
            metadata={},
        )
        self.db.commit()
        self.db.refresh(record)
        return record.to_dict()

    def update_run_step(
        self,
        run_id: str,
        step_id: str,
        request: WorkflowRunStepUpdateRequest | dict[str, Any],
    ) -> dict:
        record = self._get_record(run_id)
        update = (
            request
            if isinstance(request, WorkflowRunStepUpdateRequest)
            else WorkflowRunStepUpdateRequest.model_validate(request)
        )
        if record.status in {"completed", "cancelled"}:
            raise WorkflowRunTransitionError(
                f"Run '{run_id}' is already '{record.status}' and cannot be modified."
            )
        step_previews = json.loads(record.step_previews_json)
        step_map = {step["step_id"]: step for step in step_previews}
        if step_id not in step_map:
            raise WorkflowRunTransitionError(f"Unknown step '{step_id}' in run '{run_id}'.")

        step = step_map[step_id]
        from_status = step["status"]
        self._validate_step_transition(from_status, update.status)
        if update.status in {"running", "awaiting_approval", "completed"} and step["blockers"]:
            raise WorkflowRunTransitionError(
                f"Step '{step_id}' is still blocked by: {', '.join(step['blockers'])}."
            )

        step["status"] = update.status
        if update.note:
            step["notes"] = update.note

        if update.status == "completed":
            self._unlock_dependent_steps(step_id, step_previews)

        record.step_previews_json = json.dumps(step_previews, ensure_ascii=False)
        previous_run_status = record.status
        record.status = self._derive_run_status(step_previews, record.status)
        self._refresh_run_indexes(record, step_previews)
        self._append_event(
            run_id=record.run_id,
            workflow_id=record.workflow_id,
            event_type="step_status_updated",
            actor=record.operator,
            target_kind="step",
            target_id=step_id,
            from_status=from_status,
            to_status=step["status"],
            note=update.note,
            metadata={},
        )
        if record.status != previous_run_status:
            self._append_event(
                run_id=record.run_id,
                workflow_id=record.workflow_id,
                event_type="run_status_derived",
                actor=record.operator,
                target_kind="run",
                target_id=record.run_id,
                from_status=previous_run_status,
                to_status=record.status,
                note=f"Derived from step '{step_id}' transition.",
                metadata={},
            )
        self.db.commit()
        self.db.refresh(record)
        return record.to_dict()

    def _get_record(self, run_id: str) -> WorkflowRunRecord:
        statement = select(WorkflowRunRecord).where(WorkflowRunRecord.run_id == run_id)
        record = self.db.scalar(statement)
        if record is None:
            raise WorkflowRunNotFoundError(run_id)
        return record

    @staticmethod
    def _validate_run_transition(current: str, target: RunStatus) -> None:
        allowed: dict[str, set[str]] = {
            "previewed": {"queued", "cancelled"},
            "queued": {"running", "cancelled", "blocked"},
            "running": {"awaiting_approval", "failed", "completed", "cancelled", "blocked"},
            "awaiting_approval": {"running", "failed", "completed", "cancelled"},
            "blocked": {"queued", "running", "cancelled"},
            "failed": {"queued", "cancelled"},
            "completed": set(),
            "cancelled": set(),
        }
        if target == current:
            return
        if target not in allowed.get(current, set()):
            raise WorkflowRunTransitionError(
                f"Cannot transition run from '{current}' to '{target}'."
            )

    @staticmethod
    def _validate_step_transition(current: str, target: StepStatus) -> None:
        allowed: dict[str, set[str]] = {
            "blocked": {"queued"},
            "queued": {"running", "awaiting_approval", "completed", "failed"},
            "running": {"awaiting_approval", "completed", "failed", "queued"},
            "awaiting_approval": {"running", "completed", "failed"},
            "failed": {"queued"},
            "completed": set(),
        }
        if target == current:
            return
        if target not in allowed.get(current, set()):
            raise WorkflowRunTransitionError(
                f"Cannot transition step from '{current}' to '{target}'."
            )

    @staticmethod
    def _unlock_dependent_steps(completed_step_id: str, step_previews: list[dict[str, Any]]) -> None:
        completed_ids = {
            step["step_id"]
            for step in step_previews
            if step["status"] == "completed"
        }
        completed_ids.add(completed_step_id)
        for step in step_previews:
            if completed_step_id not in step["depends_on"]:
                continue
            remaining_blockers = [
                dependency for dependency in step["depends_on"] if dependency not in completed_ids
            ]
            step["blockers"] = remaining_blockers
            if not remaining_blockers and step["status"] == "blocked":
                step["status"] = "queued"

    @staticmethod
    def _derive_run_status(step_previews: list[dict[str, Any]], current_status: str) -> str:
        if current_status == "cancelled":
            return "cancelled"
        statuses = {step["status"] for step in step_previews}
        if "failed" in statuses:
            return "failed"
        if statuses == {"completed"}:
            return "completed"
        if "awaiting_approval" in statuses:
            return "awaiting_approval"
        if "running" in statuses:
            return "running"
        if "queued" in statuses:
            return "queued"
        if "blocked" in statuses:
            return "blocked"
        return current_status

    @staticmethod
    def _refresh_run_indexes(record: WorkflowRunRecord, step_previews: list[dict[str, Any]]) -> None:
        record.next_steps_json = json.dumps(
            [step["step_id"] for step in step_previews if step["status"] == "queued"],
            ensure_ascii=False,
        )
        record.blocked_steps_json = json.dumps(
            [step["step_id"] for step in step_previews if step["status"] == "blocked"],
            ensure_ascii=False,
        )
        record.approval_steps_json = json.dumps(
            [
                step["step_id"]
                for step in step_previews
                if step["status"] == "awaiting_approval" or step["approval_required"]
            ],
            ensure_ascii=False,
        )

    def _append_event(
        self,
        *,
        run_id: str,
        workflow_id: str,
        event_type: str,
        actor: str | None,
        target_kind: str,
        target_id: str | None,
        from_status: str | None,
        to_status: str | None,
        note: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self.db.add(
            WorkflowRunEventRecord(
                run_id=run_id,
                workflow_id=workflow_id,
                event_type=event_type,
                actor=actor,
                target_kind=target_kind,
                target_id=target_id,
                from_status=from_status,
                to_status=to_status,
                note=note,
                metadata_json=json.dumps(metadata, ensure_ascii=False),
            )
        )

    def dispatch_to_openclaw(self, run_id: str) -> dict[str, Any]:
        """Dispatch a workflow run to OpenClaw runtime.

        This creates the dispatch manifest and attempts to send it to the OpenClaw
        daemon running locally (by default at ~/.openclaw).

        The dispatch format includes:
        - run_id: unique identifier for this run
        - workflow_id: which workflow to execute
        - steps: ordered list of steps with owner agents and dependencies
        - input_summary: operator-provided context

        Returns the dispatch result including the dispatch_id and status.
        """
        record = self._get_record(run_id)

        if record.status not in {"previewed", "queued"}:
            raise WorkflowRunTransitionError(
                f"Cannot dispatch run in '{record.status}' status. Only 'previewed' or 'queued' runs can be dispatched."
            )

        # Build the dispatch manifest
        manifest = self._build_dispatch_manifest(record)
        dispatch_id = f"dispatch-{run_id}"

        # Try to dispatch to OpenClaw daemon
        try:
            result = self._send_to_openclaw_daemon(dispatch_id, manifest)
            # Update run status to running
            record.status = "running"
            self._append_event(
                run_id=run_id,
                workflow_id=record.workflow_id,
                event_type="run_dispatched",
                actor=record.operator,
                target_kind="run",
                target_id=run_id,
                from_status="queued",
                to_status="running",
                note=f"Dispatched to OpenClaw: {dispatch_id}",
                metadata={"dispatch_id": dispatch_id, "dispatch_result": result},
            )
            self.db.commit()
            self.db.refresh(record)
            return {
                "dispatch_id": dispatch_id,
                "status": "dispatched",
                "run_id": run_id,
                "manifest": manifest,
                "result": result,
            }
        except Exception as exc:
            # Log the failure but don't change the run status
            self._append_event(
                run_id=run_id,
                workflow_id=record.workflow_id,
                event_type="dispatch_failed",
                actor=record.operator,
                target_kind="run",
                target_id=run_id,
                from_status=record.status,
                to_status=record.status,
                note=f"Dispatch failed: {exc}",
                metadata={"error": str(exc)},
            )
            self.db.commit()
            raise OpenClawDispatchError(f"Failed to dispatch to OpenClaw: {exc}") from exc

    def _build_dispatch_manifest(self, record: WorkflowRunRecord) -> dict[str, Any]:
        """Build the dispatch manifest for a workflow run."""
        manifest = self.manifest_service.load_manifest()
        step_previews = json.loads(record.step_previews_json)

        # Build agent map
        agent_map = {agent.id: agent for agent in [*manifest.agents, manifest.lead_bot]}

        steps = []
        for step in step_previews:
            owner = agent_map.get(step["owner_agent_id"])
            steps.append({
                "step_id": step["step_id"],
                "name": step["name"],
                "owner_agent_id": step["owner_agent_id"],
                "owner_display_name": owner.identity.display_name if owner else step["owner_agent_id"],
                "objective": step.get("objective", ""),
                "depends_on": step.get("depends_on", []),
                "approval_required": step.get("approval_required", False),
                "deliverables": step.get("deliverables", []),
            })

        return {
            "dispatch_id": f"dispatch-{record.run_id}",
            "run_id": record.run_id,
            "workflow_id": record.workflow_id,
            "workflow_name": record.workflow_name,
            "lead_agent_id": record.lead_agent_id,
            "input_summary": record.input_summary,
            "requested_outputs": json.loads(record.requested_outputs_json or "[]"),
            "steps": steps,
            "metadata": {
                "studio_id": manifest.metadata.studio_id,
                "studio_name": manifest.metadata.studio_name,
            },
        }

    def _send_to_openclaw_daemon(self, dispatch_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        """Send dispatch manifest to OpenClaw daemon.

        The OpenClaw daemon is typically running locally at ~/.openclaw or at a
        configured endpoint. This method attempts to communicate with it via
        the OpenClaw CLI or API.

        Returns the result from the daemon, or raises OpenClawDispatchError.
        """
        import os
        import subprocess

        openclaw_home = os.path.expanduser("~/.openclaw")
        dispatch_file = os.path.join(openclaw_home, "dispatches", f"{dispatch_id}.json")

        # Ensure dispatch directory exists
        os.makedirs(os.path.dirname(dispatch_file), exist_ok=True)

        # Write dispatch manifest to file
        with open(dispatch_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # Try to trigger OpenClaw daemon via CLI
        try:
            # Try openclaw CLI if available
            result = subprocess.run(
                ["openclaw", "dispatch", "--file", dispatch_file],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return {
                    "status": "success",
                    "stdout": result.stdout,
                    "dispatch_file": dispatch_file,
                }
            else:
                # CLI not available or failed, daemon might still pick up the file
                return {
                    "status": "queued",
                    "message": "Dispatch manifest written. OpenClaw daemon will pick it up.",
                    "dispatch_file": dispatch_file,
                }
        except FileNotFoundError:
            # openclaw CLI not found, daemon will pick up the file
            return {
                "status": "queued",
                "message": "OpenClaw CLI not found. Dispatch manifest written. Daemon will pick it up.",
                "dispatch_file": dispatch_file,
            }
        except subprocess.TimeoutExpired:
            raise OpenClawDispatchError("OpenClaw CLI timed out.")
        except Exception as exc:
            raise OpenClawDispatchError(f"Failed to communicate with OpenClaw: {exc}") from exc
