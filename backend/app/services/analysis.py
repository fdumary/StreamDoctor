import logging
from datetime import timezone
from time import time

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.models.ai_analysis import AIAnalysis
from app.models.photo import Photo
from app.models.report import ReportStatus, utcnow
from app.schemas.analysis import AnalysisResponse
from app.schemas.reports import ObservationFields
from app.services.ai_provider import ProviderError
from app.services.reports import commit_change, get_report


def expire_abandoned(db, report_id: str):
    now = int(time())
    db.execute(
        update(AIAnalysis)
        .where(
            AIAnalysis.report_id == report_id,
            AIAnalysis.status == "running",
            AIAnalysis.lease_expires_at <= now,
        )
        .values(
            status="failed",
            active_report_id=None,
            error_code="analysis_interrupted",
            error_message="Analysis expired or was interrupted. Start a new attempt.",
            completed_at=utcnow(),
        )
    )
    db.commit()


def latest_analysis(db, report_id):
    return db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.report_id == report_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )


def analysis_response(db, analysis, report, *, is_owner=True):
    expected = analysis.feedback_report_version if analysis.feedback else analysis.input_report_version
    photo_exists = db.get(Photo, analysis.evidence_photo_id) is not None

    submitted_ids = (report.submitted_snapshot or {}).get("ai_analysis_ids", [])
    stale = (report.version != expected and analysis.id not in submitted_ids) or not photo_exists
    values = {
        name: getattr(analysis, name)
        for name in AnalysisResponse.model_fields
        if name not in {"is_stale", "can_decide"}
    }
    return AnalysisResponse(
        **values,
        is_stale=stale,
        can_decide=bool(
            is_owner
            and not stale
            and report.status == ReportStatus.draft
            and analysis.status == "succeeded"
            and not analysis.feedback
            and analysis.result
            and analysis.result["suggestions"]
        ),
    )


def get_analysis(db, report_id, analysis_id):
    analysis = db.get(AIAnalysis, analysis_id)
    if not analysis or analysis.report_id != report_id:
        raise HTTPException(404, "Analysis not found")
    return analysis


def run_analysis(db, report_id, user, data, settings, storage, provider, limiter):
    report = get_report(db, report_id, user)
    if report.contributor_id != user.id:
        raise HTTPException(404, "Report not found")
    expire_abandoned(db, report.id)
    existing = db.scalar(
        select(AIAnalysis).where(
            AIAnalysis.report_id == report.id, AIAnalysis.request_id == str(data.request_id)
        )
    )
    if existing:
        if existing.evidence_photo_id != str(data.photo_id):
            raise HTTPException(409, "This request_id was already used for another photo")
        return existing, False
    if report.status != ReportStatus.draft:
        raise HTTPException(409, "Analysis can only be requested for a draft")
    if settings.ai_mode == "disabled":
        raise HTTPException(503, "AI is disabled. Configure AI_MODE=mock or http on the server")
    if settings.ai_mode == "mock" and not report.is_synthetic:
        raise HTTPException(422, "Mock analysis is available only for synthetic reports")
    photo = db.get(Photo, str(data.photo_id))
    if photo is None or photo.report_id != report.id:
        raise HTTPException(404, "Photo not found on this report")
    if db.scalar(select(AIAnalysis.id).where(AIAnalysis.active_report_id == report.id)):
        raise HTTPException(409, "An analysis is already running for this report")
    limiter.check(user.id)
    path = storage.path(photo.storage_key)
    if not path.is_file():
        raise HTTPException(503, "Photo file is unavailable")
    snapshot = {key: getattr(report, key) for key in ObservationFields.model_fields}
    snapshot.update(
        observed_at=report.observed_at.replace(tzinfo=timezone.utc).isoformat(),
        site_id=report.site_id,
        is_synthetic=report.is_synthetic,
    )
    report.updated_at = utcnow()

    analysis = AIAnalysis(
        report_id=report.id,
        active_report_id=report.id,
        evidence_photo_id=photo.id,
        photo_sha256=photo.stored_sha256,
        request_id=str(data.request_id),
        input_report_version=report.version + 1,
        input_snapshot=snapshot,
        provider=settings.ai_mode,
        is_mock=settings.ai_mode == "mock",
        lease_expires_at=int(time()) + settings.ai_timeout_seconds * 3 + 30,
    )
    db.add(analysis)
    try:
        commit_change(db)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "An analysis was requested concurrently. Retry with the same request_id."
        ) from exc
    analysis_id = analysis.id
    try:
        result = provider.analyze(path, analysis.photo_sha256, analysis.id)
        values = {
            "status": "succeeded",
            "result": result.model_dump(mode="json"),
            "error_code": None,
            "error_message": None,
        }
    except ProviderError as exc:
        values = {"status": "failed", "error_code": exc.code, "error_message": exc.message}
    except Exception as exc:
        logging.getLogger(__name__).error("AI adapter failed with %s", type(exc).__name__)
        values = {
            "status": "failed",
            "error_code": "internal_error",
            "error_message": "Analysis could not be completed; the report is still saved",
        }
    if int(time()) >= analysis.lease_expires_at:
        values = {
            "status": "failed",
            "error_code": "analysis_interrupted",
            "error_message": "Analysis expired. Start a new attempt.",
        }

    db.execute(
        update(AIAnalysis)
        .where(AIAnalysis.id == analysis_id, AIAnalysis.status == "running")
        .values(**values, active_report_id=None, completed_at=utcnow())
    )
    db.commit()
    db.expire_all()
    return db.get(AIAnalysis, analysis_id), True


def record_feedback(db, report, analysis, data):
    canonical = data.model_dump(mode="json")
    if analysis.feedback is not None:
        if analysis.feedback["request"] == canonical:
            return analysis
        raise HTTPException(409, "Feedback is already recorded and cannot be replaced")
    if report.status != ReportStatus.draft:
        raise HTTPException(409, "Submitted reports cannot be changed")
    if analysis.status != "succeeded":
        raise HTTPException(409, "This analysis has no successful result to review")
    if analysis.input_report_version != report.version or db.get(Photo, analysis.evidence_photo_id) is None:
        raise HTTPException(409, "Analysis is stale. Request a new analysis for the current report")
    suggested = {item["field"]: item for item in analysis.result["suggestions"]}
    if set(suggested) != {item.field for item in data.decisions}:
        raise HTTPException(422, "Provide exactly one decision for each suggested field")
    before = {key: getattr(report, key) for key in ObservationFields.model_fields}
    for item in data.decisions:
        if item.action == "accept":
            setattr(report, item.field, suggested[item.field]["value"])
        elif item.action == "edit":
            if item.value == suggested[item.field]["value"]:
                raise HTTPException(422, "Use accept when the value matches the AI suggestion")
            setattr(report, item.field, item.value)
    after = {key: getattr(report, key) for key in ObservationFields.model_fields}
    analysis.feedback = {
        "request": canonical,
        "before": before,
        "after": after,
        "decided_by": report.contributor_id,
    }
    analysis.feedback_at = utcnow()
    analysis.feedback_report_version = report.version + 1
    report.updated_at = utcnow()
    commit_change(db)
    db.refresh(analysis)
    return analysis


def list_analyses(db, report, user, limit, offset):
    query = select(AIAnalysis).where(AIAnalysis.report_id == report.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(
        query.order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [
            analysis_response(db, item, report, is_owner=report.contributor_id == user.id) for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
