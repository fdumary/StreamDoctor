from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select

from app.models.assessment import Assessment
from app.models.photo import Photo
from app.models.report import Report, ReportStatus
from app.models.review import ReviewCase
from app.services.sites import get_site

POLICY_VERSION = "stream-health-1.0"
MINIMUM_CONTRIBUTORS = 2
MAX_REPORTS = 5000
HEALTH_FIELDS = ("clarity", "smell", "flow", "foam", "water_color")
LABELS = {
    "green": "No configured concern detected",
    "yellow": "Follow-up observations needed",
    "red": "Concerning observations need investigation",
    "unknown": "Insufficient independent observations",
}
LIMITATIONS = [
    "Prototype observation rules; this is not a laboratory water-quality assessment.",
    "Green does not establish that water is safe for drinking, swimming, children, or animals.",
    "Contributor accounts and photo hashes reduce repetition but cannot prove observer independence.",
]


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def concern_rules(report):
    flags = []
    if report.smell in ("sewage", "chemical"):
        flags.append(("concerning_smell", "Sewage-like or chemical smell reported.", "red"))
    if report.ph is not None and not 6 <= report.ph <= 9:
        flags.append(("unusual_ph", "Measured pH is outside the prototype review band of 6–9.", "red"))
    if report.clarity in ("slightly_cloudy", "cloudy", "opaque"):
        flags.append(
            ("reduced_clarity", "Reduced water clarity reported; turbidity was not measured.", "yellow")
        )
    if report.foam == "extensive":
        flags.append(("extensive_foam", "Extensive foam reported; its origin is unknown.", "yellow"))
    if report.water_color in ("brown", "green", "black", "other"):
        flags.append(("unusual_color", "Water coloration needs contextual investigation.", "yellow"))
    if report.flow in ("dry", "still"):
        flags.append(("low_flow", "Dry or still conditions reported.", "yellow"))
    return flags


def load_rows(db, site_id, start, end, synthetic):
    rows = db.execute(
        select(Report, ReviewCase, Assessment)
        .outerjoin(ReviewCase, ReviewCase.report_id == Report.id)
        .outerjoin(Assessment, Assessment.id == ReviewCase.assessment_id)
        .where(
            Report.site_id == site_id,
            Report.status == ReportStatus.submitted,
            Report.is_synthetic == synthetic,
            Report.observed_at > start,
            Report.observed_at <= end,
        )
        .order_by(Report.observed_at.desc(), Report.id)
        .limit(MAX_REPORTS + 1)
    ).all()
    if len(rows) > MAX_REPORTS:
        raise HTTPException(422, "Too many reports in this window; choose fewer days")
    ids = [row[0].id for row in rows]
    hashes = {}
    for offset in range(0, len(ids), 400):
        for photo in db.scalars(select(Photo).where(Photo.report_id.in_(ids[offset : offset + 400]))):
            hashes.setdefault(photo.report_id, set()).update((photo.original_sha256, photo.stored_sha256))
    return rows, hashes


def trusted(row):
    _, case, assessment = row
    return bool(
        case
        and assessment
        and (case.status == "approved" or (case.status == "pending" and assessment.auto_eligible))
    )


