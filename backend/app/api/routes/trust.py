from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database, require_reviewer
from app.models.review import Review
from app.models.user import User
from app.schemas.trust import AssessmentResponse, ReviewQueuePage, ReviewRequest, ReviewResponse
from app.services import assessments, reviews
from app.services.reports import get_report

router = APIRouter(tags=["Trust and expert review"])
Reviewer = Annotated[User, Depends(require_reviewer)]


@router.post("/reports/{report_id}/assessment", response_model=AssessmentResponse)
def assess_report(report_id: str, db: Database, user: CurrentUser):
    report = get_report(db, report_id, user)
    assessment, case = assessments.assess_report(db, report)
    return assessments.assessment_response(assessment, case, report)


@router.get("/reports/{report_id}/assessment", response_model=AssessmentResponse)
def get_assessment(report_id: str, db: Database, user: CurrentUser):
    report = get_report(db, report_id, user)
    assessment, case = assessments.current_assessment(db, report.id)
    return assessments.assessment_response(assessment, case, report)


@router.get("/reviews", response_model=ReviewQueuePage)
def queue(
    db: Database,
    user: Reviewer,
    status: Literal["pending", "approved", "rejected"] = "pending",
    include_optional: bool = False,
    synthetic: bool | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return reviews.review_queue(db, user, status, include_optional, synthetic, limit, offset)


@router.post("/reports/{report_id}/reviews", response_model=ReviewResponse)
def review_report(report_id: str, data: ReviewRequest, db: Database, user: Reviewer):
    report = get_report(db, report_id, user)
    return reviews.review_report(db, report, user, data)


@router.get("/reports/{report_id}/review", response_model=ReviewResponse)
def get_review(report_id: str, db: Database, user: CurrentUser):
    get_report(db, report_id, user)
    item = db.scalar(select(Review).where(Review.report_id == report_id))
    if item is None:
        raise HTTPException(404, "No expert decision exists for this report")
    return item
