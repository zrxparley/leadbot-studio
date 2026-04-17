from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RunStatus = Literal[
    "previewed",
    "queued",
    "running",
    "awaiting_approval",
    "blocked",
    "failed",
    "completed",
    "cancelled",
]
StepStatus = Literal[
    "queued",
    "blocked",
    "running",
    "awaiting_approval",
    "failed",
    "completed",
]


class BotIdentity(BaseModel):
    display_name: str
    avatar: str | None = None
    remark: str | None = None


class WorkspaceProfile(BaseModel):
    root: str
    soul_path: str | None = None
    agents_path: str | None = None
    user_path: str | None = None
    skills_dir: str | None = None
    notes: str | None = None


class SkillAttachment(BaseModel):
    slug: str
    name: str
    source: Literal["builtin", "local", "clawhub", "custom"] = "custom"
    enabled: bool = True
    purpose: str
    debug_notes: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ToolPolicy(BaseModel):
    allow: list[str] = Field(default_factory=list)
    deny: list[str] = Field(default_factory=list)
    sandbox_mode: Literal["none", "workspace", "agent", "all"] = "workspace"
    sandbox_scope: Literal["workspace", "agent"] = "agent"


class ChannelBinding(BaseModel):
    channel: str
    account_id: str | None = None
    guild_id: str | None = None
    peer_kind: Literal["dm", "group", "topic", "channel"] | None = None
    peer_id: str | None = None
    topic_id: str | None = None
    notes: str | None = None


class GovernancePolicy(BaseModel):
    approval_mode: Literal["human_required", "leadbot_review", "fully_delegated"] = (
        "leadbot_review"
    )
    hard_blocks: list[str] = Field(default_factory=list)
    escalation_targets: list[str] = Field(default_factory=list)
    audit_requirements: list[str] = Field(default_factory=list)
    a2a_allow: list[str] = Field(default_factory=list)


class AgentBot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["specialist"] = "specialist"
    role: str
    objective: str
    identity: BotIdentity
    workspace: WorkspaceProfile
    capabilities: list[str] = Field(default_factory=list)
    skills: list[SkillAttachment] = Field(default_factory=list)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    bindings: list[ChannelBinding] = Field(default_factory=list)
    handoff_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class LeadBot(AgentBot):
    type: Literal["lead"] = "lead"
    coordination_style: Literal["manager", "planner", "dispatcher"] = "manager"
    manages_agents: list[str] = Field(default_factory=list)
    workflow_ids: list[str] = Field(default_factory=list)
    governance: GovernancePolicy = Field(default_factory=GovernancePolicy)


class WorkflowParticipant(BaseModel):
    agent_id: str
    mode: Literal["lead", "owner", "support", "reviewer", "observer"] = "owner"
    responsibility: str
    required_skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class WorkflowStep(BaseModel):
    id: str
    name: str
    step_type: Literal[
        "intake",
        "research",
        "design",
        "build",
        "review",
        "qa",
        "publish",
        "ops",
        "custom",
    ] = "custom"
    owner_agent_id: str
    depends_on: list[str] = Field(default_factory=list)
    objective: str
    instructions: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    handoff_to: list[str] = Field(default_factory=list)
    approval_required: bool = False


class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    trigger: str
    lead_agent_id: str
    participants: list[WorkflowParticipant]
    steps: list[WorkflowStep]
    outputs: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class LeadBotConversationTurn(BaseModel):
    role: Literal["operator", "leadbot"] = "operator"
    content: str


class LeadBotModelSkillDraft(BaseModel):
    slug: str
    name: str
    purpose: str


class LeadBotModelAgentDraft(BaseModel):
    id: str
    display_name: str
    role: str
    objective: str
    template_hint: Literal["researcher", "builder", "qa", "publisher", "custom"] = "custom"
    remark: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    skills: list[LeadBotModelSkillDraft] = Field(default_factory=list)
    handoff_tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class LeadBotModelWorkflowParticipantDraft(BaseModel):
    agent_id: str
    mode: Literal["lead", "owner", "support", "reviewer", "observer"] = "owner"
    responsibility: str
    required_skills: list[str] = Field(default_factory=list)
    notes: str | None = None


class LeadBotModelWorkflowStepDraft(BaseModel):
    id: str
    name: str
    step_type: Literal[
        "intake",
        "research",
        "design",
        "build",
        "review",
        "qa",
        "publish",
        "ops",
        "custom",
    ] = "custom"
    owner_agent_id: str
    depends_on: list[str] = Field(default_factory=list)
    objective: str
    instructions: str | None = None
    deliverables: list[str] = Field(default_factory=list)
    handoff_to: list[str] = Field(default_factory=list)
    approval_required: bool = False


