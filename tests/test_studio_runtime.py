from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.studio.runtime import WorkflowRunNotFoundError, WorkflowRunService
from app.studio.schemas import WorkflowRunRequest
from app.studio.service import StudioManifestService


def _build_session(tmp_path) -> Session:
    database_path = tmp_path / "workflow_runs.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return factory()


def test_create_and_fetch_workflow_run(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    manifest_service = StudioManifestService(str(manifest_path))
    db = _build_session(tmp_path)

    try:
        service = WorkflowRunService(db, manifest_service)
        created = service.create_run(
            "build-delivery",
            WorkflowRunRequest(
                operator="aha",
                input_summary="Prepare a release run.",
                requested_outputs=["artifact", "verification report"],
            ),
        )

        fetched = service.get_run(created["run_id"])

        assert created["workflow_id"] == "build-delivery"
        assert created["status"] == "previewed"
        assert created["operator"] == "aha"
        assert fetched["run_id"] == created["run_id"]
        assert len(fetched["step_previews"]) == 4
    finally:
        db.close()


def test_list_runs_can_filter_by_workflow(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    manifest_service = StudioManifestService(str(manifest_path))
    db = _build_session(tmp_path)

    try:
        service = WorkflowRunService(db, manifest_service)
        service.create_run("build-delivery", WorkflowRunRequest(operator="aha"))
        service.create_run("research-briefing", WorkflowRunRequest(operator="aha"))

        filtered = service.list_runs(workflow_id="build-delivery")

        assert len(filtered) == 1
        assert filtered[0]["workflow_id"] == "build-delivery"
    finally:
        db.close()


def test_unknown_run_raises(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    manifest_service = StudioManifestService(str(manifest_path))
    db = _build_session(tmp_path)

    try:
        service = WorkflowRunService(db, manifest_service)
        try:
            service.get_run("missing-run")
            raise AssertionError("Expected WorkflowRunNotFoundError")
        except WorkflowRunNotFoundError:
            pass
    finally:
        db.close()
