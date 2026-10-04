from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.models.assessment import Assessment
from app.models.report import Report, ReportStatus
from app.models.review import Review, ReviewCase


def review_report(db, report, user, data):
    if report.contributor_id == user.id:
        raise HTTPException(403, "You cannot review your own report")
    if report.status != ReportStatus.submitted:
        raise HTTPException(409, "Only submitted reports can be reviewed")
    existing = db.scalar(select(Review).where(Review.request_id == str(data.request_id)))
    if existing:
        if (
            existing.report_id == report.id
            and existing.reviewer_id == user.id
            and existing.assessment_id == str(data.assessment_id)
            and existing.decision == data.decision
            and existing.reason == data.reason
        ):
            return existing
        raise HTTPException(409, "Review request_id has already been used")
    case = db.get(ReviewCase, report.id)
    if not case:
        raise HTTPException(409, "Assess the report before reviewing it")
    if case.status != "pending":
        raise HTTPException(409, "This report already has a final expert decision")
    if case.assessment_id != str(data.assessment_id):
        raise HTTPException(409, "Assessment has changed. Read the current assessment before reviewing")
    item = Review(
        report_id=report.id,
        assessment_id=case.assessment_id,
        reviewer_id=user.id,
        request_id=str(data.request_id),
        decision=data.decision,
        reason=data.reason,
    )
    db.add(item)
    case.status = data.decision
    try:
        db.commit()
    except (IntegrityError, StaleDataError) as exc:
        db.rollback()
        raise HTTPException(409, "Another reviewer already changed this report. Reload the review.") from exc
    db.refresh(item)
    return item


def review_queue(db, user, status, include_optional, synthetic, limit, offset):
    query = (
        select(ReviewCase, Report, Assessment)
        .join(Report, Report.id == ReviewCase.report_id)
        .join(Assessment, Assessment.id == ReviewCase.assessment_id)
        .where(Report.contributor_id != user.id, ReviewCase.status == status)
    )
    if not include_optional and status == "pending":
        query = query.where(Assessment.requires_review.is_(True))
    if synthetic is not None:
        query = query.where(Report.is_synthetic == synthetic)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(Assessment.score, ReviewCase.created_at, Report.id).offset(offset).limit(limit)
    ).all()
    items = [
        {
            "report_id": report.id,
            "site_id": report.site_id,
            "assessment_id": assessment.id,
            "score": assessment.score,
            "evidence_coverage": assessment.evidence_coverage,
            "requires_review": assessment.requires_review,
            "status": case.status,
            "is_synthetic": report.is_synthetic,
            "reasons": assessment.reasons,
        }
        for case, report, assessment in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}
