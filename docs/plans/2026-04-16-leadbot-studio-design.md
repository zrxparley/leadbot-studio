# LeadBot Studio on OpenClaw

## Goal

Build a GitHub-ready framework that lets one `LeadBot` coordinate multiple OpenClaw agents as a reusable "studio" operating model.

The project should let a builder:

- define a named LeadBot with governance rules and workflow ownership
- register many specialized AgentBots with custom identity, avatar, workspace, skills, notes, and tool policy
- define multiple workflows/flows with different teams, handoffs, and outputs
- export an OpenClaw-aligned configuration starter instead of replacing OpenClaw's gateway routing model

This keeps the architecture aligned with OpenClaw's official model:

- OpenClaw Gateway remains the source of truth for routing and bindings
- each `agentId` stays isolated with its own workspace, sessions, and auth state
- LeadBot becomes a control-plane abstraction for orchestration, workflow planning, and governance

## Product Shape

The framework is a FastAPI control plane called `LeadBot Studio`.

It manages four first-class concepts:

1. `StudioManifest`
   - the top-level studio definition
   - includes metadata, defaults, governance, lead bot, specialist agents, and workflows

2. `AgentBot`
   - a specialist OpenClaw-compatible agent profile
   - stores identity, role, workspace, capabilities, skills, debug notes, tool policy, and channel bindings

3. `LeadBot`
   - a specialized `AgentBot` with additional coordination responsibility
   - owns workflow selection, escalation rules, human approval policy, and agent-to-agent collaboration policy

4. `Workflow`
   - a reusable operating flow
   - contains participants, ordered steps, approval checkpoints, handoff outputs, and delivery targets

## Architecture

### 1. Configuration-first control plane

The first implementation is config-first, backed by a JSON manifest file.

Why:

- aligns well with OpenClaw's existing workspace/config mentality
- keeps the MVP publishable without introducing migration complexity
- makes GitHub diffs readable for studio edits
- still allows a future DB-backed UI or versioned control room

### 2. Workflow compilation, not runtime replacement

LeadBot Studio should not pretend to be OpenClaw's internal runtime.

Instead it should:

- validate workflow definitions
- compile a workflow into a dispatch plan
- export OpenClaw-compatible agent and binding snippets
- generate handoff packets and execution previews for humans or higher-level automation

This avoids fighting the platform while still delivering strong orchestration ergonomics.

### 3. Governance by design

Each LeadBot and AgentBot definition includes:

- allowed/denied tools
- sandbox hints
- approval mode
- escalation rules
- hard blocks
- audit notes

This mirrors OpenClaw's delegate architecture and keeps the project suitable for organization-style deployments.

## Core API Surface

- `GET /studio/manifest`
  - return the active studio manifest
- `PUT /studio/manifest`
  - replace the active studio manifest after validation
- `GET /studio/summary`
  - quick summary for control room dashboards
- `GET /studio/agents`
  - list LeadBot + specialist bots
- `GET /studio/workflows`
  - list defined flows
- `GET /studio/workflows/{workflow_id}/plan`
  - compile a dispatch/handoff preview
- `GET /studio/openclaw/export`
  - export an OpenClaw-aligned starter config bundle

## OpenClaw Export Model

The exporter should produce:

- `agents.list`
  - one entry per LeadBot or AgentBot
- `bindings`
  - channel/topic/account routing starters derived from bot bindings
- `coordination`
  - LeadBot-centric collaboration metadata for A2A allowlists, workflow ownership, and approval rules
- `workflows`
  - app-level workflow definitions preserved for external tooling

Important: `coordination` is a LeadBot Studio concept, not an OpenClaw core config primitive. It is included so builders can keep orchestration metadata beside the raw OpenClaw config starter.

## Example Use Cases

### Build Studio

- LeadBot: `studio-lead`
- Agents: `designer`, `coder`, `qa`, `publisher`
- Flow: spec -> implement -> test -> publish

### Research Studio

- LeadBot: `research-lead`
- Agents: `searcher`, `analyst`, `writer`
- Flow: collect -> analyze -> synthesize -> publish

### Content Studio

- LeadBot: `content-lead`
- Agents: `idea-bot`, `draft-bot`, `editor-bot`, `ops-bot`
- Flow: ideation -> draft -> review -> distribute

## Risks and Trade-offs

### Why not make LeadBot the only gateway?

Because official OpenClaw routing is gateway/binding based. Trying to force all ingress through a single visible bot would make the product less native and would create fragile runtime assumptions.

### Why not execute real inter-agent calls in the MVP?

Real execution depends on the user's OpenClaw runtime, channels, auth, tools, and session topology. A publishable framework should first make those definitions structured, reviewable, and exportable.

### Why JSON manifest instead of database tables?

This makes the framework easier to inspect, fork, version, and publish today. The service layer is intentionally written so a DB-backed store can replace file persistence later.

## Delivery Scope for This Iteration

- design doc
- new `app.studio` module with schemas and manifest service
- workflow plan compiler
- OpenClaw export builder
- sample studio manifest with LeadBot + multiple AgentBots
- FastAPI endpoints
- tests for validation and export behavior
- README repositioned around LeadBot Studio
