import json
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.studio.schemas import LeadBotModelDraftResponse, StudioManifest, WorkflowRunRequest
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


def test_leadbot_can_draft_connected_agents_and_workflow_from_brief(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    draft = service.draft_studio_from_brief(
        {
            "brief": "我想做一个内容增长工作室，LeadBot 统筹，研究员负责选题，开发负责自动化，QA 负责审校，发布负责上线分发。",
            "operator": "aha",
        }
    )

    assert draft.studio_name
    assert len(draft.suggested_agents) >= 4
    assert {agent.id for agent in draft.suggested_agents} >= {
        "researcher",
        "builder",
        "qa",
        "publisher",
    }
    workflow = draft.suggested_workflows[0]
    assert workflow.lead_agent_id == "studio-lead"
    assert workflow.steps[0].id == "intake"
    assert any(step.id == "deliver" for step in workflow.steps)
    assert any(step.approval_required for step in workflow.steps)
    assert draft.draft_source == "deterministic"
    assert draft.conversation[-1].role == "operator"
    assert draft.suggested_next_prompts


def test_apply_leadbot_draft_can_update_existing_studio(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    draft = service.draft_studio_from_brief(
        {
            "brief": "Build a product launch studio with research, development, QA, and publishing.",
        }
    )

    result = service.apply_draft_bundle(
        {
            "draft": draft.model_dump(mode="json"),
            "replace_existing": True,
        }
    )
    manifest = service.load_manifest()

    assert "researcher" in result.updated_agents
    assert "builder" in result.updated_agents
    assert len(result.created_workflows) == 1
    assert manifest.lead_bot.workflow_ids
    assert any(
        workflow.id in result.created_workflows for workflow in manifest.workflows
    )


def test_leadbot_can_use_model_backed_drafting_with_refinement_context(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    settings = Settings(
        leadbot_draft_provider="openai",
        leadbot_draft_model="gpt-5.4",
        openai_api_key="test-key",
    )
    service = StudioManifestService(str(manifest_path), settings=settings)
    captured_request: dict[str, object] = {}

    class FakeResponses:
        def parse(self, **kwargs):
            captured_request.update(kwargs)
            payload = {
                "studio_name": "LeadBot Launch Studio",
                "leadbot_response": "我把这次工作室草案改成了更偏发布驱动的形态。",
                "rationale": [
                    "The operator asked for a launch-oriented workflow.",
                    "The existing draft already had the right core agents, so LeadBot refined it instead of rebuilding from scratch.",
                ],
                "suggested_next_prompts": [
                    "把发布前的 QA 提前一轮。",
                    "再加一个负责社媒分发的 Agent。",
                ],
                "agents": [
                    {
                        "id": "researcher",
                        "display_name": "Launch Researcher",
                        "role": "Launch Research Specialist",
                        "objective": "Find launch angles and gather proof points.",
                        "template_hint": "researcher",
                        "remark": "Own the signal-gathering pass.",
                        "capabilities": ["launch research", "proof gathering"],
                        "skills": [
                            {
                                "slug": "launch-research",
                                "name": "Launch Research",
                                "purpose": "Shape the launch brief.",
                            }
                        ],
                        "handoff_tags": ["launch-brief"],
                    },
                    {
                        "id": "publisher",
                        "display_name": "Launch Publisher",
                        "role": "Launch Publishing Specialist",
                        "objective": "Package and distribute the launch assets.",
                        "template_hint": "publisher",
                        "remark": "Own outbound launch delivery.",
                        "capabilities": ["launch packaging", "distribution"],
                    },
                ],
                "workflow": {
                    "id": "launch-flow",
                    "name": "Launch Flow",
                    "description": "LeadBot-managed launch workflow.",
                    "trigger": "Operator asks for a launch studio.",
                    "participants": [
                        {
                            "agent_id": "researcher",
                            "mode": "owner",
                            "responsibility": "Own launch research.",
                            "required_skills": ["launch-research"],
                        },
                        {
                            "agent_id": "publisher",
                            "mode": "owner",
                            "responsibility": "Own publishing and distribution.",
                        },
                    ],
                    "steps": [
                        {
                            "id": "intake",
                            "name": "Lead Intake",
                            "step_type": "intake",
                            "owner_agent_id": "studio-lead",
                            "objective": "Set launch priorities.",
                            "deliverables": ["launch brief"],
                            "handoff_to": ["researcher"],
                        },
                        {
                            "id": "research-pass",
                            "name": "Launch Research",
                            "step_type": "research",
                            "owner_agent_id": "researcher",
                            "depends_on": ["intake"],
                            "objective": "Build the launch brief.",
                            "deliverables": ["launch insights"],
                            "handoff_to": ["publisher"],
                        },
                        {
                            "id": "release",
                            "name": "Launch Release",
                            "step_type": "publish",
                            "owner_agent_id": "publisher",
                            "depends_on": ["research-pass"],
                            "objective": "Distribute the launch assets.",
                            "deliverables": ["launch package"],
                            "handoff_to": ["studio-lead"],
                            "approval_required": True,
                        },
                    ],
                    "outputs": ["launch package"],
                    "success_criteria": ["Launch assets are ready for operator review."],
                    "tags": ["launch", "model"],
                },
            }
            return SimpleNamespace(
                output_parsed=LeadBotModelDraftResponse.model_validate(payload)
            )

    service._build_openai_client = lambda: SimpleNamespace(responses=FakeResponses())

    draft = service.draft_studio_from_brief(
        {
            "brief": "把这个工作室改成发布优先，并减少开发步骤。",
            "conversation": [
                {"role": "operator", "content": "先给我起一个工作室。"},
                {"role": "leadbot", "content": "我已经起草了一版基础工作室。"},
            ],
            "current_draft": {
                "studio_name": "Draft Studio",
                "brief": "先给我起一个工作室。",
                "leadbot_response": "旧草案",
                "suggested_agents": [],
                "suggested_workflows": [],
            },
        }
    )

    assert draft.draft_source == "model"
    assert draft.suggested_agents[0].identity.display_name == "Launch Researcher"
    assert draft.suggested_workflows[0].steps[-1].approval_required is True
    assert draft.conversation[-1].role == "leadbot"
    encoded_input = json.loads(captured_request["input"][1]["content"])
    assert encoded_input["current_draft"]["studio_name"] == "Draft Studio"
    assert len(encoded_input["conversation"]) == 2


def test_leadbot_model_failure_falls_back_to_builtin_planner(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    settings = Settings(
        leadbot_draft_provider="openai",
        openai_api_key="test-key",
    )
    service = StudioManifestService(str(manifest_path), settings=settings)
    service._build_openai_client = lambda: SimpleNamespace(
        responses=SimpleNamespace(parse=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    )

    draft = service.draft_studio_from_brief({"brief": "Build a studio for launch operations."})

    assert draft.draft_source == "fallback"
    assert any("fallback" in item.lower() for item in draft.rationale)


def test_draft_includes_manifest_diff_preview(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    draft = service.draft_studio_from_brief(
        {"brief": "Create a launch studio with research and publishing only."}
    )

    assert draft.manifest_diff.created_workflows or draft.manifest_diff.updated_workflows
    assert draft.manifest_diff.deleted_agents
    assert draft.manifest_diff.warnings


def test_apply_draft_can_sync_remove_missing_entities(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))
    manifest = service.load_manifest()
    builder = next(agent for agent in manifest.agents if agent.id == "builder")
    workflow = manifest.workflows[0].model_copy(
        update={
            "id": "builder-only",
            "name": "Builder Only",
            "participants": [
                participant
                for participant in manifest.workflows[0].participants
                if participant.agent_id in {"studio-lead", "builder"}
            ],
            "steps": [
                step.model_copy(
                    update={
                        "owner_agent_id": "builder" if step.id != "intake" else "studio-lead",
                        "handoff_to": [
                            target for target in step.handoff_to if target in {"studio-lead", "builder"}
                        ],
                    }
                )
                for step in manifest.workflows[0].steps
            ],
        }
    )
    trimmed_draft = {
        "studio_name": "Trimmed Studio",
        "brief": "Keep only builder flow.",
        "leadbot_response": "Trim to builder-only operations.",
        "suggested_agents": [builder.model_dump(mode="json")],
        "suggested_workflows": [workflow.model_dump(mode="json")],
    }

    result = service.apply_draft_bundle(
        {
            "draft": trimmed_draft,
            "replace_existing": True,
            "sync_removed_entities": True,
        }
    )
    updated = service.load_manifest()

    assert "publisher" in result.deleted_agents
    assert "research-briefing" in result.deleted_workflows
    assert {agent.id for agent in updated.agents} == {"builder"}
    assert {workflow.id for workflow in updated.workflows} == {workflow.id}


def test_execute_leadbot_instruction_can_auto_apply(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    service = StudioManifestService(str(manifest_path))

    result = service.execute_leadbot_instruction(
        {
            "brief": "Create a content launch studio with research, QA, and publishing.",
            "auto_apply": True,
            "replace_existing": True,
            "sync_removed_entities": False,
        }
    )

    assert result.applied is True
    assert result.apply_result is not None
    assert result.draft.manifest_diff is not None
