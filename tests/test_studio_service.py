import json

import pytest

from app.studio.schemas import StudioManifest
from app.studio.service import StudioManifestService, WorkflowNotFoundError


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
