from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.studio.schemas import AgentBot, LeadBot, StudioManifest, WorkflowDefinition


class WorkflowNotFoundError(ValueError):
    """Raised when a requested workflow is not defined in the studio manifest."""


class StudioManifestService:
    def __init__(self, manifest_path: str | None = None) -> None:
        settings = get_settings()
        self.manifest_path = Path(manifest_path or settings.leadbot_manifest_path)

    def load_manifest(self) -> StudioManifest:
        self._ensure_manifest_exists()
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return StudioManifest.model_validate(payload)

    def save_manifest(self, manifest: StudioManifest | dict[str, Any]) -> StudioManifest:
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

    def list_agents(self) -> list[LeadBot | AgentBot]:
        manifest = self.load_manifest()
        return [manifest.lead_bot, *manifest.agents]

    def list_workflows(self) -> list[WorkflowDefinition]:
        return self.load_manifest().workflows

    def get_workflow_plan(self, workflow_id: str) -> dict[str, Any]:
        manifest = self.load_manifest()
        workflow = next((item for item in manifest.workflows if item.id == workflow_id), None)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)

        agent_map = {manifest.lead_bot.id: manifest.lead_bot}
        agent_map.update({agent.id: agent for agent in manifest.agents})

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

    def _ensure_manifest_exists(self) -> None:
        if self.manifest_path.exists():
            return
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(_default_manifest_payload(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


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