def summarize(rows, hashes, filtered):
    candidates = [row for row in rows if not filtered or trusted(row)]
    selected, contributors, used_hashes = [], set(), set()
    repeats = incomplete = 0
    for row in candidates:
        report = row[0]
        image_hashes = hashes.get(report.id, set())
        if report.contributor_id in contributors or used_hashes.intersection(image_hashes):
            repeats += 1
            continue
        contributors.add(report.contributor_id)
        used_hashes.update(image_hashes)
        known = sum(getattr(report, field) not in (None, "unknown") for field in HEALTH_FIELDS)
        if known + (report.ph is not None) < 2:
            incomplete += 1
            continue
        selected.append(row)
    counts = Counter(flag for row in selected for flag in concern_rules(row[0]))
    indicators = [
        {"code": code, "reason": reason, "severity": severity, "reports": count}
        for (code, reason, severity), count in sorted(counts.items())
    ]
    status = "unknown"
    if len(selected) >= MINIMUM_CONTRIBUTORS:
        status = (
            "red" if any(i["severity"] == "red" for i in indicators) else "yellow" if indicators else "green"
        )
    scores = [row[2].score for row in selected if row[2] is not None]
    return {
        "status": status,
        "label": LABELS[status],
        "submitted_reports": len(rows),
        "eligible_reports": len(candidates),
        "contributing_reports": len(selected),
        "independent_contributors": len(selected),
        "excluded_by_trust": len(rows) - len(candidates),
        "excluded_repeats": repeats,
        "excluded_incomplete": incomplete,
        "latest_observation_at": utc(selected[0][0].observed_at) if selected else None,
        "mean_trust_score": round(sum(scores) / len(scores), 2) if scores else None,
        "indicators": indicators,
        "limitations": LIMITATIONS
        + (["Fewer than two usable independent contributors."] if status == "unknown" else []),
    }


def diagnose(db, site_id, days=7, synthetic=False, now=None):
    site = get_site(db, site_id)
    now = utc(now or datetime.now(timezone.utc))
    start = now - timedelta(days=days)
    rows, hashes = load_rows(db, site_id, start, now, synthetic)
    previous_rows, previous_hashes = load_rows(db, site_id, start - timedelta(days=days), start, synthetic)
    current = summarize(rows, hashes, True)
    raw = summarize(rows, hashes, False)
    previous = summarize(previous_rows, previous_hashes, True)
    rank = {"green": 0, "yellow": 1, "red": 2}
    direction = "insufficient_data"
    if current["status"] in rank and previous["status"] in rank:
        delta = rank[current["status"]] - rank[previous["status"]]
        direction = "worsening" if delta > 0 else "improving" if delta < 0 else "unchanged"
    signals = {item["code"] for item in current["indicators"]}
    explanations = []
    if "reduced_clarity" in signals or "unusual_color" in signals:
        explanations.append(
            "Sediment, biological material, or runoff could explain appearance; no cause is established."
        )
    if "extensive_foam" in signals:
        explanations.append(
            "Natural organic material or human inputs could produce foam; appearance alone cannot distinguish them."
        )
    if "concerning_smell" in signals:
        explanations.append(
            "An odor report needs field investigation and sampling; it does not identify a pollutant or source."
        )
    description = f"{current['label']}. Based on {current['contributing_reports']} trusted independent observations in {days} days."
    citizen_actions = [
        "Check local authority advisories before water contact; this card does not establish safety."
    ]
    if current["status"] in ("yellow", "red", "unknown"):
        citizen_actions.append(
            "Add a fresh observation and photo from an accessible bank; do not enter the stream to collect data."
        )
    return {
        "site_id": site.id,
        "site_name": site.name,
        "is_synthetic": synthetic,
        "policy_version": POLICY_VERSION,
        "generated_at": now,
        "window_start": start,
        "window_end": now,
        "trusted": current,
        "unfiltered": raw,
        "trust_lens_changed": current["status"] != raw["status"],
        "trend": {"previous_status": previous["status"], "direction": direction},
        "audiences": {
            "citizens": {"summary": description, "actions": citizen_actions},
            "researchers": {
                "summary": f"{description} Trend: {direction}. {current['excluded_by_trust']} reports excluded by trust.",
                "actions": [
                    "Inspect indicator counts, missing evidence, and review decisions before interpreting a change.",
                    "Compare with laboratory measurements and site-specific ecological baselines.",
                ],
            },
            "planners": {
                "summary": description,
                "actions": [
                    "Prioritize field investigation where trusted concern indicators are present.",
                    "Use repeated sampling to test possible explanations; do not attribute a cause from this card alone.",
                ],
            },
        },
        "possible_explanations": explanations,
    }
