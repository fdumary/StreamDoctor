from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models.ai_analysis import AIAnalysis
from app.models.assessment import Assessment
from app.models.photo import Photo
from app.models.report import Report, ReportStatus, utcnow
from app.models.review import Review, ReviewCase
from app.models.user import Role, User
from app.schemas.trust import ReviewRequest
from app.services.assessments import assess_report
from app.services.reviews import review_report
from app.services.trust_score import calculate_assessment


def new_user(db, role=Role.volunteer):
    user = User(
        email=f"{uuid4().hex}@example.com", display_name="Test", password_hash="unused-test-hash", role=role
    )
    db.add(user)
    db.flush()
    return user


def make_report(
    db, user, site_id, *, observed_at=None, submitted_at=None, synthetic=False, photo_hash=None, **fields
):
    values = dict(
        clarity="clear",
        smell="none",
        flow="slow",
        foam="none",
        visible_life="plants",
        water_color="colorless",
    )
    values.update(fields)
    report = Report(
        contributor_id=user.id,
        site_id=site_id,
        status=ReportStatus.submitted,
        observed_at=observed_at or utcnow(),
        submitted_at=submitted_at or utcnow(),
        is_synthetic=synthetic,
        submitted_snapshot=values.copy(),
        **values,
    )
    db.add(report)
    db.flush()
    digest = photo_hash or uuid4().hex * 2
    photo = Photo(
        report_id=report.id,
        storage_key=uuid4().hex + ".png",
        original_sha256=digest,
        stored_sha256=digest,
        byte_size=100,
        width=10,
        height=10,
        source="synthetic",
    )
    db.add(photo)
    db.commit()
    return report, photo


def approve(db, report, reviewer, decision="approved"):
    assessment, _ = assess_report(db, report)
    return review_report(
        db,
        report,
        reviewer,
        ReviewRequest(
            assessment_id=assessment.id,
            request_id=uuid4(),
            decision=decision,
            reason="Evidence reviewed independently for this test.",
        ),
    )


def add_ai(db, report, photo, original="clear", suggested="clear", is_mock=False):
    analysis = AIAnalysis(
        report_id=report.id,
        evidence_photo_id=photo.id,
        photo_sha256=photo.stored_sha256,
        request_id=str(uuid4()),
        status="succeeded",
        provider="mock" if is_mock else "http",
        is_mock=is_mock,
        input_report_version=report.version,
        input_snapshot={"clarity": original},
        lease_expires_at=1,
        result={"image_usable": True, "suggestions": [{"field": "clarity", "value": suggested}]},
    )
    db.add(analysis)
    db.commit()
    return analysis


def test_missing_evidence_is_not_a_penalty_or_automatic_trust(client, site):
    with client.app.state.session_factory() as db:
        report, _ = make_report(db, new_user(db), site["id"])
        result = calculate_assessment(db, report)
        assert result["score"] == 100
        assert result["evidence_coverage"] == 0.3
        assert result["requires_review"] and not result["auto_eligible"]
        assert result["components"]["contributor_history"]["score"] is None
        assert result["components"]["nearby_agreement"]["score"] is None


def test_original_before_ai_used_even_when_final_answers_agree(client, site):
    with client.app.state.session_factory() as db:
        report, photo = make_report(db, new_user(db), site["id"], clarity="cloudy")
        add_ai(db, report, photo, original="clear", suggested="cloudy")
        result = calculate_assessment(db, report)
        assert result["components"]["ai_photo_agreement"]["score"] == 0
        assert result["score"] == 42.86
        assert result["requires_review"]
        assert "photo_disagreement" in {flag["code"] for flag in result["flags"]}


def test_successful_live_agreement_can_be_eligible_but_mock_cannot(client, site):
    with client.app.state.session_factory() as db:
        report, photo = make_report(db, new_user(db), site["id"])
        analysis = add_ai(db, report, photo)
        result = calculate_assessment(db, report)
        assert result["score"] == 100 and result["evidence_coverage"] == 0.7
        assert result["auto_eligible"]
        analysis.is_mock = True
        db.commit()
        result = calculate_assessment(db, report)
        assert result["evidence_coverage"] == 0.3 and result["requires_review"]


def test_unusual_ph_is_flagged_without_declaring_report_false(client, site):
    with client.app.state.session_factory() as db:
        report, photo = make_report(db, new_user(db), site["id"], ph=11)
        add_ai(db, report, photo)
        result = calculate_assessment(db, report)
        assert result["score"] == 100
        assert result["requires_review"]
        flag = next(flag for flag in result["flags"] if flag["code"] == "unusual_ph")
        assert flag["penalty"] == 0


