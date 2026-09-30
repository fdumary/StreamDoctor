from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import Database
from app.models.photo import Photo
from app.models.report import Report
from app.models.stream_site import StreamSite
from app.models.user import User

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
def live():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Database):
    try:
        # Also checks that the initial migration has been applied.
        for model in (User, StreamSite, Report, Photo):
            db.execute(select(model).limit(1))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable or migrations not applied") from exc
    return {"status": "ready"}
