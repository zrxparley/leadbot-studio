from fastapi import APIRouter, HTTPException

from app.studio.schemas import StudioManifest
from app.studio.service import StudioManifestService, WorkflowNotFoundError

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


@router.get("/workflows")
def list_workflows() -> list[dict]:
    return [workflow.model_dump(mode="json") for workflow in studio_service.list_workflows()]


@router.get("/workflows/{workflow_id}/plan")
def get_workflow_plan(workflow_id: str) -> dict:
    try:
        return studio_service.get_workflow_plan(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc


@router.get("/openclaw/export")
def get_openclaw_export() -> dict:
    return studio_service.export_openclaw_bundle()