class LeadBotModelWorkflowDraft(BaseModel):
    id: str
    name: str
    description: str
    trigger: str
    participants: list[LeadBotModelWorkflowParticipantDraft] = Field(default_factory=list)
    steps: list[LeadBotModelWorkflowStepDraft] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class LeadBotModelDraftResponse(BaseModel):
    studio_name: str
    leadbot_response: str
    rationale: list[str] = Field(default_factory=list)
    suggested_next_prompts: list[str] = Field(default_factory=list)
    agents: list[LeadBotModelAgentDraft] = Field(default_factory=list)
    workflow: LeadBotModelWorkflowDraft


class LeadBotDraftChange(BaseModel):
    entity_type: Literal["agent", "workflow"]
    entity_id: str
    action: Literal["create", "update", "delete", "unchanged"]
    label: str
    summary: str


class LeadBotWorkflowParticipantChange(BaseModel):
    agent_id: str
    action: Literal["create", "update", "delete", "unchanged"]
    summary: str
    before_mode: str | None = None
    after_mode: str | None = None


class LeadBotWorkflowStepChange(BaseModel):
    step_id: str
    step_name: str
    action: Literal["create", "update", "delete", "unchanged"]
    summary: str
    before_owner_agent_id: str | None = None
    after_owner_agent_id: str | None = None
    before_depends_on: list[str] = Field(default_factory=list)
    after_depends_on: list[str] = Field(default_factory=list)
    before_position: int | None = None
    after_position: int | None = None
    before_approval_required: bool | None = None
    after_approval_required: bool | None = None


class LeadBotWorkflowReview(BaseModel):
    workflow_id: str
    workflow_name: str
    action: Literal["create", "update", "delete", "unchanged"]
    summary: str
    participant_changes: list[LeadBotWorkflowParticipantChange] = Field(default_factory=list)
    step_changes: list[LeadBotWorkflowStepChange] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class LeadBotDraftDiff(BaseModel):
    created_agents: list[LeadBotDraftChange] = Field(default_factory=list)
    updated_agents: list[LeadBotDraftChange] = Field(default_factory=list)
    deleted_agents: list[LeadBotDraftChange] = Field(default_factory=list)
    unchanged_agents: list[LeadBotDraftChange] = Field(default_factory=list)
    created_workflows: list[LeadBotDraftChange] = Field(default_factory=list)
    updated_workflows: list[LeadBotDraftChange] = Field(default_factory=list)
    deleted_workflows: list[LeadBotDraftChange] = Field(default_factory=list)
    unchanged_workflows: list[LeadBotDraftChange] = Field(default_factory=list)
    workflow_reviews: list[LeadBotWorkflowReview] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LeadBotDraftBundle(BaseModel):
    studio_name: str
    brief: str
    leadbot_response: str
    draft_source: Literal["deterministic", "model", "fallback"] = "deterministic"
    rationale: list[str] = Field(default_factory=list)
    conversation: list[LeadBotConversationTurn] = Field(default_factory=list)
    suggested_next_prompts: list[str] = Field(default_factory=list)
    suggested_agents: list[AgentBot] = Field(default_factory=list)
    suggested_workflows: list[WorkflowDefinition] = Field(default_factory=list)
    manifest_diff: LeadBotDraftDiff = Field(default_factory=LeadBotDraftDiff)


class LeadBotDraftRequest(BaseModel):
    brief: str
    operator: str | None = None
    prefer_model: bool = True
    conversation: list[LeadBotConversationTurn] = Field(default_factory=list)
    current_draft: dict[str, Any] | None = None


class LeadBotDraftApplyRequest(BaseModel):
    draft: LeadBotDraftBundle
    replace_existing: bool = False
    sync_removed_entities: bool = False


class LeadBotDraftApplyResult(BaseModel):
    created_agents: list[str] = Field(default_factory=list)
    updated_agents: list[str] = Field(default_factory=list)
    deleted_agents: list[str] = Field(default_factory=list)
    created_workflows: list[str] = Field(default_factory=list)
    updated_workflows: list[str] = Field(default_factory=list)
    deleted_workflows: list[str] = Field(default_factory=list)


class LeadBotExecutionRequest(LeadBotDraftRequest):
    auto_apply: bool = False
    replace_existing: bool = True
    sync_removed_entities: bool = True


class LeadBotExecutionResult(BaseModel):
    draft: LeadBotDraftBundle
    applied: bool = False
    apply_result: LeadBotDraftApplyResult | None = None


ProposalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "revision_requested",
    "applied",
]


class LeadBotProposalRecord(BaseModel):
    proposal_id: str
    status: ProposalStatus = "pending"
    brief: str
    draft: LeadBotDraftBundle
    operator: str | None = None
    reviewer_note: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadBotProposalCreateRequest(LeadBotDraftRequest):
    title: str | None = None


class LeadBotProposalActionRequest(BaseModel):
    action: Literal["approve", "reject", "revise"]
    note: str | None = None
    replace_existing: bool = True
    sync_removed_entities: bool = True


