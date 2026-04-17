from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base
from app.studio.proposals import LeadBotProposalService
from app.studio.service import StudioManifestService


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return SessionLocal()


def test_proposal_can_be_created_and_approved(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    manifest_service = StudioManifestService(str(manifest_path))
    db = make_session()
    service = LeadBotProposalService(db, manifest_service)

    proposal = service.create_proposal(
        {
            "brief": "Create a launch studio with research and publishing.",
            "operator": "aha",
        }
    )
    assert proposal.status == "pending"

    result = service.act_on_proposal(
        proposal.proposal_id,
        {
            "action": "approve",
            "note": "Looks good.",
            "replace_existing": True,
            "sync_removed_entities": False,
        },
    )

    assert result.proposal.status == "applied"
    assert result.apply_result is not None


def test_proposal_can_be_rejected_or_marked_for_revision(tmp_path):
    manifest_path = tmp_path / "leadbot_studio_manifest.json"
    manifest_service = StudioManifestService(str(manifest_path))
    db = make_session()
    service = LeadBotProposalService(db, manifest_service)

    proposal = service.create_proposal({"brief": "Create a compact studio."})
    revised = service.act_on_proposal(
        proposal.proposal_id,
        {"action": "revise", "note": "Keep QA but remove publishing."},
    )
    assert revised.proposal.status == "revision_requested"
    assert revised.proposal.reviewer_note == "Keep QA but remove publishing."

    proposal_two = service.create_proposal({"brief": "Create another compact studio."})
    rejected = service.act_on_proposal(
        proposal_two.proposal_id,
        {"action": "reject", "note": "This is too broad."},
    )
    assert rejected.proposal.status == "rejected"
