from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(tags=["leadbot-console"])


@router.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/studio/console", status_code=307)


@router.get("/studio/console", response_class=HTMLResponse, include_in_schema=False)
def studio_console() -> str:
    return CONSOLE_HTML


CONSOLE_HTML = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>LeadBot Studio Console</title>
    <style>
      :root {
        --bg: #f5f1e8;
        --ink: #16120f;
        --muted: #6d6358;
        --panel: rgba(255, 252, 246, 0.88);
        --panel-strong: #fffaf1;
        --line: rgba(22, 18, 15, 0.12);
        --accent: #bf5a36;
        --accent-soft: rgba(191, 90, 54, 0.14);
        --accent-cool: #2c6e73;
        --success: #357a5c;
        --warning: #a06a1b;
        --danger: #a13a35;
        --shadow: 0 24px 80px rgba(46, 27, 14, 0.12);
      }

      * {
        box-sizing: border-box;
      }

      html,
      body {
        margin: 0;
        min-height: 100%;
        background:
          radial-gradient(circle at top left, rgba(191, 90, 54, 0.16), transparent 28%),
          radial-gradient(circle at top right, rgba(44, 110, 115, 0.18), transparent 26%),
          linear-gradient(180deg, #f8f4ec 0%, #efe6d7 100%);
        color: var(--ink);
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      }

      body::before {
        content: "";
        position: fixed;
        inset: 0;
        background-image:
          linear-gradient(rgba(22, 18, 15, 0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(22, 18, 15, 0.03) 1px, transparent 1px);
        background-size: 24px 24px;
        opacity: 0.35;
        pointer-events: none;
      }

      .shell {
        position: relative;
        z-index: 1;
        max-width: 1480px;
        margin: 0 auto;
        padding: 28px;
      }

      .hero {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 22px;
        align-items: stretch;
        margin-bottom: 22px;
      }

      .hero-panel,
      .panel {
        position: relative;
        overflow: hidden;
        background: var(--panel);
        border: 1px solid rgba(255, 255, 255, 0.56);
        box-shadow: var(--shadow);
        backdrop-filter: blur(20px);
      }

      .hero-panel {
        border-radius: 28px;
        padding: 28px;
      }

      .hero-panel::after,
      .panel::after {
        content: "";
        position: absolute;
        inset: 0;
        border-radius: inherit;
        border: 1px solid rgba(255, 255, 255, 0.36);
        pointer-events: none;
      }

      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 7px 12px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.64);
        color: var(--accent);
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }

      h1,
      h2,
      h3 {
        margin: 0;
        font-weight: 600;
      }

      h1 {
        margin-top: 18px;
        max-width: 12ch;
        font-size: clamp(2.8rem, 5vw, 5.2rem);
        line-height: 0.92;
      }

      .hero-copy {
        margin-top: 16px;
        max-width: 58ch;
        color: var(--muted);
        font-size: 1.02rem;
        line-height: 1.65;
      }

      .hero-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: 20px;
      }

      button,
      select,
      input,
      textarea {
        font: inherit;
      }

      button,
      .button {
        appearance: none;
        border: none;
        border-radius: 999px;
        padding: 12px 18px;
        background: var(--ink);
        color: #fff8f1;
        cursor: pointer;
        transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
      }

      button.secondary {
        background: rgba(22, 18, 15, 0.08);
        color: var(--ink);
      }

      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 24px rgba(22, 18, 15, 0.12);
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
        height: 100%;
      }

      .metric {
        border-radius: 20px;
        background: var(--panel-strong);
        border: 1px solid var(--line);
        padding: 18px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 132px;
      }

      .metric-label {
        color: var(--muted);
        font-size: 0.88rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .metric-value {
        margin-top: 16px;
        font-size: clamp(2rem, 3vw, 3rem);
        line-height: 1;
      }

      .metric-detail {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.94rem;
      }

      .layout {
        display: grid;
        grid-template-columns: 320px minmax(0, 1fr) 360px;
        gap: 18px;
      }

      .panel {
        border-radius: 24px;
        padding: 22px;
      }

      .panel-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 18px;
      }

      .panel-title {
        font-size: 1.1rem;
      }

      .panel-subtitle {
        color: var(--muted);
        font-size: 0.92rem;
        margin-top: 4px;
      }

      .stack {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .card {
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.58);
        padding: 16px;
        transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
      }

      .card:hover {
        transform: translateY(-1px);
        border-color: rgba(191, 90, 54, 0.26);
        background: rgba(255, 255, 255, 0.82);
      }

      .card.active {
        border-color: rgba(191, 90, 54, 0.52);
        background: linear-gradient(135deg, rgba(191, 90, 54, 0.14), rgba(255, 255, 255, 0.92));
      }

      .card h3 {
        font-size: 1rem;
      }

      .meta {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.55;
      }

      .pill-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }

      .pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 999px;
        padding: 6px 11px;
        background: rgba(22, 18, 15, 0.06);
        color: var(--ink);
        font-size: 0.8rem;
      }

      .pill.status-previewed,
      .pill.status-queued {
        background: rgba(44, 110, 115, 0.12);
        color: var(--accent-cool);
      }

      .pill.status-running {
        background: rgba(191, 90, 54, 0.14);
        color: var(--accent);
      }

      .pill.status-awaiting_approval,
      .pill.status-blocked {
        background: rgba(160, 106, 27, 0.14);
        color: var(--warning);
      }

      .pill.status-completed {
        background: rgba(53, 122, 92, 0.16);
        color: var(--success);
      }

      .pill.status-failed,
      .pill.status-cancelled {
        background: rgba(161, 58, 53, 0.16);
        color: var(--danger);
      }

      .detail-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
        gap: 16px;
      }

      .section {
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.58);
        padding: 16px;
      }

      .section + .section {
        margin-top: 14px;
      }

      .section h3 {
        font-size: 0.96rem;
        margin-bottom: 12px;
      }

      .step {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 12px;
        align-items: start;
        padding: 12px 0;
        border-top: 1px solid rgba(22, 18, 15, 0.08);
      }

      .step:first-child {
        border-top: none;
        padding-top: 0;
      }

      .step-index {
        width: 34px;
        height: 34px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(22, 18, 15, 0.07);
        font-size: 0.9rem;
      }

      .step-title {
        font-size: 0.98rem;
      }

      .step-copy {
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.55;
      }

      .timeline {
        position: relative;
        padding-left: 18px;
      }

      .timeline::before {
        content: "";
        position: absolute;
        left: 4px;
        top: 8px;
        bottom: 8px;
        width: 2px;
        background: rgba(22, 18, 15, 0.12);
      }

      .event {
        position: relative;
        padding: 0 0 16px 18px;
      }

      .event::before {
        content: "";
        position: absolute;
        left: -1px;
        top: 6px;
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--accent);
        box-shadow: 0 0 0 4px rgba(191, 90, 54, 0.12);
      }

      .event-type {
        font-size: 0.86rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--accent);
      }

      .event-body {
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.55;
      }

      .muted {
        color: var(--muted);
      }

      .empty {
        padding: 18px;
        border-radius: 18px;
        border: 1px dashed rgba(22, 18, 15, 0.18);
        color: var(--muted);
        text-align: center;
      }

      .run-controls {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .run-controls textarea {
        width: 100%;
        min-height: 108px;
        resize: vertical;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.72);
        padding: 14px;
        color: var(--ink);
      }

      .control-stack {
        display: flex;
        flex-direction: column;
        gap: 14px;
        margin-top: 14px;
      }

      .control-card {
        border-radius: 18px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.52);
        padding: 14px;
      }

      .control-title {
        font-size: 0.9rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }

      .control-meta {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.5;
      }

      .inline-form {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 12px;
      }

      .inline-form select,
      .inline-form input {
        min-height: 44px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.78);
        padding: 0 14px;
        color: var(--ink);
      }

      .inline-form select {
        min-width: 190px;
      }

      .inline-form input {
        flex: 1 1 220px;
      }

      .inline-form button:disabled,
      .inline-form select:disabled,
      .inline-form input:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }

      .split {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .statusline {
        min-height: 24px;
        color: var(--muted);
        font-size: 0.92rem;
      }

      .loading {
        opacity: 0.6;
      }

      .timestamp {
        display: inline-block;
        margin-top: 6px;
        color: var(--muted);
        font-size: 0.82rem;
      }

      @media (max-width: 1180px) {
        .hero,
        .layout,
        .detail-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <div class="shell">
      <section class="hero">
        <div class="hero-panel">
          <div class="eyebrow">LeadBot Studio Console</div>
          <h1>Operate the studio, not just the API.</h1>
          <p class="hero-copy">
            This control room gives one operator-facing surface for studio structure,
            workflow orchestration, run state, and event history. It is intentionally
            wired straight to the current FastAPI endpoints so we can evolve product behavior
            and UI together.
          </p>
          <div class="hero-actions">
            <button id="refreshButton">Refresh Studio</button>
            <button class="secondary" id="openDocsButton" type="button">Open API Docs</button>
          </div>
        </div>
        <div class="hero-panel">
          <div id="summaryGrid" class="summary-grid"></div>
        </div>
      </section>

      <section class="layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Agents</h2>
              <div class="panel-subtitle">LeadBot plus the current studio roster.</div>
            </div>
          </div>
          <div id="agentsList" class="stack"></div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Workflow Control</h2>
              <div class="panel-subtitle">Select a workflow, review its structure, then create a run.</div>
            </div>
          </div>
          <div class="detail-grid">
            <div>
              <div id="workflowList" class="stack"></div>
            </div>
            <div>
              <div class="section">
                <h3>Quick Run</h3>
                <div class="run-controls">
                  <textarea id="runInput" placeholder="Describe the operator intent for the next run."></textarea>
                  <div class="split">
                    <button id="createRunButton" type="button">Create Run</button>
                    <span id="runCreateStatus" class="statusline"></span>
                  </div>
                </div>
              </div>
              <div id="workflowMeta" class="section"></div>
            </div>
          </div>
          <div class="section">
            <h3>Workflow Steps</h3>
            <div id="workflowSteps"></div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">Runs & Events</h2>
              <div class="panel-subtitle">Live execution history and audit trail.</div>
            </div>
          </div>
          <div id="runsList" class="stack"></div>
          <div class="section">
            <div class="split">
              <h3>Selected Run</h3>
              <span id="runActionStatus" class="statusline"></span>
            </div>
            <div id="runMeta"></div>
          </div>
          <div class="section">
            <h3>Event Timeline</h3>
            <div id="eventsList" class="timeline"></div>
          </div>
        </div>
      </section>
    </div>

    <script>
      const state = {
        summary: null,
        agents: [],
        workflows: [],
        workflowPlans: new Map(),
        runs: [],
        selectedWorkflowId: null,
        selectedRunId: null,
      };

      const elements = {
        summaryGrid: document.getElementById("summaryGrid"),
        agentsList: document.getElementById("agentsList"),
        workflowList: document.getElementById("workflowList"),
        workflowMeta: document.getElementById("workflowMeta"),
        workflowSteps: document.getElementById("workflowSteps"),
        runsList: document.getElementById("runsList"),
        runMeta: document.getElementById("runMeta"),
        eventsList: document.getElementById("eventsList"),
        refreshButton: document.getElementById("refreshButton"),
        createRunButton: document.getElementById("createRunButton"),
        runCreateStatus: document.getElementById("runCreateStatus"),
        runInput: document.getElementById("runInput"),
        openDocsButton: document.getElementById("openDocsButton"),
        runActionStatus: document.getElementById("runActionStatus"),
      };

      const RUN_TRANSITIONS = {
        previewed: ["queued", "cancelled"],
        queued: ["running", "blocked", "cancelled"],
        running: ["awaiting_approval", "failed", "completed", "blocked", "cancelled"],
        awaiting_approval: ["running", "failed", "completed", "cancelled"],
        blocked: ["queued", "running", "cancelled"],
        failed: ["queued", "cancelled"],
        completed: [],
        cancelled: [],
      };

      const STEP_TRANSITIONS = {
        blocked: ["queued"],
        queued: ["running", "awaiting_approval", "completed", "failed"],
        running: ["awaiting_approval", "completed", "failed", "queued"],
        awaiting_approval: ["running", "completed", "failed"],
        failed: ["queued"],
        completed: [],
      };

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      async function fetchJson(url, options) {
        const response = await fetch(url, options);
        if (!response.ok) {
          let detail = `Request failed: ${response.status}`;
          try {
            const payload = await response.json();
            detail = payload.detail || JSON.stringify(payload);
          } catch (_error) {
            const text = await response.text();
            if (text) {
              detail = text;
            }
          }
          throw new Error(detail);
        }
        return response.json();
      }

      function humanizeStatus(value) {
        return String(value ?? "").replaceAll("_", " ");
      }

      function formatTimestamp(value) {
        if (!value) {
          return "Unknown time";
        }
        const timestamp = new Date(value);
        if (Number.isNaN(timestamp.getTime())) {
          return value;
        }
        return timestamp.toLocaleString();
      }

      function renderSummary() {
        if (!state.summary) {
          elements.summaryGrid.innerHTML = '<div class="empty">No studio summary yet.</div>';
          return;
        }
        const summary = state.summary;
        const metrics = [
          { label: "LeadBot", value: summary.lead_bot_id, detail: summary.studio_name },
          { label: "Agents", value: summary.agent_count, detail: `${summary.specialist_count} specialists active` },
          { label: "Workflows", value: summary.workflow_count, detail: `${summary.skill_count} skill bindings declared` },
          { label: "Channels", value: summary.channels.length || "0", detail: summary.channels.join(", ") || "No bindings configured" },
        ];
        elements.summaryGrid.innerHTML = metrics.map((metric) => `
          <article class="metric">
            <div class="metric-label">${escapeHtml(metric.label)}</div>
            <div class="metric-value">${escapeHtml(metric.value)}</div>
            <div class="metric-detail">${escapeHtml(metric.detail)}</div>
          </article>
        `).join("");
      }

      function renderAgents() {
        if (!state.agents.length) {
          elements.agentsList.innerHTML = '<div class="empty">No agents configured.</div>';
          return;
        }
        elements.agentsList.innerHTML = state.agents.map((agent) => `
          <article class="card">
            <h3>${escapeHtml(agent.identity.display_name)}</h3>
            <div class="meta">${escapeHtml(agent.role)}</div>
            <div class="pill-row">
              <span class="pill">${escapeHtml(agent.type)}</span>
              <span class="pill">${escapeHtml(agent.workspace.root)}</span>
            </div>
            <div class="meta">${escapeHtml(agent.objective)}</div>
          </article>
        `).join("");
      }

      function renderWorkflows() {
        if (!state.workflows.length) {
          elements.workflowList.innerHTML = '<div class="empty">No workflows available.</div>';
          elements.workflowMeta.innerHTML = '<div class="empty">Select a workflow to inspect it.</div>';
          elements.workflowSteps.innerHTML = '<div class="empty">No step data yet.</div>';
          return;
        }
        elements.workflowList.innerHTML = state.workflows.map((workflow) => `
          <button class="card ${workflow.id === state.selectedWorkflowId ? "active" : ""}" data-workflow-id="${escapeHtml(workflow.id)}" type="button">
            <h3>${escapeHtml(workflow.name)}</h3>
            <div class="meta">${escapeHtml(workflow.description)}</div>
            <div class="pill-row">
              ${(workflow.tags || []).map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}
            </div>
          </button>
        `).join("");

        const selectedPlan = state.workflowPlans.get(state.selectedWorkflowId);
        if (!selectedPlan) {
          elements.workflowMeta.innerHTML = '<div class="empty">Select a workflow to inspect it.</div>';
          elements.workflowSteps.innerHTML = '<div class="empty">No step data yet.</div>';
          return;
        }

        elements.workflowMeta.innerHTML = `
          <h3>${escapeHtml(selectedPlan.workflow_name)}</h3>
          <div class="meta">${escapeHtml(selectedPlan.trigger)}</div>
          <div class="pill-row">
            <span class="pill">Lead: ${escapeHtml(selectedPlan.lead_bot.display_name)}</span>
            <span class="pill">Approval: ${escapeHtml(selectedPlan.lead_bot.approval_mode)}</span>
          </div>
          <div class="meta">Outputs: ${escapeHtml(selectedPlan.outputs.join(", ") || "None declared")}</div>
        `;

        elements.workflowSteps.innerHTML = selectedPlan.steps.map((step) => `
          <div class="step">
            <div class="step-index">${escapeHtml(step.sequence)}</div>
            <div>
              <div class="step-title">${escapeHtml(step.name)}</div>
              <div class="step-copy">${escapeHtml(step.objective)}</div>
              <div class="pill-row">
                <span class="pill">${escapeHtml(step.owner_display_name)}</span>
                <span class="pill">${escapeHtml(step.type)}</span>
                ${step.approval_required ? '<span class="pill status-awaiting_approval">approval</span>' : ""}
              </div>
            </div>
            <div class="meta">${escapeHtml(step.deliverables.join(", ") || "No deliverables")}</div>
          </div>
        `).join("");

        elements.workflowList.querySelectorAll("[data-workflow-id]").forEach((button) => {
          button.addEventListener("click", async () => {
            const workflowId = button.getAttribute("data-workflow-id");
            await selectWorkflow(workflowId);
          });
        });
      }

      function renderRuns() {
        if (!state.runs.length) {
          elements.runsList.innerHTML = '<div class="empty">No runs yet. Create one from the workflow panel.</div>';
          renderRunDetail(null, []);
          return;
        }
        elements.runsList.innerHTML = state.runs.map((run) => `
          <button class="card ${run.run_id === state.selectedRunId ? "active" : ""}" data-run-id="${escapeHtml(run.run_id)}" type="button">
            <h3>${escapeHtml(run.workflow_name)}</h3>
            <div class="pill-row">
              <span class="pill status-${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
              <span class="pill">${escapeHtml(run.operator || "unassigned")}</span>
            </div>
            <div class="meta">${escapeHtml(run.input_summary)}</div>
          </button>
        `).join("");

        elements.runsList.querySelectorAll("[data-run-id]").forEach((button) => {
          button.addEventListener("click", () => {
            selectRun(button.getAttribute("data-run-id"));
          });
        });
      }

      async function selectWorkflow(workflowId, options = {}) {
        state.selectedWorkflowId = workflowId;
        if (!workflowId) {
          renderWorkflows();
          state.runs = [];
          state.selectedRunId = null;
          renderRuns();
          renderRunDetail(null, []);
          return;
        }
        if (!state.workflowPlans.has(workflowId)) {
          const plan = await fetchJson(`/studio/workflows/${workflowId}/plan`);
          state.workflowPlans.set(workflowId, plan);
        }
        renderWorkflows();
        if (options.loadRuns !== false) {
          await loadRuns();
        }
      }

      async function selectRun(runId) {
        if (!runId) {
          state.selectedRunId = null;
          renderRuns();
          renderRunDetail(null, []);
          return;
        }
        state.selectedRunId = runId;
        const [run, events] = await Promise.all([
          fetchJson(`/studio/runs/${runId}`),
          fetchJson(`/studio/runs/${runId}/events`),
        ]);
        renderRuns();
        renderRunDetail(run, events);
      }

      async function loadRuns() {
        const suffix = state.selectedWorkflowId ? `?workflow_id=${encodeURIComponent(state.selectedWorkflowId)}` : "";
        state.runs = await fetchJson(`/studio/runs${suffix}`);
        if (!state.selectedRunId && state.runs.length) {
          state.selectedRunId = state.runs[0].run_id;
        } else if (state.selectedRunId && !state.runs.some((run) => run.run_id === state.selectedRunId)) {
          state.selectedRunId = state.runs[0]?.run_id || null;
        }
        renderRuns();
        if (state.selectedRunId) {
          await selectRun(state.selectedRunId);
        } else {
          renderRunDetail(null, []);
        }
      }

      async function refreshAll() {
        document.body.classList.add("loading");
        elements.runCreateStatus.textContent = "Refreshing studio…";
        elements.runActionStatus.textContent = "";
        try {
          const [summary, agents, workflows] = await Promise.all([
            fetchJson("/studio/summary"),
            fetchJson("/studio/agents"),
            fetchJson("/studio/workflows"),
          ]);
          state.summary = summary;
          state.agents = agents;
          state.workflows = workflows;
          if (!state.selectedWorkflowId && workflows.length) {
            state.selectedWorkflowId = workflows[0].id;
          } else if (state.selectedWorkflowId && !workflows.some((item) => item.id === state.selectedWorkflowId)) {
            state.selectedWorkflowId = workflows[0]?.id || null;
          }
          renderSummary();
          renderAgents();
          await selectWorkflow(state.selectedWorkflowId, { loadRuns: true });
          elements.runCreateStatus.textContent = "Studio refreshed.";
        } catch (error) {
          console.error(error);
          elements.runCreateStatus.textContent = "Refresh failed. Check the console API.";
        } finally {
          document.body.classList.remove("loading");
        }
      }

      async function createRun() {
        if (!state.selectedWorkflowId) {
          elements.runCreateStatus.textContent = "Pick a workflow first.";
          return;
        }
        elements.runCreateStatus.textContent = "Creating run…";
        try {
          const input_summary = elements.runInput.value.trim() || "Operator-triggered run from the console.";
          const run = await fetchJson(`/studio/workflows/${state.selectedWorkflowId}/runs`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ operator: "console-operator", input_summary }),
          });
          state.selectedRunId = run.run_id;
          elements.runInput.value = "";
          await loadRuns();
          elements.runCreateStatus.textContent = "Run created.";
        } catch (error) {
          console.error(error);
          elements.runCreateStatus.textContent = "Run creation failed.";
        }
      }

      function renderRunDetail(run, events) {
        if (!run) {
          elements.runMeta.innerHTML = '<div class="empty">Select a run to inspect its current state.</div>';
          elements.eventsList.innerHTML = '<div class="empty">No events to display yet.</div>';
          return;
        }

        const runTransitions = RUN_TRANSITIONS[run.status] || [];
        const runIsTerminal = run.status === "completed" || run.status === "cancelled";

        elements.runMeta.innerHTML = `
          <div class="pill-row">
            <span class="pill status-${escapeHtml(run.status)}">${escapeHtml(humanizeStatus(run.status))}</span>
            <span class="pill">${escapeHtml(run.run_id)}</span>
            <span class="pill">${escapeHtml(run.operator || "unassigned")}</span>
          </div>
          <div class="meta" style="margin-top: 12px;">${escapeHtml(run.input_summary)}</div>
          <div class="meta">Next steps: ${escapeHtml((run.next_steps || []).join(", ") || "None")}</div>
          <div class="meta">Blocked: ${escapeHtml((run.blocked_steps || []).join(", ") || "None")}</div>
          <div class="meta">Approvals: ${escapeHtml((run.approval_steps || []).join(", ") || "None")}</div>
          <div class="control-stack">
            <div class="control-card">
              <div class="control-title">Run Controls</div>
              <div class="control-meta">
                Move the workflow run through the control plane without leaving the operator console.
              </div>
              ${
                runTransitions.length
                  ? `
                    <div class="inline-form">
                      <select id="runStatusSelect" aria-label="Run status">
                        ${runTransitions.map((status) => `
                          <option value="${escapeHtml(status)}">${escapeHtml(humanizeStatus(status))}</option>
                        `).join("")}
                      </select>
                      <input id="runStatusNote" type="text" placeholder="Optional run note" />
                      <button id="applyRunStatusButton" type="button">Apply Run Status</button>
                    </div>
                  `
                  : `<div class="control-meta">${runIsTerminal ? "This run is terminal and no longer accepts state changes." : "No run-level transitions are available right now."}</div>`
              }
            </div>
            <div class="control-card">
              <div class="control-title">Step Controls</div>
              <div class="control-meta">
                Advance specialist work one step at a time. Dependency blocking is still enforced by the backend.
              </div>
              ${
                (run.step_previews || []).map((step, index) => {
                  const transitions = runIsTerminal ? [] : (STEP_TRANSITIONS[step.status] || []);
                  return `
                    <div class="step">
                      <div class="step-index">${escapeHtml(index + 1)}</div>
                      <div>
                        <div class="step-title">${escapeHtml(step.name)}</div>
                        <div class="step-copy">
                          ${escapeHtml(step.owner_display_name)} owns this step.
                          ${step.blockers?.length ? ` Blocked by ${escapeHtml(step.blockers.join(", "))}.` : ""}
                          ${step.notes ? ` Latest note: ${escapeHtml(step.notes)}` : ""}
                        </div>
                        <div class="pill-row">
                          <span class="pill status-${escapeHtml(step.status)}">${escapeHtml(humanizeStatus(step.status))}</span>
                          <span class="pill">${escapeHtml(step.owner_agent_id)}</span>
                          ${step.approval_required ? '<span class="pill status-awaiting_approval">approval gate</span>' : ""}
                        </div>
                        ${
                          transitions.length
                            ? `
                              <div class="inline-form">
                                <select data-step-select="${escapeHtml(step.step_id)}" aria-label="Step status">
                                  ${transitions.map((status) => `
                                    <option value="${escapeHtml(status)}">${escapeHtml(humanizeStatus(status))}</option>
                                  `).join("")}
                                </select>
                                <input data-step-note="${escapeHtml(step.step_id)}" type="text" placeholder="Optional step note" />
                                <button data-step-apply="${escapeHtml(step.step_id)}" type="button">Update Step</button>
                              </div>
                            `
                            : `<div class="control-meta">${runIsTerminal ? "Run is terminal, so step controls are locked." : "This step is already terminal."}</div>`
                        }
                      </div>
                      <div class="meta">${escapeHtml((step.deliverables || []).join(", ") || "No deliverables")}</div>
                    </div>
                  `;
                }).join("")
              }
            </div>
          </div>
        `;

        const runActionButton = document.getElementById("applyRunStatusButton");
        if (runActionButton) {
          runActionButton.addEventListener("click", applyRunStatus);
        }
        elements.runMeta.querySelectorAll("[data-step-apply]").forEach((button) => {
          button.addEventListener("click", () => {
            const stepId = button.getAttribute("data-step-apply");
            applyStepStatus(stepId);
          });
        });

        if (!events.length) {
          elements.eventsList.innerHTML = '<div class="empty">No audit events recorded yet.</div>';
          return;
        }

        elements.eventsList.innerHTML = events.map((event) => `
          <div class="event">
            <div class="event-type">${escapeHtml(event.event_type)}</div>
            <div class="event-body">
              ${escapeHtml(event.target_kind)} ${escapeHtml(event.target_id || "")}
              ${event.from_status || event.to_status ? `• ${escapeHtml(humanizeStatus(event.from_status || "none"))} → ${escapeHtml(humanizeStatus(event.to_status || "none"))}` : ""}
              ${event.note ? `<br />${escapeHtml(event.note)}` : ""}
              ${event.actor ? `<br />Actor: ${escapeHtml(event.actor)}` : ""}
              <span class="timestamp">${escapeHtml(formatTimestamp(event.created_at))}</span>
            </div>
          </div>
        `).join("");
      }

      async function applyRunStatus() {
        if (!state.selectedRunId) {
          elements.runActionStatus.textContent = "Pick a run first.";
          return;
        }
        const statusSelect = document.getElementById("runStatusSelect");
        const noteInput = document.getElementById("runStatusNote");
        if (!statusSelect) {
          elements.runActionStatus.textContent = "No run transition available.";
          return;
        }
        elements.runActionStatus.textContent = "Updating run…";
        try {
          await fetchJson(`/studio/runs/${state.selectedRunId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              status: statusSelect.value,
              note: noteInput?.value?.trim() || null,
              operator: "console-operator",
            }),
          });
          await loadRuns();
          elements.runActionStatus.textContent = `Run moved to ${humanizeStatus(statusSelect.value)}.`;
        } catch (error) {
          console.error(error);
          elements.runActionStatus.textContent = error.message || "Run update failed.";
        }
      }

      async function applyStepStatus(stepId) {
        if (!state.selectedRunId || !stepId) {
          elements.runActionStatus.textContent = "Pick a run and step first.";
          return;
        }
        const statusSelect = elements.runMeta.querySelector(`[data-step-select="${CSS.escape(stepId)}"]`);
        const noteInput = elements.runMeta.querySelector(`[data-step-note="${CSS.escape(stepId)}"]`);
        if (!statusSelect) {
          elements.runActionStatus.textContent = "No step transition available.";
          return;
        }
        elements.runActionStatus.textContent = `Updating step ${stepId}…`;
        try {
          await fetchJson(`/studio/runs/${state.selectedRunId}/steps/${stepId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              status: statusSelect.value,
              note: noteInput?.value?.trim() || null,
            }),
          });
          await loadRuns();
          elements.runActionStatus.textContent = `Step ${stepId} moved to ${humanizeStatus(statusSelect.value)}.`;
        } catch (error) {
          console.error(error);
          elements.runActionStatus.textContent = error.message || "Step update failed.";
        }
      }

      elements.refreshButton.addEventListener("click", refreshAll);
      elements.createRunButton.addEventListener("click", createRun);
      elements.openDocsButton.addEventListener("click", () => {
        window.open("/docs", "_blank", "noopener,noreferrer");
      });

      refreshAll();
    </script>
  </body>
</html>
"""
