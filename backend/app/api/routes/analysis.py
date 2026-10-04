from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.api.dependencies import CurrentUser, Database
from app.schemas.analysis import AnalysisPage, AnalysisRequest, AnalysisResponse, FeedbackRequest
from app.services import analysis
from app.services.reports import get_report

router = APIRouter(prefix="/reports/{report_id}", tags=["AI second opinion"])


@router.post("/analysis", response_model=AnalysisResponse, status_code=201)
def request_analysis(
    report_id: str,
    data: AnalysisRequest,
    db: Database,
    user: CurrentUser,
    request: Request,
    response: Response,
):
    state = request.app.state
    item, created = analysis.run_analysis(
        db, report_id, user, data, state.settings, state.photo_storage, state.ai_provider, state.ai_limiter
    )
    response.status_code = 201 if created else 200
    report = get_report(db, report_id, user)
    return analysis.analysis_response(db, item, report)


@router.get("/analyses", response_model=AnalysisPage)
def list_analyses(
    report_id: str,
    db: Database,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    report = get_report(db, report_id, user)
    return analysis.list_analyses(db, report, user, limit, offset)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(report_id: str, analysis_id: str, db: Database, user: CurrentUser):
    report = get_report(db, report_id, user)
    item = analysis.get_analysis(db, report_id, analysis_id)
    return analysis.analysis_response(db, item, report, is_owner=report.contributor_id == user.id)


@router.post("/analyses/{analysis_id}/feedback", response_model=AnalysisResponse)
def record_feedback(report_id: str, analysis_id: str, data: FeedbackRequest, db: Database, user: CurrentUser):
    report = get_report(db, report_id, user)
    if report.contributor_id != user.id:
        raise HTTPException(404, "Report not found")
    item = analysis.get_analysis(db, report_id, analysis_id)
    item = analysis.record_feedback(db, report, item, data)
    return analysis.analysis_response(db, item, report)
