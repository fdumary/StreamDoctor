from typing import Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, Database
from app.models.report import ReportStatus
from app.schemas.reports import ReportCreate, ReportPage, ReportPatch, ReportResponse
from app.services import reports

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("", response_model=ReportResponse, status_code=201)
def create_report(data: ReportCreate, db: Database, user: CurrentUser):
    return reports.report_response(db, reports.create_report(db, data, user))


@router.get("", response_model=ReportPage)
def list_reports(
    db: Database,
    user: CurrentUser,
    scope: Literal["mine", "submitted"] = "mine",
    status: ReportStatus | None = None,
    site_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return reports.list_reports(db, user, scope, status, site_id, limit, offset)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, db: Database, user: CurrentUser):
    return reports.report_response(db, reports.get_report(db, report_id, user))


@router.patch("/{report_id}", response_model=ReportResponse)
def patch_report(report_id: str, data: ReportPatch, db: Database, user: CurrentUser):
    report = reports.get_report(db, report_id, user, write=True)
    return reports.report_response(db, reports.patch_report(db, report, data))


@router.post("/{report_id}/submit", response_model=ReportResponse)
def submit_report(report_id: str, db: Database, user: CurrentUser):
    report = reports.get_report(db, report_id, user)
    if report.contributor_id != user.id:
        from fastapi import HTTPException

        raise HTTPException(404, "Report not found")
    return reports.report_response(db, reports.submit_report(db, report))
