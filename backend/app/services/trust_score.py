import hashlib
import json
from datetime import timedelta

from sqlalchemy import or_, select

from app.models.ai_analysis import AIAnalysis
from app.models.photo import Photo
from app.models.report import Report, ReportStatus
from app.models.review import Review
from app.services.plausibility import OBSERVATION_FIELDS, check_plausibility

SCORING_VERSION = "streamtrust-1.0"
WEIGHTS = {
    "ai_photo_agreement": 0.4,
    "plausibility": 0.3,
    "nearby_agreement": 0.2,
    "contributor_history": 0.1,
}
POLICY = {
    "weights": WEIGHTS,
    "eligible_score": 75.0,
    "minimum_coverage": 0.7,
    "nearby_window_hours": 24,
    "minimum_peer_contributors": 2,
    "minimum_reviewed_history": 3,
    "history_prior_approved": 1,
    "history_prior_rejected": 1,
    "ph_review_band": [6, 9],
    "same_site_only": True,
}


def known(value):
    return value not in (None, "unknown")


def signal(name, score, reasons, details=None):
    return {
        "available": score is not None,
        "score": round(score, 2) if score is not None else None,
        "weight": WEIGHTS[name],
        "reasons": reasons,
        "details": details or {},
    }


def photo_agreement(db, report, photos):
    analyses = db.scalars(
        select(AIAnalysis)
        .where(AIAnalysis.report_id == report.id)
        .order_by(AIAnalysis.created_at, AIAnalysis.id)
    ).all()
    evidence_ids = []
    if not analyses:
        return signal("ai_photo_agreement", None, ["No AI analysis is available."]), evidence_ids
    original = analyses[0].input_snapshot
    hashes = {photo.id: photo.stored_sha256 for photo in photos}
    comparisons, used_photos, used_hashes = [], set(), set()
    for item in analyses:
        if (
            item.status != "succeeded"
            or item.is_mock
            or not item.result
            or not item.result.get("image_usable")
            or item.evidence_photo_id in used_photos
            or item.photo_sha256 in used_hashes
            or hashes.get(item.evidence_photo_id) != item.photo_sha256
        ):
            continue
        used_photos.add(item.evidence_photo_id)
        used_hashes.add(item.photo_sha256)
        evidence_ids.append(item.id)
        for proposed in item.result["suggestions"]:
            field, value = proposed["field"], proposed["value"]
            if not known(original.get(field)) or not known(value):
                continue
            comparisons.append(
                {
                    "field": field,
                    "original": original[field],
                    "suggested": value,
                    "final": getattr(report, field),
                    "agrees": original[field] == value,
                }
            )
    if not comparisons:
        return signal(
            "ai_photo_agreement",
            None,
            [
                "No comparable live AI evidence. Mock, unusable, missing-photo, and unknown observations are excluded."
            ],
        ), evidence_ids
    matches = sum(item["agrees"] for item in comparisons)
    reasons = [f"AI agrees with {matches} of {len(comparisons)} original visual observations."]
    reasons += [
        f"{item['field']}: original '{item['original']}' differs from photo suggestion '{item['suggested']}'."
        for item in comparisons
        if not item["agrees"]
    ]
    return signal(
        "ai_photo_agreement",
        100 * matches / len(comparisons),
        reasons,
        {"comparisons": comparisons, "comparison_basis": "before_first_ai_analysis"},
    ), evidence_ids


def peer_agreement(db, report, photos):
    start = report.observed_at - timedelta(hours=POLICY["nearby_window_hours"])
    end = report.observed_at + timedelta(hours=POLICY["nearby_window_hours"])
    candidates = db.scalars(
        select(Report)
        .join(Review, Review.report_id == Report.id)
        .where(
            Review.decision == "approved",
            Report.status == ReportStatus.submitted,
            Report.site_id == report.site_id,
            Report.id != report.id,
            Report.contributor_id != report.contributor_id,
            Report.is_synthetic == report.is_synthetic,
            Report.observed_at >= start,
            Report.observed_at <= end,
        )
        .order_by(Report.observed_at.desc(), Report.id)
    ).all()
    contributors, selected, comparisons = set(), [], []
    used_hashes = {photo.original_sha256 for photo in photos} | {photo.stored_sha256 for photo in photos}
    for peer in candidates:
        if peer.contributor_id in contributors:
            continue
        peer_photos = db.scalars(select(Photo).where(Photo.report_id == peer.id)).all()
        peer_hashes = {photo.original_sha256 for photo in peer_photos} | {
            photo.stored_sha256 for photo in peer_photos
        }
        if not peer_hashes or used_hashes.intersection(peer_hashes):
            continue
        pairs = [
            (getattr(report, field), getattr(peer, field))
            for field in OBSERVATION_FIELDS
            if known(getattr(report, field)) and known(getattr(peer, field))
        ]
        if not pairs:
            continue
        contributors.add(peer.contributor_id)
        used_hashes.update(peer_hashes)
        selected.append(peer.id)
        comparisons.append(sum(left == right for left, right in pairs) / len(pairs))
    if len(selected) < POLICY["minimum_peer_contributors"]:
        return signal(
            "nearby_agreement",
            None,
            [
                "Fewer than two independent expert-approved contributors have comparable reports at this site within 24 hours."
            ],
            {"independent_contributors": len(selected)},
        ), selected
    score = 100 * sum(comparisons) / len(comparisons)
    return signal(
        "nearby_agreement",
        score,
        [
            f"Compared with {len(selected)} independent expert-approved contributors at the same site within 24 hours.",
            "Disagreement can represent a real change and requires review rather than automatic rejection.",
        ],
        {"independent_contributors": len(selected)},
    ), selected


