from datetime import timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.models.photo import Photo
from app.models.report import Report, ReportStatus, utcnow
from app.models.user import Role, User
from app.schemas.photos import PhotoResponse
from app.schemas.reports import ObservationFields, ReportCreate, ReportPatch, ReportResponse, ReportSummary
from app.services.sites import get_site


def commit_change(db: Session):
    try:
        db.commit()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(409, "Report changed concurrently. Reload and try again.") from exc


def get_report(db: Session, report_id: str, user: User, *, write: bool = False) -> Report:
    report = db.get(Report, report_id)
    # Hide other users' drafts and reports rather than confirming their existence.
    if report is None or (
        report.contributor_id != user.id
        and (write or user.role != Role.reviewer or report.status != ReportStatus.submitted)
    ):
        raise HTTPException(404, "Report not found")
    if write and report.status != ReportStatus.draft:
        raise HTTPException(409, "Submitted reports cannot be changed")
    return report


def photo_response(photo: Photo) -> PhotoResponse:
    values = {name: getattr(photo, name) for name in PhotoResponse.model_fields if name != "download_path"}
    return PhotoResponse(
        **values, download_path=f"/api/v1/reports/{photo.report_id}/photos/{photo.id}/content"
    )


def report_response(db: Session, report: Report) -> ReportResponse:
    photos = db.scalars(
        select(Photo).where(Photo.report_id == report.id).order_by(Photo.created_at, Photo.id)
    ).all()
    return ReportResponse(
        **ReportSummary.model_validate(report).model_dump(),
        photos=[photo_response(photo) for photo in photos],
        submitted_snapshot=report.submitted_snapshot,
    )


def create_report(db: Session, data: ReportCreate, user: User) -> Report:
    site = get_site(db, str(data.site_id))
    if site.is_demo and not data.is_synthetic:
        raise HTTPException(422, "Reports for demo sites must set is_synthetic=true")
    values = data.model_dump()
    values["site_id"] = str(data.site_id)
    report = Report(**values, contributor_id=user.id)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def patch_report(db: Session, report: Report, data: ReportPatch) -> Report:
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_synthetic") is False:
        site = get_site(db, report.site_id)
        synthetic_photo = db.scalar(
            select(Photo.id).where(Photo.report_id == report.id, Photo.source == "synthetic").limit(1)
        )
        if site.is_demo or synthetic_photo:
            raise HTTPException(422, "Demo sites and synthetic photos require a synthetic report")
    for field, value in changes.items():
        setattr(report, field, value)
    report.updated_at = utcnow()
    commit_change(db)
    db.refresh(report)
    return report


def submit_report(db: Session, report: Report) -> Report:
    # Idempotent re-submission returns the same snapshot and timestamp.
    if report.status == ReportStatus.submitted:
        return report
    required = ("clarity", "smell", "flow", "foam", "visible_life", "water_color")
    missing = [field for field in required if getattr(report, field) is None]
    photos = db.scalars(select(Photo).where(Photo.report_id == report.id).order_by(Photo.id)).all()
    if missing or not photos:
        raise HTTPException(
            422,
            {
                "message": "Complete observations and attach at least one photo before submitting",
                "missing_fields": missing,
                "photo_required": not bool(photos),
            },
        )
    snapshot = ObservationFields.model_validate(
        {key: getattr(report, key) for key in ObservationFields.model_fields}
    ).model_dump(mode="json")
    snapshot.update(
        site_id=report.site_id,
        observed_at=report.observed_at.replace(tzinfo=timezone.utc).isoformat(),
        is_synthetic=report.is_synthetic,
        photo_ids=[photo.id for photo in photos],
    )
    report.submitted_snapshot = snapshot
    report.status = ReportStatus.submitted
    report.submitted_at = utcnow()
    report.updated_at = report.submitted_at
    commit_change(db)
    db.refresh(report)
    return report


def list_reports(
    db: Session,
    user: User,
    scope: str,
    status: ReportStatus | None,
    site_id: str | None,
    limit: int,
    offset: int,
):
    query = select(Report)
    if scope == "submitted":
        if user.role != Role.reviewer:
            raise HTTPException(403, "Reviewer role required")
        query = query.where(Report.status == ReportStatus.submitted)
    else:
        query = query.where(Report.contributor_id == user.id)
    if status:
        query = query.where(Report.status == status)
    if site_id:
        query = query.where(Report.site_id == site_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(Report.created_at.desc(), Report.id).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}