def test_context_conflict_and_unknowns_require_review(client, site):
    with client.app.state.session_factory() as db:
        report, _ = make_report(db, new_user(db), site["id"], flow="dry", foam="extensive", ph=7)
        result = calculate_assessment(db, report)
        assert result["components"]["plausibility"]["score"] == 80
        assert {"dry_with_foam", "dry_with_ph"}.issubset({f["code"] for f in result["flags"]})
        for field in ("clarity", "smell", "flow", "foam", "visible_life", "water_color"):
            setattr(report, field, "unknown")
        db.commit()
        assert "limited_observations" in {f["code"] for f in calculate_assessment(db, report)["flags"]}


def test_peers_need_independent_approved_contributors_and_unique_photos(client, site):
    with client.app.state.session_factory() as db:
        reviewer = new_user(db, Role.reviewer)
        owner = new_user(db)
        report, photo = make_report(db, owner, site["id"])
        peer_user = new_user(db)
        one, _ = make_report(db, peer_user, site["id"])
        approve(db, one, reviewer)
        again, _ = make_report(db, peer_user, site["id"])
        approve(db, again, reviewer)
        own, _ = make_report(db, owner, site["id"])
        approve(db, own, reviewer)
        duplicate, _ = make_report(db, new_user(db), site["id"], photo_hash=photo.stored_sha256)
        approve(db, duplicate, reviewer)
        result = calculate_assessment(db, report)
        assert not result["components"]["nearby_agreement"]["available"]
        assert "reused_photo" in {f["code"] for f in result["flags"]}
        second, _ = make_report(db, new_user(db), site["id"])
        approve(db, second, reviewer)
        result = calculate_assessment(db, report)
        assert result["components"]["nearby_agreement"]["score"] == 100
        assert result["components"]["nearby_agreement"]["details"]["independent_contributors"] == 2


def test_unreviewed_out_of_window_and_synthetic_peers_excluded(client, site):
    with client.app.state.session_factory() as db:
        reviewer = new_user(db, Role.reviewer)
        report, _ = make_report(db, new_user(db), site["id"])
        make_report(db, new_user(db), site["id"])
        synthetic, _ = make_report(db, new_user(db), site["id"], synthetic=True)
        approve(db, synthetic, reviewer)
        old, _ = make_report(db, new_user(db), site["id"], observed_at=utcnow() - timedelta(days=3))
        approve(db, old, reviewer)
        result = calculate_assessment(db, report)
        assert not result["components"]["nearby_agreement"]["available"]


def test_contributor_history_uses_independent_decisions_not_scores(client, site):
    with client.app.state.session_factory() as db:
        owner, reviewer = new_user(db), new_user(db, Role.reviewer)
        for index, decision in enumerate(["approved", "approved", "rejected"]):
            old, _ = make_report(db, owner, site["id"], submitted_at=utcnow() - timedelta(days=index + 1))
            approve(db, old, reviewer, decision)
        current, _ = make_report(db, owner, site["id"])
        result = calculate_assessment(db, current)
        assert result["components"]["contributor_history"]["score"] == 60
        assert result["components"]["contributor_history"]["details"]["reviewed_reports"] == 3


def test_rescoring_identical_evidence_reuses_immutable_snapshot(client, site):
    with client.app.state.session_factory() as db:
        report, _ = make_report(db, new_user(db), site["id"])
        first, _ = assess_report(db, report)
        second, _ = assess_report(db, report)
        assert first.id == second.id
        assert db.scalar(select(func.count()).select_from(Assessment)) == 1
        assert first.scoring_version == "streamtrust-1.0"
        assert first.policy["minimum_coverage"] == 0.7


def test_changed_evidence_creates_new_snapshot_and_stale_review_is_rejected(client, site):
    from fastapi import HTTPException

    with client.app.state.session_factory() as db:
        reviewer = new_user(db, Role.reviewer)
        report, _ = make_report(db, new_user(db), site["id"])
        old, _ = assess_report(db, report)
        for _ in range(2):
            peer, _ = make_report(db, new_user(db), site["id"])
            approve(db, peer, reviewer)
        new, _ = assess_report(db, report)
        assert new.id != old.id
        with pytest.raises(HTTPException) as error:
            review_report(
                db,
                report,
                reviewer,
                ReviewRequest(
                    assessment_id=old.id,
                    request_id=uuid4(),
                    decision="approved",
                    reason="A review based on stale evidence.",
                ),
            )
        assert error.value.status_code == 409
        assert db.get(Assessment, old.id) is not None


def test_competing_final_decisions_cannot_both_commit(client, site):
    from sqlalchemy.orm.exc import StaleDataError

    with client.app.state.session_factory() as db:
        reviewer = new_user(db, Role.reviewer)
        report, _ = make_report(db, new_user(db), site["id"])
        assess_report(db, report)
        with client.app.state.session_factory() as stale:
            old_case = stale.get(ReviewCase, report.id)
            approve(db, report, reviewer)
            old_case.status = "rejected"
            with pytest.raises(StaleDataError):
                stale.commit()
            stale.rollback()
        assert db.scalar(select(Review).where(Review.report_id == report.id)).decision == "approved"