class LeadBotProposalActionResult(BaseModel):
    proposal: LeadBotProposalRecord
    apply_result: LeadBotDraftApplyResult | None = None


class StudioMetadata(BaseModel):
    studio_id: str
    studio_name: str
    description: str
    version: str = "0.1.0"


class StudioDefaults(BaseModel):
    timezone: str = "Asia/Shanghai"
    openclaw_home: str = "~/.openclaw"
    default_model: str = "gpt-5.4"
    default_channel: str = "telegram"


class StudioManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: StudioMetadata
    defaults: StudioDefaults = Field(default_factory=StudioDefaults)
    lead_bot: LeadBot
    agents: list[AgentBot]
    workflows: list[WorkflowDefinition]

    @model_validator(mode="after")
    def validate_manifest(self) -> "StudioManifest":
        agent_ids = {agent.id for agent in self.agents}
        if len(agent_ids) != len(self.agents):
            raise ValueError("Agent ids must be unique.")
        if self.lead_bot.id in agent_ids:
            raise ValueError("LeadBot id must not duplicate a specialist agent id.")

        known_ids = agent_ids | {self.lead_bot.id}
        unknown_managed = sorted(set(self.lead_bot.manages_agents) - agent_ids)
        if unknown_managed:
            raise ValueError(
                f"LeadBot manages unknown agents: {', '.join(unknown_managed)}."
            )

        workflow_ids = {workflow.id for workflow in self.workflows}
        if len(workflow_ids) != len(self.workflows):
            raise ValueError("Workflow ids must be unique.")

        missing_workflows = sorted(set(self.lead_bot.workflow_ids) - workflow_ids)
        if missing_workflows:
            raise ValueError(
                f"LeadBot references unknown workflows: {', '.join(missing_workflows)}."
            )

        for workflow in self.workflows:
            if workflow.lead_agent_id != self.lead_bot.id:
                raise ValueError(
                    f"Workflow '{workflow.id}' must be owned by lead bot '{self.lead_bot.id}'."
                )
            participant_ids = {participant.agent_id for participant in workflow.participants}
            if self.lead_bot.id not in participant_ids:
                raise ValueError(
                    f"Workflow '{workflow.id}' must include the LeadBot as a participant."
                )
            unknown_participants = sorted(participant_ids - known_ids)
            if unknown_participants:
                raise ValueError(
                    f"Workflow '{workflow.id}' has unknown participants: "
                    f"{', '.join(unknown_participants)}."
                )

            step_ids = {step.id for step in workflow.steps}
            if len(step_ids) != len(workflow.steps):
                raise ValueError(f"Workflow '{workflow.id}' contains duplicate step ids.")

            for step in workflow.steps:
                if step.owner_agent_id not in participant_ids:
                    raise ValueError(
                        f"Workflow '{workflow.id}' step '{step.id}' owner "
                        f"'{step.owner_agent_id}' is not a participant."
                    )
                unknown_dependencies = sorted(set(step.depends_on) - step_ids)
                if unknown_dependencies:
                    raise ValueError(
                        f"Workflow '{workflow.id}' step '{step.id}' depends on unknown steps: "
                        f"{', '.join(unknown_dependencies)}."
                    )
                unknown_handoffs = sorted(set(step.handoff_to) - participant_ids)
                if unknown_handoffs:
                    raise ValueError(
                        f"Workflow '{workflow.id}' step '{step.id}' hands off to unknown "
                        f"participants: {', '.join(unknown_handoffs)}."
                    )

        return self


class WorkflowRunRequest(BaseModel):
    operator: str | None = None
    input_summary: str = "Operator-triggered workflow dry run."
    requested_outputs: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class WorkflowRunStepPreview(BaseModel):
    step_id: str
    name: str
    owner_agent_id: str
    owner_display_name: str
    status: StepStatus
    depends_on: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    approval_required: bool = False
    handoff_to: list[str] = Field(default_factory=list)
    notes: str | None = None


class WorkflowRunPreview(BaseModel):
    run_id: str
    mode: Literal["dry_run"] = "dry_run"
    workflow_id: str
    workflow_name: str
    lead_agent_id: str
    operator: str | None = None
    status: RunStatus = "previewed"
    input_summary: str
    requested_outputs: list[str] = Field(default_factory=list)
    created_at: datetime
    next_steps: list[str] = Field(default_factory=list)
    blocked_steps: list[str] = Field(default_factory=list)
    approval_steps: list[str] = Field(default_factory=list)
    step_previews: list[WorkflowRunStepPreview] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class WorkflowRunUpdateRequest(BaseModel):
    status: RunStatus
    note: str | None = None
    operator: str | None = None


class WorkflowRunStepUpdateRequest(BaseModel):
    status: StepStatus
    note: str | None = None
