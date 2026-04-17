from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from typing import Any

from app.core.config import get_settings
from app.studio.schemas import (
    AgentBot,
    BotIdentity,
    LeadBot,
    LeadBotDraftApplyRequest,
    LeadBotDraftApplyResult,
    LeadBotDraftBundle,
    LeadBotDraftRequest,
    SkillAttachment,
    StudioManifest,
    ToolPolicy,
    WorkflowDefinition,
    WorkflowParticipant,
    WorkflowRunPreview,
    WorkflowRunRequest,
    WorkflowRunStepPreview,
    WorkflowStep,
    WorkspaceProfile,
)


class WorkflowNotFoundError(ValueError):
    """Raised when a requested workflow is not defined in the studio manifest."""


class AgentNotFoundError(ValueError):
    """Raised when a requested agent is not defined in the studio manifest."""


class EntityConflictError(ValueError):
    """Raised when a requested create or update would conflict with existing data."""


class EntityInUseError(ValueError):
    """Raised when a delete would leave dangling references behind."""


class StudioManifestRepository:
    def __init__(self, manifest_path: str | None = None) -> None:
        settings = get_settings()
        self.manifest_path = Path(manifest_path or settings.leadbot_manifest_path)

    def load(self) -> StudioManifest:
        self._ensure_exists()
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return StudioManifest.model_validate(payload)

    def save(self, manifest: StudioManifest | dict[str, Any]) -> StudioManifest:
        validated = (
            manifest
            if isinstance(manifest, StudioManifest)
            else StudioManifest.model_validate(manifest)
        )
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return validated

    def _ensure_exists(self) -> None:
        if self.manifest_path.exists():
            return
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(_default_manifest_payload(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class StudioManifestService:
    def __init__(self, manifest_path: str | None = None) -> None:
        self.repository = StudioManifestRepository(manifest_path)

    def load_manifest(self) -> StudioManifest:
        return self.repository.load()

    def save_manifest(self, manifest: StudioManifest | dict[str, Any]) -> StudioManifest:
        return self.repository.save(manifest)

    def draft_studio_from_brief(
        self, request: LeadBotDraftRequest | dict[str, Any]
    ) -> LeadBotDraftBundle:
        manifest = self.load_manifest()
        prompt = (
            request
            if isinstance(request, LeadBotDraftRequest)
            else LeadBotDraftRequest.model_validate(request)
        )
        brief = prompt.brief.strip()
        brief_lower = brief.lower()
        templates = _select_agent_templates_for_brief(brief_lower)
        agents = [
            _build_agent_from_template(template_key, brief, manifest.defaults.openclaw_home)
            for template_key in templates
        ]
        workflow = _build_workflow_from_brief(brief, manifest.lead_bot, agents)
        rationale = _build_draft_rationale(brief, templates, workflow)
        return LeadBotDraftBundle(
            studio_name=_infer_studio_name(brief),
            brief=brief,
            leadbot_response=(
                f"我根据这段需求起草了 {len(agents)} 个 specialist agents 和 "
                f"{len([workflow])} 条 workflow。"
                "它们已经按研究、执行、校验、发布的节奏接好了依赖，你可以直接应用再微调。"
            ),
            rationale=rationale,
            suggested_agents=agents,
            suggested_workflows=[workflow],
        )

    def apply_draft_bundle(
        self,
        request: LeadBotDraftApplyRequest | LeadBotDraftBundle | dict[str, Any],
    ) -> LeadBotDraftApplyResult:
        apply_request = (
            request
            if isinstance(request, LeadBotDraftApplyRequest)
            else LeadBotDraftApplyRequest.model_validate(
                {"draft": request, "replace_existing": False}
                if isinstance(request, LeadBotDraftBundle)
                else request
            )
        )
        manifest = self.load_manifest()
        existing_agent_ids = {agent.id for agent in manifest.agents}
        existing_workflow_ids = {workflow.id for workflow in manifest.workflows}
        result = LeadBotDraftApplyResult()

        for agent in apply_request.draft.suggested_agents:
            normalized_agent = self._normalize_agent_for_apply(
                agent,
                existing_ids=existing_agent_ids | {manifest.lead_bot.id},
                replace_existing=apply_request.replace_existing,
            )
            if normalized_agent.id in existing_agent_ids:
                self.update_agent(normalized_agent.id, normalized_agent)
                result.updated_agents.append(normalized_agent.id)
            else:
                self.create_agent(normalized_agent)
                result.created_agents.append(normalized_agent.id)
                existing_agent_ids.add(normalized_agent.id)

        for workflow in apply_request.draft.suggested_workflows:
            normalized_workflow = self._normalize_workflow_for_apply(
                workflow,
                existing_ids=existing_workflow_ids,
                replace_existing=apply_request.replace_existing,
            )
            if normalized_workflow.id in existing_workflow_ids:
                self.update_workflow(normalized_workflow.id, normalized_workflow)
                result.updated_workflows.append(normalized_workflow.id)
            else:
                self.create_workflow(normalized_workflow)
                result.created_workflows.append(normalized_workflow.id)
                existing_workflow_ids.add(normalized_workflow.id)

        return result

    def get_summary(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        agent_catalog = [manifest.lead_bot, *manifest.agents]
        return {
            "studio_id": manifest.metadata.studio_id,
            "studio_name": manifest.metadata.studio_name,
            "description": manifest.metadata.description,
            "lead_bot_id": manifest.lead_bot.id,
            "agent_count": len(agent_catalog),
            "specialist_count": len(manifest.agents),
            "workflow_count": len(manifest.workflows),
            "skill_count": sum(len(agent.skills) for agent in agent_catalog),
            "channels": sorted(
                {
                    binding.channel
                    for agent in agent_catalog
                    for binding in agent.bindings
                }
            ),
        }

    @staticmethod
    def _normalize_agent_for_apply(
        agent: AgentBot,
        existing_ids: set[str],
        replace_existing: bool,
    ) -> AgentBot:
        if replace_existing or agent.id not in existing_ids:
            return agent
        return agent.model_copy(update={"id": _dedupe_slug(agent.id, existing_ids)})

    @staticmethod
    def _normalize_workflow_for_apply(
        workflow: WorkflowDefinition,
        existing_ids: set[str],
        replace_existing: bool,
    ) -> WorkflowDefinition:
        if replace_existing or workflow.id not in existing_ids:
            return workflow

        workflow_id = _dedupe_slug(workflow.id, existing_ids)
        step_id_map = {
            step.id: _dedupe_slug(step.id, set())
            for step in workflow.steps
        }
        updated_steps = [
            step.model_copy(
                update={
                    "id": step_id_map[step.id],
                    "depends_on": [step_id_map.get(dep, dep) for dep in step.depends_on],
                }
            )
            for step in workflow.steps
        ]
        return workflow.model_copy(update={"id": workflow_id, "steps": updated_steps})

    def list_agents(self) -> list[LeadBot | AgentBot]:
        manifest = self.load_manifest()
        return [manifest.lead_bot, *manifest.agents]

    def get_agent(self, agent_id: str) -> LeadBot | AgentBot:
        manifest = self.load_manifest()
        if manifest.lead_bot.id == agent_id:
            return manifest.lead_bot
        for agent in manifest.agents:
            if agent.id == agent_id:
                return agent
        raise AgentNotFoundError(agent_id)

    def create_agent(self, agent: AgentBot | dict[str, Any]) -> AgentBot:
        manifest = self.load_manifest()
        candidate = agent if isinstance(agent, AgentBot) else AgentBot.model_validate(agent)
        if candidate.id == manifest.lead_bot.id or any(
            existing.id == candidate.id for existing in manifest.agents
        ):
            raise EntityConflictError(f"Agent '{candidate.id}' already exists.")

        agents = [*manifest.agents, candidate]
        manages_agents = list(manifest.lead_bot.manages_agents)
        if candidate.id not in manages_agents:
            manages_agents.append(candidate.id)
        lead_bot = manifest.lead_bot.model_copy(update={"manages_agents": manages_agents})
        updated = manifest.model_copy(update={"lead_bot": lead_bot, "agents": agents})
        self.save_manifest(updated)
        return candidate

    def update_agent(self, agent_id: str, agent: AgentBot | dict[str, Any]) -> AgentBot:
        manifest = self.load_manifest()
        candidate = agent if isinstance(agent, AgentBot) else AgentBot.model_validate(agent)
        if candidate.id != agent_id:
            raise EntityConflictError("Agent id in the payload must match the path parameter.")

        for index, existing in enumerate(manifest.agents):
            if existing.id != agent_id:
                continue
            agents = list(manifest.agents)
            agents[index] = candidate
            updated = manifest.model_copy(update={"agents": agents})
            self.save_manifest(updated)
            return candidate
        raise AgentNotFoundError(agent_id)

    def delete_agent(self, agent_id: str) -> dict[str, str]:
        manifest = self.load_manifest()
        if manifest.lead_bot.id == agent_id:
            raise EntityInUseError("LeadBot cannot be deleted from the studio manifest.")

        for workflow in manifest.workflows:
            participants = {participant.agent_id for participant in workflow.participants}
            owners = {step.owner_agent_id for step in workflow.steps}
            handoffs = {target for step in workflow.steps for target in step.handoff_to}
            if agent_id in participants or agent_id in owners or agent_id in handoffs:
                raise EntityInUseError(
                    f"Agent '{agent_id}' is still referenced by workflow '{workflow.id}'."
                )

        remaining_agents = [agent for agent in manifest.agents if agent.id != agent_id]
        if len(remaining_agents) == len(manifest.agents):
            raise AgentNotFoundError(agent_id)

        lead_bot = manifest.lead_bot.model_copy(
            update={
                "manages_agents": [
                    managed_id
                    for managed_id in manifest.lead_bot.manages_agents
                    if managed_id != agent_id
                ],
                "governance": manifest.lead_bot.governance.model_copy(
                    update={
                        "a2a_allow": [
                            allowed_id
                            for allowed_id in manifest.lead_bot.governance.a2a_allow
                            if allowed_id != agent_id
                        ]
                    }
                ),
            }
        )
        updated = manifest.model_copy(update={"lead_bot": lead_bot, "agents": remaining_agents})
        self.save_manifest(updated)
        return {"deleted_agent_id": agent_id}

    def list_workflows(self) -> list[WorkflowDefinition]:
        return self.load_manifest().workflows

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition:
        manifest = self.load_manifest()
        for workflow in manifest.workflows:
            if workflow.id == workflow_id:
                return workflow
        raise WorkflowNotFoundError(workflow_id)

    def create_workflow(
        self, workflow: WorkflowDefinition | dict[str, Any]
    ) -> WorkflowDefinition:
        manifest = self.load_manifest()
        candidate = (
            workflow
            if isinstance(workflow, WorkflowDefinition)
            else WorkflowDefinition.model_validate(workflow)
        )
        if any(existing.id == candidate.id for existing in manifest.workflows):
            raise EntityConflictError(f"Workflow '{candidate.id}' already exists.")

        workflows = [*manifest.workflows, candidate]
        workflow_ids = list(manifest.lead_bot.workflow_ids)
        if candidate.id not in workflow_ids:
            workflow_ids.append(candidate.id)
        lead_bot = manifest.lead_bot.model_copy(update={"workflow_ids": workflow_ids})
        updated = manifest.model_copy(update={"lead_bot": lead_bot, "workflows": workflows})
        self.save_manifest(updated)
        return candidate

    def update_workflow(
        self, workflow_id: str, workflow: WorkflowDefinition | dict[str, Any]
    ) -> WorkflowDefinition:
        manifest = self.load_manifest()
        candidate = (
            workflow
            if isinstance(workflow, WorkflowDefinition)
            else WorkflowDefinition.model_validate(workflow)
        )
        if candidate.id != workflow_id:
            raise EntityConflictError("Workflow id in the payload must match the path parameter.")

        for index, existing in enumerate(manifest.workflows):
            if existing.id != workflow_id:
                continue
            workflows = list(manifest.workflows)
            workflows[index] = candidate
            updated = manifest.model_copy(update={"workflows": workflows})
            self.save_manifest(updated)
            return candidate
        raise WorkflowNotFoundError(workflow_id)

    def delete_workflow(self, workflow_id: str) -> dict[str, str]:
        manifest = self.load_manifest()
        remaining_workflows = [
            workflow for workflow in manifest.workflows if workflow.id != workflow_id
        ]
        if len(remaining_workflows) == len(manifest.workflows):
            raise WorkflowNotFoundError(workflow_id)

        lead_bot = manifest.lead_bot.model_copy(
            update={
                "workflow_ids": [
                    existing_id
                    for existing_id in manifest.lead_bot.workflow_ids
                    if existing_id != workflow_id
                ]
            }
        )
        updated = manifest.model_copy(
            update={"lead_bot": lead_bot, "workflows": remaining_workflows}
        )
        self.save_manifest(updated)
        return {"deleted_workflow_id": workflow_id}

    def get_workflow_plan(self, workflow_id: str) -> dict[str, Any]:
        manifest = self.load_manifest()
        workflow = self.get_workflow(workflow_id)
        agent_map = self._build_agent_map(manifest)

        steps = []
        edges = []
        for index, step in enumerate(workflow.steps, start=1):
            owner = agent_map[step.owner_agent_id]
            if step.depends_on:
                for dependency in step.depends_on:
                    edges.append({"from": dependency, "to": step.id})
            handoff_targets = [agent_map[target] for target in step.handoff_to]
            steps.append(
                {
                    "sequence": index,
                    "step_id": step.id,
                    "name": step.name,
                    "type": step.step_type,
                    "owner_agent_id": owner.id,
                    "owner_display_name": owner.identity.display_name,
                    "owner_role": owner.role,
                    "objective": step.objective,
                    "instructions": step.instructions,
                    "deliverables": step.deliverables,
                    "approval_required": step.approval_required,
                    "depends_on": step.depends_on,
                    "handoff_targets": [
                        {
                            "agent_id": target.id,
                            "display_name": target.identity.display_name,
                            "role": target.role,
                        }
                        for target in handoff_targets
                    ],
                }
            )

        return {
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "trigger": workflow.trigger,
            "lead_bot": {
                "id": manifest.lead_bot.id,
                "display_name": manifest.lead_bot.identity.display_name,
                "coordination_style": manifest.lead_bot.coordination_style,
                "approval_mode": manifest.lead_bot.governance.approval_mode,
            },
            "participants": [
                {
                    "agent_id": participant.agent_id,
                    "display_name": agent_map[participant.agent_id].identity.display_name,
                    "mode": participant.mode,
                    "responsibility": participant.responsibility,
                    "required_skills": participant.required_skills,
                }
                for participant in workflow.participants
            ],
            "steps": steps,
            "edges": edges,
            "outputs": workflow.outputs,
            "success_criteria": workflow.success_criteria,
            "handoff_protocol": {
                "standard_owner": manifest.lead_bot.identity.display_name,
                "leadbot_reviews_required": any(step["approval_required"] for step in steps),
                "managed_agents": manifest.lead_bot.manages_agents,
                "allowed_a2a": manifest.lead_bot.governance.a2a_allow,
            },
            "coverage": {
                "participants": len(workflow.participants),
                "steps": len(workflow.steps),
                "agents_with_bindings": sorted(
                    agent.id for agent in agent_map.values() if agent.bindings
                ),
                "participant_modes": {
                    participant.agent_id: participant.mode for participant in workflow.participants
                },
                "skill_matrix": {
                    participant.agent_id: participant.required_skills
                    for participant in workflow.participants
                },
            },
        }

    def create_workflow_dry_run(
        self, workflow_id: str, request: WorkflowRunRequest | dict[str, Any] | None = None
    ) -> WorkflowRunPreview:
        manifest = self.load_manifest()
        workflow = self.get_workflow(workflow_id)
        request_model = (
            request
            if isinstance(request, WorkflowRunRequest)
            else WorkflowRunRequest.model_validate(request or {})
        )
        agent_map = self._build_agent_map(manifest)

        step_previews: list[WorkflowRunStepPreview] = []
        next_steps: list[str] = []
        blocked_steps: list[str] = []
        approval_steps: list[str] = []
        for step in workflow.steps:
            owner = agent_map[step.owner_agent_id]
            blockers = list(step.depends_on)
            status = "queued" if not blockers else "blocked"
            if status == "queued":
                next_steps.append(step.id)
            else:
                blocked_steps.append(step.id)
            if step.approval_required:
                approval_steps.append(step.id)

            step_previews.append(
                WorkflowRunStepPreview(
                    step_id=step.id,
                    name=step.name,
                    owner_agent_id=owner.id,
                    owner_display_name=owner.identity.display_name,
                    status=status,
                    depends_on=step.depends_on,
                    blockers=blockers,
                    deliverables=step.deliverables,
                    approval_required=step.approval_required,
                    handoff_to=step.handoff_to,
                )
            )

        return WorkflowRunPreview(
            run_id=f"dryrun-{workflow.id}-{uuid4().hex[:8]}",
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            lead_agent_id=manifest.lead_bot.id,
            operator=request_model.operator,
            input_summary=request_model.input_summary,
            requested_outputs=request_model.requested_outputs or workflow.outputs,
            created_at=datetime.now(UTC),
            next_steps=next_steps,
            blocked_steps=blocked_steps,
            approval_steps=approval_steps,
            step_previews=step_previews,
            metadata=request_model.metadata,
        )

    def export_openclaw_bundle(self) -> dict[str, Any]:
        manifest = self.load_manifest()
        agents = [manifest.lead_bot, *manifest.agents]
        agent_entries = []
        bindings = []

        for agent in agents:
            entry: dict[str, Any] = {
                "id": agent.id,
                "name": agent.identity.display_name,
                "workspace": agent.workspace.root,
                "identity": {
                    "name": agent.identity.display_name,
                },
                "tools": {
                    "allow": agent.tool_policy.allow,
                    "deny": agent.tool_policy.deny,
                },
                "sandbox": {
                    "mode": agent.tool_policy.sandbox_mode,
                    "scope": agent.tool_policy.sandbox_scope,
                },
                "studio": {
                    "role": agent.role,
                    "objective": agent.objective,
                    "capabilities": agent.capabilities,
                    "skills": [skill.slug for skill in agent.skills if skill.enabled],
                },
            }
            if agent.identity.avatar:
                entry["identity"]["avatar"] = agent.identity.avatar
            agent_entries.append(entry)

            for binding in agent.bindings:
                match: dict[str, Any] = {"channel": binding.channel}
                if binding.account_id:
                    match["accountId"] = binding.account_id
                if binding.guild_id:
                    match["guildId"] = binding.guild_id
                if binding.peer_id:
                    match["peer"] = {
                        "kind": binding.peer_kind or "group",
                        "id": binding.peer_id,
                    }
                if binding.topic_id:
                    match["topicId"] = binding.topic_id

                bindings.append(
                    {
                        "agentId": agent.id,
                        "match": match,
                        "notes": binding.notes,
                    }
                )

        return {
            "studio": {
                "id": manifest.metadata.studio_id,
                "name": manifest.metadata.studio_name,
                "description": manifest.metadata.description,
            },
            "agents": {
                "list": agent_entries,
            },
            "bindings": bindings,
            "coordination": {
                "leadBot": {
                    "id": manifest.lead_bot.id,
                    "managesAgents": manifest.lead_bot.manages_agents,
                    "workflowIds": manifest.lead_bot.workflow_ids,
                    "approvalMode": manifest.lead_bot.governance.approval_mode,
                    "hardBlocks": manifest.lead_bot.governance.hard_blocks,
                    "a2aAllow": manifest.lead_bot.governance.a2a_allow,
                    "auditRequirements": manifest.lead_bot.governance.audit_requirements,
                }
            },
            "workflows": [
                {
                    "id": workflow.id,
                    "name": workflow.name,
                    "leadAgentId": workflow.lead_agent_id,
                    "participants": [
                        participant.model_dump(mode="json")
                        for participant in workflow.participants
                    ],
                    "steps": [step.model_dump(mode="json") for step in workflow.steps],
                    "outputs": workflow.outputs,
                    "successCriteria": workflow.success_criteria,
                }
                for workflow in manifest.workflows
            ],
        }

    @staticmethod
    def _build_agent_map(manifest: StudioManifest) -> dict[str, LeadBot | AgentBot]:
        agent_map: dict[str, LeadBot | AgentBot] = {manifest.lead_bot.id: manifest.lead_bot}
        agent_map.update({agent.id: agent for agent in manifest.agents})
        return agent_map


def _dedupe_slug(candidate: str, existing_ids: set[str]) -> str:
    if candidate not in existing_ids:
        return candidate
    index = 2
    while f"{candidate}-{index}" in existing_ids:
        index += 1
    return f"{candidate}-{index}"


def _slugify(value: str, fallback: str) -> str:
    output = []
    last_dash = False
    for char in value.lower():
        if char.isascii() and char.isalnum():
            output.append(char)
            last_dash = False
            continue
        if char in {" ", "-", "_", "/", "|"} and not last_dash:
            output.append("-")
            last_dash = True
    slug = "".join(output).strip("-")
    return slug or fallback


def _infer_studio_name(brief: str) -> str:
    brief_lower = brief.lower()
    if any(keyword in brief_lower for keyword in ["content", "marketing", "campaign", "social"]):
        return "LeadBot Content Studio"
    if any(keyword in brief_lower for keyword in ["app", "product", "code", "build", "automation"]):
        return "LeadBot Build Studio"
    if any(keyword in brief for keyword in ["内容", "营销", "发布", "增长"]):
        return "LeadBot 内容工作室"
    if any(keyword in brief for keyword in ["开发", "产品", "代码", "自动化", "系统"]):
        return "LeadBot 研发工作室"
    return "LeadBot Custom Studio"


def _select_agent_templates_for_brief(brief_lower: str) -> list[str]:
    selected: list[str] = []
    if any(keyword in brief_lower for keyword in ["research", "analysis", "brief", "insight"]):
        selected.append("researcher")
    if any(keyword in brief_lower for keyword in ["build", "product", "code", "app", "automation"]):
        selected.append("builder")
    if any(keyword in brief_lower for keyword in ["qa", "test", "review", "quality", "stability"]):
        selected.append("qa")
    if any(keyword in brief_lower for keyword in ["publish", "launch", "marketing", "content", "social"]):
        selected.append("publisher")

    if any(keyword in brief_lower for keyword in ["研究", "分析", "调研", "brief"]):
        selected.append("researcher")
    if any(keyword in brief_lower for keyword in ["开发", "代码", "产品", "自动化", "系统", "网站", "应用"]):
        selected.append("builder")
    if any(keyword in brief_lower for keyword in ["测试", "校验", "审核", "review", "验证"]):
        selected.append("qa")
    if any(keyword in brief_lower for keyword in ["发布", "上线", "营销", "内容", "增长", "运营"]):
        selected.append("publisher")

    if "researcher" not in selected:
        selected.insert(0, "researcher")
    if "builder" not in selected:
        selected.append("builder")
    if len(selected) < 3:
        selected.append("qa")
    if any(keyword in brief_lower for keyword in ["发布", "内容", "营销", "launch", "publish", "campaign"]) and "publisher" not in selected:
        selected.append("publisher")

    deduped: list[str] = []
    for item in selected:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _agent_template_catalog(openclaw_home: str) -> dict[str, dict[str, Any]]:
    return {
        "researcher": {
            "id": "researcher",
            "display_name": "ResearchBot",
            "role": "Research Specialist",
            "objective": "Gather source material, extract signal, and hand structured briefs to the rest of the studio.",
            "remark": "Discovery, research, and insight generation specialist.",
            "capabilities": ["research", "source validation", "briefing", "discovery"],
            "handoff_tags": ["research", "brief", "handoff-ready"],
            "notes": "Best used for discovery, research sprints, and operator brief creation.",
            "metadata": {"template": "researcher"},
            "skills": [
                {
                    "slug": "deep-research",
                    "name": "Deep Research",
                    "purpose": "Turn broad requests into source-backed research briefs.",
                }
            ],
            "tool_policy": {
                "allow": ["web.search", "docs.read", "files.write"],
                "deny": ["publish", "prod.deploy"],
            },
        },
        "builder": {
            "id": "builder",
            "display_name": "DevBot",
            "role": "Development Specialist",
            "objective": "Convert approved plans into implemented outputs with clear milestones and handoff notes.",
            "remark": "Implementation and systems delivery specialist.",
            "capabilities": ["implementation", "automation", "integration", "delivery"],
            "handoff_tags": ["build", "implementation", "ready-for-review"],
            "notes": "Best used for implementation, automation, and production output generation.",
            "metadata": {"template": "builder"},
            "skills": [
                {
                    "slug": "implementation-engine",
                    "name": "Implementation Engine",
                    "purpose": "Ship implementation slices with verification-ready handoff notes.",
                }
            ],
            "tool_policy": {
                "allow": ["files.write", "terminal.exec", "tests.run"],
                "deny": ["prod.deploy"],
            },
        },
        "qa": {
            "id": "qa",
            "display_name": "QABot",
            "role": "Quality Specialist",
            "objective": "Review output quality, catch gaps, and keep the workflow honest before delivery.",
            "remark": "Review and release-readiness specialist.",
            "capabilities": ["qa", "review", "validation", "release checks"],
            "handoff_tags": ["qa", "review", "release-gate"],
            "notes": "Best used for gating, validation, and operator-facing risk notes.",
            "metadata": {"template": "qa"},
            "skills": [
                {
                    "slug": "release-check",
                    "name": "Release Check",
                    "purpose": "Validate outputs against criteria and escalate residual risk.",
                }
            ],
            "tool_policy": {
                "allow": ["tests.run", "files.read", "terminal.exec"],
                "deny": ["publish", "prod.deploy"],
            },
        },
        "publisher": {
            "id": "publisher",
            "display_name": "PublishBot",
            "role": "Publishing Specialist",
            "objective": "Package approved work and adapt it for outward-facing delivery channels.",
            "remark": "Release, delivery, and distribution specialist.",
            "capabilities": ["publishing", "distribution", "packaging", "handoff"],
            "handoff_tags": ["publish", "distribution", "done"],
            "notes": "Best used for packaging the last mile and channel-ready outputs.",
            "metadata": {"template": "publisher"},
            "skills": [
                {
                    "slug": "delivery-packaging",
                    "name": "Delivery Packaging",
                    "purpose": "Prepare final deliverables for release and channel distribution.",
                }
            ],
            "tool_policy": {
                "allow": ["files.write", "docs.read", "terminal.exec"],
                "deny": ["schema.migrate"],
            },
        },
    }


def _build_agent_from_template(
    template_key: str,
    brief: str,
    openclaw_home: str,
) -> AgentBot:
    template = _agent_template_catalog(openclaw_home)[template_key]
    workspace_root = f"{openclaw_home.rstrip('/')}/workspace-{template['id']}"
    return AgentBot(
        id=template["id"],
        role=template["role"],
        objective=f"{template['objective']} Current studio brief: {brief}",
        identity=BotIdentity(
            display_name=template["display_name"],
            remark=template["remark"],
        ),
        workspace=WorkspaceProfile(
            root=workspace_root,
            soul_path=f"{workspace_root}/SOUL.md",
            agents_path=f"{workspace_root}/AGENTS.md",
            user_path=f"{workspace_root}/USER.md",
            skills_dir=f"{workspace_root}/skills",
            notes=template["notes"],
        ),
        capabilities=template["capabilities"],
        skills=[
            SkillAttachment(
                slug=skill["slug"],
                name=skill["name"],
                purpose=skill["purpose"],
            )
            for skill in template["skills"]
        ],
        tool_policy=ToolPolicy(
            allow=template["tool_policy"]["allow"],
            deny=template["tool_policy"]["deny"],
        ),
        handoff_tags=template["handoff_tags"],
        notes=template["notes"],
        metadata=template["metadata"],
    )


def _build_workflow_from_brief(
    brief: str,
    lead_bot: LeadBot,
    agents: list[AgentBot],
) -> WorkflowDefinition:
    workflow_slug = _slugify(brief[:48], "leadbot-flow")
    agent_ids = {agent.id for agent in agents}
    participants = [
        WorkflowParticipant(
            agent_id=lead_bot.id,
            mode="lead",
            responsibility="Translate the operator brief into delegated work and approve final outputs.",
            notes="LeadBot always owns the intake and final decision loop.",
        )
    ]
    for agent in agents:
        mode = "owner"
        responsibility = f"Own the {agent.role.lower()} slice of the workflow."
        participants.append(
            WorkflowParticipant(
                agent_id=agent.id,
                mode=mode,
                responsibility=responsibility,
                required_skills=[skill.slug for skill in agent.skills],
                notes=agent.identity.remark,
            )
        )

    steps: list[WorkflowStep] = [
        WorkflowStep(
            id="intake",
            name="Lead Intake",
            step_type="intake",
            owner_agent_id=lead_bot.id,
            objective="Interpret the operator request, set priorities, and hand off the first execution slice.",
            instructions=f"Brief from operator: {brief}",
            deliverables=["priority brief", "delegation plan"],
            handoff_to=[agents[0].id] if agents else [],
        )
    ]

    previous_step_id = "intake"
    if "researcher" in agent_ids:
        steps.append(
            WorkflowStep(
                id="research",
                name="Research Briefing",
                step_type="research",
                owner_agent_id="researcher",
                depends_on=[previous_step_id],
                objective="Collect the context, risks, and source material required to execute the brief well.",
                deliverables=["research brief", "source summary"],
                handoff_to=["builder"] if "builder" in agent_ids else ["qa"] if "qa" in agent_ids else [lead_bot.id],
            )
        )
        previous_step_id = "research"

    if "builder" in agent_ids:
        steps.append(
            WorkflowStep(
                id="build",
                name="Build Output",
                step_type="build",
                owner_agent_id="builder",
                depends_on=[previous_step_id],
                objective="Produce the core implementation or working output for the brief.",
                deliverables=["working output", "handoff notes"],
                handoff_to=["qa"] if "qa" in agent_ids else ["publisher"] if "publisher" in agent_ids else [lead_bot.id],
            )
        )
        previous_step_id = "build"

    if "qa" in agent_ids:
        steps.append(
            WorkflowStep(
                id="review",
                name="QA Review",
                step_type="qa",
                owner_agent_id="qa",
                depends_on=[previous_step_id],
                objective="Validate the output, surface residual risk, and prepare the final handoff.",
                deliverables=["qa findings", "approval notes"],
                handoff_to=["publisher"] if "publisher" in agent_ids else [lead_bot.id],
                approval_required=True,
            )
        )
        previous_step_id = "review"

    final_owner = "publisher" if "publisher" in agent_ids else lead_bot.id
    final_type = "publish" if "publisher" in agent_ids else "custom"
    steps.append(
        WorkflowStep(
            id="deliver",
            name="Final Delivery",
            step_type=final_type,
            owner_agent_id=final_owner,
            depends_on=[previous_step_id],
            objective="Package the approved output and hand the final result back through LeadBot.",
            deliverables=["final delivery", "operator summary"],
            handoff_to=[lead_bot.id],
            approval_required=final_owner != lead_bot.id,
        )
    )

    return WorkflowDefinition(
        id=workflow_slug,
        name=f"{_infer_studio_name(brief)} Delivery Flow",
        description=f"LeadBot-generated workflow for: {brief}",
        trigger=brief,
        lead_agent_id=lead_bot.id,
        participants=participants,
        steps=steps,
        outputs=["final delivery", "operator-ready summary"],
        success_criteria=[
            "Each specialist has a clear ownership slice.",
            "LeadBot can approve or redirect the final output.",
            "The workflow includes dependency-aware handoffs.",
        ],
        tags=["leadbot-generated", "auto-wired", "brief-driven"],
    )


def _build_draft_rationale(
    brief: str,
    templates: list[str],
    workflow: WorkflowDefinition,
) -> list[str]:
    rationale = [
        f"LeadBot picked {len(templates)} specialist roles based on the brief: {', '.join(templates)}.",
        "The workflow always starts with LeadBot intake so approvals and delegation stay centralized.",
        "Dependencies are auto-wired in execution order so each handoff has a clear predecessor.",
    ]
    if any(step.approval_required for step in workflow.steps):
        rationale.append("Approval gates were inserted before the final delivery stage.")
    if any(template == "publisher" for template in templates):
        rationale.append("A publishing stage was added because the brief implies outward-facing delivery.")
    if any(template == "researcher" for template in templates):
        rationale.append("A research stage was added so downstream agents start from a structured brief.")
    return rationale


def _default_manifest_payload() -> dict[str, Any]:
    return {
        "metadata": {
            "studio_id": "leadbot-studio",
            "studio_name": "LeadBot Studio",
            "description": "A reusable OpenClaw control plane for coordinating specialist AgentBots.",
            "version": "0.1.0",
        },
        "defaults": {
            "timezone": "Asia/Shanghai",
            "openclaw_home": "~/.openclaw",
            "default_model": "gpt-5.4",
            "default_channel": "telegram",
        },
        "lead_bot": {
            "id": "studio-lead",
            "type": "lead",
            "role": "Studio Lead",
            "objective": "Plan work, route tasks to the right specialists, enforce approvals, and deliver outputs.",
            "identity": {
                "display_name": "LeadBot",
                "avatar": "https://example.com/avatars/leadbot.png",
                "remark": "Main coordination bot for the studio.",
            },
            "workspace": {
                "root": "~/.openclaw/workspace-studio-lead",
                "soul_path": "~/.openclaw/workspace-studio-lead/SOUL.md",
                "agents_path": "~/.openclaw/workspace-studio-lead/AGENTS.md",
                "user_path": "~/.openclaw/workspace-studio-lead/USER.md",
                "skills_dir": "~/.openclaw/workspace-studio-lead/skills",
                "notes": "Control-plane workspace with governance rules and handoff standards.",
            },
            "capabilities": [
                "workflow planning",
                "agent dispatch",
                "approval routing",
                "handoff governance",
            ],
            "skills": [
                {
                    "slug": "workflow-manager",
                    "name": "Workflow Manager",
                    "source": "custom",
                    "enabled": True,
                    "purpose": "Compile flow definitions into dispatch plans and review gates.",
                    "debug_notes": "Trace handoff packets before enabling proactive execution.",
                },
                {
                    "slug": "openclaw-export",
                    "name": "OpenClaw Exporter",
                    "source": "custom",
                    "enabled": True,
                    "purpose": "Export LeadBot Studio metadata into OpenClaw-aligned config starters.",
                },
            ],
            "tool_policy": {
                "allow": ["read", "message", "cron", "sessions_list", "sessions_history"],
                "deny": ["write", "edit", "apply_patch"],
                "sandbox_mode": "agent",
                "sandbox_scope": "agent",
            },
            "bindings": [
                {
                    "channel": "telegram",
                    "account_id": "studio",
                    "peer_kind": "group",
                    "peer_id": "-1001234567890",
                    "topic_id": "1",
                    "notes": "Default control room topic.",
                }
            ],
            "handoff_tags": ["brief", "handoff", "approval", "done"],
            "notes": "LeadBot owns all workflow approvals and exception handling.",
            "metadata": {
                "team": "core-studio",
                "visibility": "internal",
            },
            "coordination_style": "manager",
            "manages_agents": ["researcher", "builder", "qa", "publisher"],
            "workflow_ids": ["build-delivery", "research-briefing"],
            "governance": {
                "approval_mode": "leadbot_review",
                "hard_blocks": [
                    "Never send external outreach without an approved workflow step.",
                    "Never grant credentials or change identity provider settings.",
                ],
                "escalation_targets": ["human-owner"],
                "audit_requirements": [
                    "Log all workflow dispatches.",
                    "Retain handoff packets for postmortems.",
                ],
                "a2a_allow": ["researcher", "builder", "qa", "publisher"],
            },
        },
        "agents": [
            {
                "id": "researcher",
                "role": "Research Specialist",
                "objective": "Find sources, collect context, and produce research packets for downstream agents.",
                "identity": {
                    "display_name": "ResearchBot",
                    "avatar": "https://example.com/avatars/researchbot.png",
                    "remark": "Best used for sourcing and discovery.",
                },
                "workspace": {
                    "root": "~/.openclaw/workspace-researcher",
                    "soul_path": "~/.openclaw/workspace-researcher/SOUL.md",
                    "agents_path": "~/.openclaw/workspace-researcher/AGENTS.md",
                    "skills_dir": "~/.openclaw/workspace-researcher/skills",
                },
                "capabilities": ["web research", "source triage", "evidence packets"],
                "skills": [
                    {
                        "slug": "web-research",
                        "name": "Web Research",
                        "source": "builtin",
                        "enabled": True,
                        "purpose": "Collect relevant sources and produce summaries.",
                    }
                ],
                "tool_policy": {
                    "allow": ["read", "browser", "message"],
                    "deny": ["apply_patch"],
                    "sandbox_mode": "workspace",
                    "sandbox_scope": "agent",
                },
                "bindings": [],
                "handoff_tags": ["research", "sources"],
                "notes": "Can be invoked by LeadBot or by BuilderBot for clarifications.",
                "metadata": {"discipline": "research"},
            },
            {
                "id": "builder",
                "role": "Build Specialist",
                "objective": "Implement specs and ship working code or automation assets.",
                "identity": {
                    "display_name": "BuilderBot",
                    "avatar": "https://example.com/avatars/builderbot.png",
                    "remark": "Owns implementation and patch generation.",
                },
                "workspace": {
                    "root": "~/.openclaw/workspace-builder",
                    "soul_path": "~/.openclaw/workspace-builder/SOUL.md",
                    "agents_path": "~/.openclaw/workspace-builder/AGENTS.md",
                    "skills_dir": "~/.openclaw/workspace-builder/skills",
                },
                "capabilities": ["coding", "automation building", "artifact assembly"],
                "skills": [
                    {
                        "slug": "code",
                        "name": "Code",
                        "source": "local",
                        "enabled": True,
                        "purpose": "Implement code changes with verification discipline.",
                    }
                ],
                "tool_policy": {
                    "allow": ["read", "write", "edit", "apply_patch", "exec", "message"],
                    "deny": [],
                    "sandbox_mode": "workspace",
                    "sandbox_scope": "agent",
                },
                "bindings": [],
                "handoff_tags": ["build", "patch", "artifact"],
                "notes": "Primary executor for production tasks.",
                "metadata": {"discipline": "engineering"},
            },
            {
                "id": "qa",
                "role": "QA Specialist",
                "objective": "Review outputs, run checks, and report risks before release.",
                "identity": {
                    "display_name": "QABot",
                    "avatar": "https://example.com/avatars/qabot.png",
                    "remark": "Focused on validation and regressions.",
                },
                "workspace": {
                    "root": "~/.openclaw/workspace-qa",
                    "soul_path": "~/.openclaw/workspace-qa/SOUL.md",
                    "agents_path": "~/.openclaw/workspace-qa/AGENTS.md",
                    "skills_dir": "~/.openclaw/workspace-qa/skills",
                },
                "capabilities": ["testing", "review", "risk assessment"],
                "skills": [
                    {
                        "slug": "checks",
                        "name": "Checks",
                        "source": "custom",
                        "enabled": True,
                        "purpose": "Run structured verification suites and summarize findings.",
                        "debug_notes": "Keep failure logs attached to the run summary.",
                    }
                ],
                "tool_policy": {
                    "allow": ["read", "exec", "message"],
                    "deny": ["apply_patch"],
                    "sandbox_mode": "workspace",
                    "sandbox_scope": "agent",
                },
                "bindings": [],
                "handoff_tags": ["qa", "review", "risk"],
                "notes": "Second-stage reviewer before publication or deployment.",
                "metadata": {"discipline": "quality"},
            },
            {
                "id": "publisher",
                "role": "Delivery Specialist",
                "objective": "Package and distribute approved outputs to the final destination.",
                "identity": {
                    "display_name": "PublisherBot",
                    "avatar": "https://example.com/avatars/publisherbot.png",
                    "remark": "Handles distribution and final delivery.",
                },
                "workspace": {
                    "root": "~/.openclaw/workspace-publisher",
                    "soul_path": "~/.openclaw/workspace-publisher/SOUL.md",
                    "agents_path": "~/.openclaw/workspace-publisher/AGENTS.md",
                    "skills_dir": "~/.openclaw/workspace-publisher/skills",
                },
                "capabilities": ["publishing", "delivery", "handoff completion"],
                "skills": [
                    {
                        "slug": "distribution",
                        "name": "Distribution",
                        "source": "custom",
                        "enabled": True,
                        "purpose": "Deliver approved outputs to channels, repos, or stakeholders.",
                    }
                ],
                "tool_policy": {
                    "allow": ["read", "message", "cron"],
                    "deny": ["apply_patch"],
                    "sandbox_mode": "agent",
                    "sandbox_scope": "agent",
                },
                "bindings": [
                    {
                        "channel": "telegram",
                        "account_id": "studio",
                        "peer_kind": "group",
                        "peer_id": "-1001234567890",
                        "topic_id": "3",
                        "notes": "Delivery lane.",
                    }
                ],
                "handoff_tags": ["publish", "deliver", "announce"],
                "notes": "Only runs after LeadBot approval.",
                "metadata": {"discipline": "delivery"},
            },
        ],
        "workflows": [
            {
                "id": "build-delivery",
                "name": "Build Delivery",
                "description": "Turn a request into a reviewed and delivered artifact.",
                "trigger": "Incoming build request in the control room.",
                "lead_agent_id": "studio-lead",
                "participants": [
                    {
                        "agent_id": "studio-lead",
                        "mode": "lead",
                        "responsibility": "Scope the task and approve gates.",
                        "required_skills": ["workflow-manager"],
                    },
                    {
                        "agent_id": "builder",
                        "mode": "owner",
                        "responsibility": "Implement the requested output.",
                        "required_skills": ["code"],
                    },
                    {
                        "agent_id": "qa",
                        "mode": "reviewer",
                        "responsibility": "Validate quality and regressions.",
                        "required_skills": ["checks"],
                    },
                    {
                        "agent_id": "publisher",
                        "mode": "support",
                        "responsibility": "Distribute approved artifacts.",
                        "required_skills": ["distribution"],
                    },
                ],
                "steps": [
                    {
                        "id": "intake",
                        "name": "Lead intake",
                        "step_type": "intake",
                        "owner_agent_id": "studio-lead",
                        "objective": "Clarify request scope and select the specialist team.",
                        "deliverables": ["task brief", "success criteria"],
                        "handoff_to": ["builder"],
                        "approval_required": False,
                    },
                    {
                        "id": "build",
                        "name": "Implementation",
                        "step_type": "build",
                        "owner_agent_id": "builder",
                        "depends_on": ["intake"],
                        "objective": "Produce the requested output and attach implementation notes.",
                        "deliverables": ["working artifact", "implementation summary"],
                        "handoff_to": ["qa"],
                        "approval_required": False,
                    },
                    {
                        "id": "review",
                        "name": "Quality review",
                        "step_type": "qa",
                        "owner_agent_id": "qa",
                        "depends_on": ["build"],
                        "objective": "Verify the artifact and raise findings if needed.",
                        "deliverables": ["verification report"],
                        "handoff_to": ["studio-lead", "publisher"],
                        "approval_required": True,
                    },
                    {
                        "id": "deliver",
                        "name": "Approved delivery",
                        "step_type": "publish",
                        "owner_agent_id": "publisher",
                        "depends_on": ["review"],
                        "objective": "Deliver the approved artifact to the designated channel.",
                        "deliverables": ["delivery confirmation"],
                        "handoff_to": ["studio-lead"],
                        "approval_required": False,
                    },
                ],
                "outputs": ["artifact", "verification report", "delivery confirmation"],
                "success_criteria": [
                    "The artifact is produced.",
                    "QA has signed off or raised tracked findings.",
                    "LeadBot has an audit trail for every handoff.",
                ],
                "tags": ["build", "delivery"],
            },
            {
                "id": "research-briefing",
                "name": "Research Briefing",
                "description": "Collect sources, synthesize them, and deliver a structured briefing.",
                "trigger": "A topic brief or trend-monitoring request from the operator.",
                "lead_agent_id": "studio-lead",
                "participants": [
                    {
                        "agent_id": "studio-lead",
                        "mode": "lead",
                        "responsibility": "Own output framing and final approval.",
                        "required_skills": ["workflow-manager"],
                    },
                    {
                        "agent_id": "researcher",
                        "mode": "owner",
                        "responsibility": "Collect and package source material.",
                        "required_skills": ["web-research"],
                    },
                    {
                        "agent_id": "publisher",
                        "mode": "support",
                        "responsibility": "Send the final briefing to the delivery lane.",
                        "required_skills": ["distribution"],
                    },
                ],
                "steps": [
                    {
                        "id": "triage",
                        "name": "Brief triage",
                        "step_type": "intake",
                        "owner_agent_id": "studio-lead",
                        "objective": "Frame the research question and the expected output format.",
                        "deliverables": ["research brief"],
                        "handoff_to": ["researcher"],
                    },
                    {
                        "id": "research-pass",
                        "name": "Source collection",
                        "step_type": "research",
                        "owner_agent_id": "researcher",
                        "depends_on": ["triage"],
                        "objective": "Collect relevant sources and synthesize the key findings.",
                        "deliverables": ["source list", "research packet"],
                        "handoff_to": ["studio-lead"],
                    },
                    {
                        "id": "approval",
                        "name": "Lead approval",
                        "step_type": "review",
                        "owner_agent_id": "studio-lead",
                        "depends_on": ["research-pass"],
                        "objective": "Approve the final briefing or request a follow-up pass.",
                        "deliverables": ["approved briefing"],
                        "handoff_to": ["publisher"],
                        "approval_required": True,
                    },
                    {
                        "id": "send",
                        "name": "Distribution",
                        "step_type": "publish",
                        "owner_agent_id": "publisher",
                        "depends_on": ["approval"],
                        "objective": "Distribute the final briefing.",
                        "deliverables": ["distribution log"],
                        "handoff_to": ["studio-lead"],
                    },
                ],
                "outputs": ["research packet", "approved briefing", "distribution log"],
                "success_criteria": [
                    "Sources are traceable.",
                    "LeadBot approves the final message.",
                    "The delivery channel receives the briefing.",
                ],
                "tags": ["research", "briefing"],
            },
        ],
    }