def history_score(db, report):
    reviews = db.execute(
        select(Review, Report.id)
        .join(Report, Review.report_id == Report.id)
        .where(
            Report.contributor_id == report.contributor_id,
            Report.id != report.id,
            Report.is_synthetic == report.is_synthetic,
            Report.submitted_at < report.submitted_at,
            Review.reviewer_id != report.contributor_id,
        )
    ).all()
    ids = [item[1] for item in reviews]
    if len(reviews) < POLICY["minimum_reviewed_history"]:
        return signal(
            "contributor_history",
            None,
            [
                "Contributor has fewer than three prior independently reviewed reports; missing history is not a penalty."
            ],
            {"reviewed_reports": len(reviews)},
        ), ids
    approved = sum(item[0].decision == "approved" for item in reviews)
    score = 100 * (approved + 1) / (len(reviews) + 2)
    return signal(
        "contributor_history",
        score,
        [
            f"{approved} of {len(reviews)} prior reports were approved by independent reviewers; a neutral prior is applied."
        ],
        {"reviewed_reports": len(reviews), "approved": approved},
    ), ids


def calculate_assessment(db, report):
    photos = db.scalars(select(Photo).where(Photo.report_id == report.id).order_by(Photo.id)).all()
    plausibility, flags, known_count = check_plausibility(report, bool(photos))
    hashes = {photo.original_sha256 for photo in photos} | {photo.stored_sha256 for photo in photos}
    duplicate_ids = (
        sorted(
            set(
                db.scalars(
                    select(Photo.report_id)
                    .join(Report, Report.id == Photo.report_id)
                    .where(
                        Photo.report_id != report.id,
                        Report.status == ReportStatus.submitted,
                        Report.is_synthetic == report.is_synthetic,
                        or_(Photo.original_sha256.in_(hashes), Photo.stored_sha256.in_(hashes)),
                    )
                ).all()
            )
        )
        if hashes
        else []
    )
    if duplicate_ids:
        flags.append(
            {
                "code": "reused_photo",
                "reason": "An attached image also appears in another submitted report; context requires expert review.",
                "needs_review": True,
                "penalty": 0,
            }
        )
    ai, analysis_ids = photo_agreement(db, report, photos)
    peers, peer_ids = peer_agreement(db, report, photos)
    history, history_ids = history_score(db, report)
    components = {
        "ai_photo_agreement": ai,
        "plausibility": signal(
            "plausibility",
            plausibility,
            [item["reason"] for item in flags] or ["No configured plausibility rule flagged this report."],
            {"known_observation_fields": known_count},
        ),
        "nearby_agreement": peers,
        "contributor_history": history,
    }
    for name, code, reason in [
        (
            "ai_photo_agreement",
            "photo_disagreement",
            "Photo analysis differs from one or more original observations.",
        ),
        (
            "nearby_agreement",
            "peer_disagreement",
            "Nearby reviewed reports disagree; a local change may explain the difference.",
        ),
    ]:
        if components[name]["available"] and components[name]["score"] < 100:
            flags.append({"code": code, "reason": reason, "needs_review": True, "penalty": 0})
    coverage = round(sum(item["weight"] for item in components.values() if item["available"]), 4)
    score = round(
        sum(item["score"] * item["weight"] for item in components.values() if item["available"]) / coverage, 2
    )
    reasons = []
    if coverage < POLICY["minimum_coverage"]:
        reasons.append("Insufficient independent evidence coverage for automatic eligibility.")
    if score < POLICY["eligible_score"]:
        reasons.append("Score is below the configured automatic eligibility threshold.")
    reasons += [flag["reason"] for flag in flags if flag["needs_review"]]
    requires_review = bool(reasons)
    if not reasons:
        reasons = [
            "Available evidence meets the prototype automatic eligibility rules; this is not expert verification."
        ]
    evidence = {
        "report_version": report.version,
        "submitted_snapshot": report.submitted_snapshot,
        "analysis_ids": analysis_ids,
        "peer_report_ids": peer_ids,
        "history_report_ids": history_ids,
        "duplicate_report_ids": duplicate_ids,
        "photo_hashes": [photo.stored_sha256 for photo in photos],
        "is_synthetic": report.is_synthetic,
    }
    values = {
        "scoring_version": SCORING_VERSION,
        "score": score,
        "evidence_coverage": coverage,
        "requires_review": requires_review,
        "auto_eligible": not requires_review,
        "components": components,
        "flags": flags,
        "reasons": reasons,
        "policy": POLICY,
        "evidence": evidence,
    }
    values["evidence_digest"] = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return values
