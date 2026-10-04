from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import Database
from app.models.ai_analysis import AIAnalysis
from app.models.assessment import Assessment
from app.models.monitoring_event import MonitoringEvent
from app.models.photo import Photo
from app.models.report import Report
from app.models.review import Review, ReviewCase
from app.models.stream_site import StreamSite
from app.models.user import User

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Database):
    try:
        for model in (
            User,
            StreamSite,
            Report,
            Photo,
            AIAnalysis,
            Assessment,
            ReviewCase,
            Review,
            MonitoringEvent,
        ):
            db.execute(select(model).limit(1))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable or migrations not applied") from exc
    return {"status": "ready"}
