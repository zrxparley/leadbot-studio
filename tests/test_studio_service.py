import json

import pytest

from app.studio.schemas import StudioManifest, WorkflowRunRequest
from app.studio.service import (
    AgentNotFoundError,
    EntityConflictError,
    EntityInUseError,
    StudioManifestService,
    WorkflowNotFoundError,
)


def test_load_manifest_bootstraps_default_file(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    manifest = service.load_manifest()

    assert manifest.metadata.studio_id == "leadbot-studio"
    assert manifest.lead_bot.id == "studio-lead"
    assert manifest_path.exists()


def test_get_workflow_plan_returns_compiled_steps(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    plan = service.get_workflow_plan("build-delivery")

    assert plan["workflow_id"] == "build-delivery"
    assert plan["lead_bot"]["id"] == "studio-lead"
    assert len(plan["steps"]) == 4
    assert any(edge["to"] == "review" for edge in plan["edges"])


def test_export_openclaw_bundle_contains_agents_bindings_and_workflows(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    export_bundle = service.export_openclaw_bundle()

    assert export_bundle["studio"]["id"] == "leadbot-studio"
    assert len(export_bundle["agents"]["list"]) == 5
    assert len(export_bundle["workflows"]) == 2
    assert export_bundle["coordination"]["leadBot"]["id"] == "studio-lead"


def test_unknown_workflow_raises(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    with pytest.raises(WorkflowNotFoundError):
        service.get_workflow_plan("missing")


def test_manifest_validation_rejects_unknown_managed_agents(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    payload = service.load_manifest().model_dump(mode="json")
    payload["lead_bot"]["manages_agents"].append("ghost-agent")

    with pytest.raises(ValueError):
        StudioManifest.model_validate(payload)


def test_save_manifest_round_trips_changes(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    payload = service.load_manifest().model_dump(mode="json")
    payload["metadata"]["studio_name"] = "My Studio"

    saved = service.save_manifest(payload)
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert saved.metadata.studio_name == "My Studio"
    assert persisted["metadata"]["studio_name"] == "My Studio"


def test_create_update_and_delete_agent_round_trip(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    manifest = service.load_manifest()
    payload = manifest.agents[0].model_dump(mode="json")
    payload["id"] = "ops"
    payload["identity"]["display_name"] = "OpsBot"

    created = service.create_agent(payload)
    assert created.id == "ops"
    assert service.get_agent("ops").identity.display_name == "OpsBot"

    payload["notes"] = "Handles studio operations."
    updated = service.update_agent("ops", payload)
    assert updated.notes == "Handles studio operations."

    deleted = service.delete_agent("ops")
    assert deleted["deleted_agent_id"] == "ops"
    with pytest.raises(AgentNotFoundError):
        service.get_agent("ops")


def test_delete_agent_blocks_when_referenced_by_workflow(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    with pytest.raises(EntityInUseError):
        service.delete_agent("builder")


def test_create_update_and_delete_workflow_round_trip(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    manifest = service.load_manifest()
    payload = manifest.workflows[0].model_dump(mode="json")
    payload["id"] = "ops-handoff"
    payload["name"] = "Ops Handoff"
    payload["steps"][0]["id"] = "ops-intake"
    payload["steps"][1]["id"] = "ops-build"
    payload["steps"][1]["depends_on"] = ["ops-intake"]
    payload["steps"][2]["id"] = "ops-review"
    payload["steps"][2]["depends_on"] = ["ops-build"]
    payload["steps"][3]["id"] = "ops-deliver"
    payload["steps"][3]["depends_on"] = ["ops-review"]

    created = service.create_workflow(payload)
    assert created.id == "ops-handoff"
    assert service.get_workflow("ops-handoff").name == "Ops Handoff"

    payload["description"] = "Updated workflow description"
    updated = service.update_workflow("ops-handoff", payload)
    assert updated.description == "Updated workflow description"

    deleted = service.delete_workflow("ops-handoff")
    assert deleted["deleted_workflow_id"] == "ops-handoff"
    with pytest.raises(WorkflowNotFoundError):
        service.get_workflow("ops-handoff")


def test_duplicate_agent_create_raises_conflict(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    existing = service.load_manifest().agents[0]

    with pytest.raises(EntityConflictError):
        service.create_agent(existing.model_dump(mode="json"))


def test_dry_run_previews_queued_and_blocked_steps(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    preview = service.create_workflow_dry_run(
        "build-delivery",
        WorkflowRunRequest(operator="aha", input_summary="Ship the first studio release."),
    )

    assert preview.workflow_id == "build-delivery"
    assert preview.operator == "aha"
    assert "intake" in preview.next_steps
    assert "build" in preview.blocked_steps
    assert "review" in preview.approval_steps
    assert preview.step_previews[0].status == "queued"
    assert preview.step_previews[1].status == "blocked"
