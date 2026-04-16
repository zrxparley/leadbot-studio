from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.studio.schemas import (
    AgentBot,
    StudioManifest,
    WorkflowDefinition,
    WorkflowRunRequest,
    WorkflowRunStepUpdateRequest,
    WorkflowRunUpdateRequest,
)
from app.studio.runtime import (
    WorkflowRunNotFoundError,
    WorkflowRunService,
    WorkflowRunTransitionError,
)
from app.studio.service import (
    AgentNotFoundError,
    EntityConflictError,
    EntityInUseError,
    StudioManifestService,
    WorkflowNotFoundError,
)

router = APIRouter(prefix="/studio", tags=["leadbot-studio"])
studio_service = StudioManifestService()


@router.get("/manifest")
def get_manifest() -> dict:
    return studio_service.load_manifest().model_dump(mode="json")


@router.put("/manifest")
def put_manifest(manifest: StudioManifest) -> dict:
    saved = studio_service.save_manifest(manifest)
    return saved.model_dump(mode="json")


@router.get("/summary")
def get_summary() -> dict:
    return studio_service.get_summary()


@router.get("/agents")
def list_agents() -> list[dict]:
    return [agent.model_dump(mode="json") for agent in studio_service.list_agents()]


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> dict:
    try:
        return studio_service.get_agent(agent_id).model_dump(mode="json")
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {exc}") from exc


@router.post("/agents")
def create_agent(agent: AgentBot) -> dict:
    try:
        return studio_service.create_agent(agent).model_dump(mode="json")
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/agents/{agent_id}")
def update_agent(agent_id: str, agent: AgentBot) -> dict:
    try:
        return studio_service.update_agent(agent_id, agent).model_dump(mode="json")
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {exc}") from exc
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str) -> dict:
    try:
        return studio_service.delete_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {exc}") from exc
    except EntityInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/workflows")
def list_workflows() -> list[dict]:
    return [workflow.model_dump(mode="json") for workflow in studio_service.list_workflows()]


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str) -> dict:
    try:
        return studio_service.get_workflow(workflow_id).model_dump(mode="json")
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.post("/workflows")
def create_workflow(workflow: WorkflowDefinition) -> dict:
    try:
        return studio_service.create_workflow(workflow).model_dump(mode="json")
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: str, workflow: WorkflowDefinition) -> dict:
    try:
        return studio_service.update_workflow(workflow_id, workflow).model_dump(mode="json")
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc
    except EntityConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str) -> dict:
    try:
        return studio_service.delete_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.get("/workflows/{workflow_id}/plan")
def get_workflow_plan(workflow_id: str) -> dict:
    try:
        return studio_service.get_workflow_plan(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.post("/workflows/{workflow_id}/dry-run")
def create_workflow_dry_run(workflow_id: str, request: WorkflowRunRequest) -> dict:
    try:
        return studio_service.create_workflow_dry_run(workflow_id, request).model_dump(mode="json")
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.post("/workflows/{workflow_id}/runs")
def create_workflow_run(
    workflow_id: str,
    request: WorkflowRunRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return WorkflowRunService(db, studio_service).create_run(workflow_id, request)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.get("/runs")
def list_workflow_runs(
    workflow_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict]:
    return WorkflowRunService(db, studio_service).list_runs(workflow_id=workflow_id)


@router.get("/runs/{run_id}")
def get_workflow_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return WorkflowRunService(db, studio_service).get_run(run_id)
    except WorkflowRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow run: {exc}") from exc


@router.get("/runs/{run_id}/events")
def list_workflow_run_events(run_id: str, db: Session = Depends(get_db)) -> list[dict]:
    try:
        return WorkflowRunService(db, studio_service).list_run_events(run_id)
    except WorkflowRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow run: {exc}") from exc


@router.patch("/runs/{run_id}")
def update_workflow_run(
    run_id: str,
    request: WorkflowRunUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return WorkflowRunService(db, studio_service).update_run(run_id, request)
    except WorkflowRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow run: {exc}") from exc
    except WorkflowRunTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/runs/{run_id}/steps/{step_id}")
def update_workflow_run_step(
    run_id: str,
    step_id: str,
    request: WorkflowRunStepUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return WorkflowRunService(db, studio_service).update_run_step(run_id, step_id, request)
    except WorkflowRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow run: {exc}") from exc
    except WorkflowRunTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/openclaw/export")
def get_openclaw_export() -> dict:
    return studio_service.export_openclaw_bundle()
