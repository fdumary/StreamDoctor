from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser, Database, require_reviewer
from app.models.user import User
from app.schemas.diagnosis import Diagnosis, MonitoringNeeds
from app.schemas.monitoring import EventCreate, EventResponse
from app.services.diagnosis import diagnose
from app.services.monitoring import create_event, monitoring_needs
from app.services.sites import list_sites

router = APIRouter(tags=["Stream insights"])
Reviewer = Annotated[User, Depends(require_reviewer)]


@router.get("/insights/hotspots")
def hotspots(
    db: Database,
    user: CurrentUser,
    days: int = Query(7, ge=1, le=30),
    synthetic: bool = False,
    limit: int = Query(10, ge=1, le=20),
    offset: int = Query(0, ge=0),
):
    page = list_sites(db, limit, offset, None)
    items = []
    for site in page["items"]:
        card = diagnose(db, site.id, days, synthetic)
        items.append(
            {
                "site_id": site.id,
                "site_name": site.name,
                "latitude": site.latitude,
                "longitude": site.longitude,
                "is_demo_site": site.is_demo,
                "is_synthetic": synthetic,
                "status": card["trusted"]["status"],
                "indicators": card["trusted"]["indicators"],
                "independent_contributors": card["trusted"]["independent_contributors"],
                "trend": card["trend"],
            }
        )
    return {
        "items": items,
        "total": page["total"],
        "limit": limit,
        "offset": offset,
        "ordering": "site name; concern levels are not ranked across pages",
    }


@router.get("/sites/{site_id}/diagnosis", response_model=Diagnosis)
def diagnosis(
    site_id: str, db: Database, user: CurrentUser, days: int = Query(7, ge=1, le=30), synthetic: bool = False
):
    return diagnose(db, site_id, days, synthetic)


@router.get("/sites/{site_id}/monitoring-needs", response_model=MonitoringNeeds)
def needs(site_id: str, db: Database, user: CurrentUser, synthetic: bool = False):
    return monitoring_needs(db, site_id, synthetic)


@router.post("/sites/{site_id}/monitoring-events", response_model=EventResponse)
def record_event(site_id: str, data: EventCreate, db: Database, user: Reviewer):
    return create_event(db, site_id, user, data)
