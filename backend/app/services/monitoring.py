from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.monitoring_event import MonitoringEvent
from app.services.diagnosis import diagnose, load_rows, summarize, utc
from app.services.sites import get_site


def create_event(db, site_id, user, data):
    get_site(db, site_id)
    existing = db.scalar(
        select(MonitoringEvent).where(
            MonitoringEvent.created_by == user.id, MonitoringEvent.request_id == str(data.request_id)
        )
    )
    if existing:
        if (existing.site_id, existing.kind, utc(existing.occurred_at), existing.is_synthetic) != (
            site_id,
            data.kind,
            data.occurred_at,
            data.is_synthetic,
        ):
            raise HTTPException(409, "Request ID already used for a different event")
        return event_response(existing)
    event = MonitoringEvent(
        site_id=site_id,
        created_by=user.id,
        **data.model_dump(mode="python", exclude={"request_id"}),
        request_id=str(data.request_id),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Event created concurrently; retry with the same request ID") from exc
    return event_response(event)


def event_response(event):
    return {
        "id": event.id,
        "site_id": event.site_id,
        "kind": event.kind,
        "occurred_at": utc(event.occurred_at),
        "is_synthetic": event.is_synthetic,
    }


def monitoring_needs(db, site_id, synthetic=False):
    card = diagnose(db, site_id, 7, synthetic)
    now, current = card["generated_at"], card["trusted"]
    needs = []

    def add(code, reason, priority="normal"):
        needs.append(
            {
                "code": code,
                "priority": priority,
                "reason": reason,
                "requested_fields": ["clarity", "smell", "flow", "foam", "water_color", "photo"],
            }
        )

    if current["status"] == "unknown":
        add("coverage_gap", "At least two usable independent trusted observations are needed.")
    latest = current["latest_observation_at"]
    if latest is None or latest < now - timedelta(hours=48):
        add("stale_observations", "No trusted usable observation in the last 48 hours.")
    if card["trust_lens_changed"]:
        add(
            "trust_disagreement",
            "Trust filtering changes the verdict; independent observations can resolve the difference.",
        )
    if current["indicators"]:
        add(
            "concern_followup", "Reported concerns need repeat observations and expert investigation.", "high"
        )
    event = db.scalar(
        select(MonitoringEvent)
        .where(
            MonitoringEvent.site_id == site_id,
            MonitoringEvent.is_synthetic == synthetic,
            MonitoringEvent.occurred_at >= now - timedelta(hours=72),
            MonitoringEvent.occurred_at <= now,
        )
        .order_by(MonitoringEvent.occurred_at.desc())
        .limit(1)
    )
    if event:
        rows, hashes = load_rows(db, site_id, utc(event.occurred_at), now, synthetic)
        after = summarize(rows, hashes, True)
        if after["independent_contributors"] < 2:
            add(
                "post_storm",
                "A reviewer recorded a storm within 72 hours; fewer than two trusted independent observations followed it.",
                "high",
            )
    return {"site_id": site_id, "is_synthetic": synthetic, "generated_at": now, "needs": needs}
