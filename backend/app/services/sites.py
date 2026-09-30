from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.stream_site import StreamSite
from app.schemas.sites import SiteCreate


def get_site(db: Session, site_id: str) -> StreamSite:
    site = db.get(StreamSite, site_id)
    if site is None:
        raise HTTPException(404, "Stream site not found")
    return site


def list_sites(db: Session, limit: int, offset: int, q: str | None):
    query = select(StreamSite)
    if q:
        query = query.where(StreamSite.name.icontains(q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    items = db.scalars(query.order_by(StreamSite.name, StreamSite.id).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def create_site(db: Session, data: SiteCreate) -> StreamSite:
    site = StreamSite(**data.model_dump())
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


def seed_demo_sites(db: Session) -> int:
    """Stable IDs make repeated seeding safe; these are fictional sites."""
    sites = [
        ("00000000-0000-4000-8000-000000000001", "Demo Stream — Upstream", 0.0, 0.0),
        ("00000000-0000-4000-8000-000000000002", "Demo Stream — Downstream", 0.0, 0.01),
    ]
    count = 0
    for site_id, name, latitude, longitude in sites:
        if db.get(StreamSite, site_id) is None:
            db.add(
                StreamSite(
                    id=site_id,
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                    description="Fictional demo site. Coordinates do not represent a real stream.",
                    is_demo=True,
                )
            )
            count += 1
    db.commit()
    return count
