# LeadBot Studio Roadmap

> This roadmap turns LeadBot Studio from a publishable foundation into a production-grade OpenClaw orchestration framework.

## Product Direction

LeadBot Studio should become the control plane for OpenClaw-native multi-agent workspaces.

The long-term shape is:

- OpenClaw handles runtime execution, session isolation, bindings, and channel delivery.
- LeadBot Studio handles studio design, agent governance, workflow modeling, approval policy, and operational visibility.
- Builders can define one LeadBot, many AgentBots, multiple workflows, and export or eventually execute those workflows against a real OpenClaw deployment.

## Guiding Principles

- Stay aligned with OpenClaw instead of re-implementing its runtime.
- Prefer configuration-first and Git-friendly workflows early.
- Add execution only after workflow definitions and governance are stable.
- Keep the LeadBot role explicit: planner, coordinator, approver, and operator-facing control surface.
- Treat auditability and approval paths as first-class features, not later add-ons.

## Phase 1: Foundation and Packaging

Status: in progress

Goal:
- Turn the existing control-plane foundation into a clean open-source starter.

Scope:
- stabilize the manifest schema
- keep the workflow plan compiler and OpenClaw exporter clean
- improve README and project positioning
- push the initial codebase to GitHub
- define the roadmap and milestone docs

Exit criteria:
- repository published
- docs explain architecture and local startup
- a default LeadBot Studio manifest works end-to-end through the API

## Phase 2: Studio Management Core

Goal:
- Make studio definitions easier to manage and safer to evolve.

Scope:
- add manifest versioning and upgrade helpers
- add richer validation errors with file-path style diagnostics
- add CRUD endpoints for agents and workflows instead of full-manifest replacement only
- add reusable workflow templates
- add role presets for common bots such as researcher, builder, reviewer, publisher, and operator

Suggested deliverables:
- `StudioManifestRepository` abstraction
- workflow template library
- schema migration/version field strategy
- API tests for create/update/delete flows

Exit criteria:
- users can modify one workflow or one agent without editing the whole manifest manually
- validation failures are easy to act on

## Phase 3: Execution Bridge to OpenClaw

Goal:
- Move from static planning/export into controlled runtime coordination.

Scope:
- define a dispatch adapter layer for OpenClaw runtime calls
- generate handoff packets from workflow steps
- add execution preview and dry-run output
- support LeadBot-driven state transitions for workflow runs
- model approval checkpoints explicitly during execution

Suggested deliverables:
- `WorkflowRun` domain model
- dispatch adapter interface
- dry-run execution endpoint
- handoff packet builder

Exit criteria:
- a workflow can be instantiated as a run
- steps can transition through queued, running, blocked, approved, failed, and done
- dry-run output is trustworthy enough for operator review

## Phase 4: Operator Console and Observability

Goal:
- Give human operators a real control room for the studio.

Scope:
- add a lightweight web UI or admin console
- visualize workflows, step status, and handoffs
- show agent capability cards and tool policies
- show audit logs, approvals, and escalation history
- expose run summaries and failure diagnostics

Suggested deliverables:
- dashboard for studio summary
- workflow run timeline view
- agent detail view
- audit/event log store

Exit criteria:
- operators can inspect current workflows and understand bottlenecks without reading raw JSON

## Phase 5: Skills, Plugins, and Integrations

Goal:
- Make LeadBot Studio extensible across teams and domains.

Scope:
- add skill catalogs and role presets
- support plugin-style adapters for delivery channels and external systems
- add starter packs for common studios such as coding, research, content, and operations
- add import/export helpers for OpenClaw workspace scaffolding

Suggested deliverables:
- starter manifests
- plugin adapter registry
- delivery adapters for GitHub, Feishu, Slack, Telegram, and email

Exit criteria:
- a new studio can be bootstrapped from a template with minimal manual editing

## Cross-Cutting Tracks

### Security and Governance

- define approval policies at workflow and step level
- add secrets boundaries and external action restrictions
- support audit retention and compliance-friendly exports

### Testing

- unit tests for schemas and compilation
- API tests for studio endpoints
- integration tests for export and dry-run execution
- fixture manifests for success and failure cases

### Documentation

- quickstart
- architecture guide
- workflow authoring guide
- agent design guide
- deployment guide

## Immediate Next Sprint

Recommended next implementation slice:

1. improve manifest lifecycle with repository abstraction and clearer validation messages
2. add workflow CRUD endpoints
3. introduce a `WorkflowRun` read model and a dry-run endpoint
4. add API tests for the new lifecycle

Why this slice:
- it keeps us in the control-plane layer
- it raises product quality without overcommitting to runtime internals too early
- it sets up the future execution bridge cleanly

## Definition of “Good Enough” for v0.2

LeadBot Studio v0.2 should let a user:

- create a studio with one LeadBot and several AgentBots
- define workflows safely through the API
- preview an execution plan
- export OpenClaw-aligned configuration
- inspect validation and workflow structure clearly

That is the right point to begin the runtime dispatch bridge.
