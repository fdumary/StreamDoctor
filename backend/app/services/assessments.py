from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.models.assessment import Assessment
from app.models.report import ReportStatus
from app.models.review import ReviewCase
from app.schemas.trust import AssessmentResponse
from app.services.trust_score import calculate_assessment


def current_assessment(db, report_id):
    case = db.get(ReviewCase, report_id)
    if case is None:
        raise HTTPException(404, "No assessment exists for this report")
    return db.get(Assessment, case.assessment_id), case


def assess_report(db, report):
    if report.status != ReportStatus.submitted:
        raise HTTPException(409, "Only submitted reports can be assessed")
    existing_case = db.get(ReviewCase, report.id)
    if existing_case and existing_case.status != "pending":
        return current_assessment(db, report.id)
    values = calculate_assessment(db, report)
    assessment = db.scalar(
        select(Assessment).where(
            Assessment.report_id == report.id, Assessment.evidence_digest == values["evidence_digest"]
        )
    )
    if assessment is None:
        assessment = Assessment(report_id=report.id, **values)
        db.add(assessment)
    try:
        db.flush()
        case = db.get(ReviewCase, report.id)
        if case is None:
            case = ReviewCase(report_id=report.id, assessment_id=assessment.id)
            db.add(case)
        elif case.status == "pending":
            case.assessment_id = assessment.id
        db.commit()
    except (IntegrityError, StaleDataError) as exc:
        db.rollback()
        raise HTTPException(409, "Assessment changed concurrently. Reload and try again.") from exc

    return current_assessment(db, report.id)


def assessment_response(assessment, case, report):
    values = {
        name: getattr(assessment, name)
        for name in AssessmentResponse.model_fields
        if name not in {"review_status", "expert_verified", "eligible_for_trusted_use", "is_synthetic"}
    }
    return AssessmentResponse(
        **values,
        review_status=case.status,
        expert_verified=case.status == "approved",
        eligible_for_trusted_use=case.status == "approved"
        or (case.status == "pending" and assessment.auto_eligible),
        is_synthetic=report.is_synthetic,
    )
