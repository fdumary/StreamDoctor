from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentUser, Database, require_reviewer
from app.schemas.sites import SiteCreate, SitePage, SiteResponse
from app.services import sites

router = APIRouter(prefix="/sites", tags=["Stream sites"])


@router.get("", response_model=SitePage)
def list_sites(
    db: Database,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, min_length=1, max_length=120),
):
    return sites.list_sites(db, limit, offset, q)


@router.post("", response_model=SiteResponse, status_code=201, dependencies=[Depends(require_reviewer)])
def create_site(data: SiteCreate, db: Database):
    return sites.create_site(db, data)


@router.get("/{site_id}", response_model=SiteResponse)
def get_site(site_id: str, db: Database, user: CurrentUser):
    return sites.get_site(db, site_id)
