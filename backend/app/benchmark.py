"""Evaluate authored synthetic scenarios using the production trust scorer."""

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, uuid5

from app.db.base import Base
from app.db.session import make_engine, make_session_factory
from app.models.ai_analysis import AIAnalysis
from app.models.assessment import Assessment  # noqa: F401
from app.models.auth_session import AuthSession  # noqa: F401
from app.models.monitoring_event import MonitoringEvent  # noqa: F401
from app.models.photo import Photo
from app.models.report import Report, ReportStatus
from app.models.review import Review, ReviewCase  # noqa: F401
from app.models.stream_site import StreamSite
from app.models.user import Role, User
from app.schemas.trust import ReviewRequest
from app.services.assessments import assess_report
from app.services.reviews import review_report
from app.services.trust_score import SCORING_VERSION, calculate_assessment

DATASET = Path(__file__).resolve().parents[1] / "benchmarks" / "streamtrust.json"
FIXED_TIME = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
DEFAULT_FIELDS = {
    "clarity": "clear",
    "smell": "none",
    "flow": "slow",
    "foam": "none",
    "visible_life": "plants",
    "water_color": "colorless",
}


def stable_id(value):
    return str(uuid5(NAMESPACE_URL, "streamdoctor-fixture/" + value))


def fixture_user(db, name, reviewer=False):
    user = User(
        id=stable_id(name),
        email=f"{name}@example.com",
        display_name="Synthetic fixture",
        password_hash="not-a-login-hash",
        role=Role.reviewer if reviewer else Role.volunteer,
    )
    db.add(user)
    db.flush()
    return user


def fixture_report(db, site, user, name, fields=None, photo=True, digest=None, observed_at=None):
    values = {**DEFAULT_FIELDS, **(fields or {})}
    report = Report(
        id=stable_id(name),
        site_id=site.id,
        contributor_id=user.id,
        observed_at=observed_at or FIXED_TIME,
        submitted_at=observed_at or FIXED_TIME,
        status=ReportStatus.submitted,
        is_synthetic=True,
        submitted_snapshot=values.copy(),
        **values,
    )
    db.add(report)
    db.flush()
    image = None
    if photo:
        digest = digest or hashlib.sha256(name.encode()).hexdigest()
        image = Photo(
            id=stable_id(name + "/photo"),
            report_id=report.id,
            storage_key=uuid5(NAMESPACE_URL, name).hex + ".png",
            original_sha256=digest,
            stored_sha256=digest,
            byte_size=1,
            width=1,
            height=1,
            source="synthetic",
        )
        db.add(image)
    db.commit()
    return report, image


def fixture_ai(db, report, photo, scenario):
    if photo is None or scenario.get("ai", "live_fixture") == "none":
        return
    mock = scenario.get("ai") == "mock"
    suggestions = [
        {
            "field": field,
            "value": value,
            "confidence": 0.5,
            "explanation": "Authored fixture; no model or image inference was run.",
        }
        for field, value in scenario.get("suggestions", {"clarity": report.clarity}).items()
    ]
    if scenario.get("unusable"):
        suggestions = []
    db.add(
        AIAnalysis(
            id=stable_id(report.id + "/analysis"),
            report_id=report.id,
            evidence_photo_id=photo.id,
            photo_sha256=photo.stored_sha256,
            request_id=stable_id(report.id + "/request"),
            status="succeeded",
            provider="mock" if mock else "http",
            is_mock=mock,
            input_report_version=report.version,
            input_snapshot={**report.submitted_snapshot, **scenario.get("original", {})},
            lease_expires_at=1,
            created_at=FIXED_TIME,
            completed_at=FIXED_TIME,
            result={
                "schema_version": "1.0",
                "model_name": "authored-benchmark-fixture",
                "model_version": "1",
                "is_mock": mock,
                "image_usable": not scenario.get("unusable", False),
                "limitations": ["Synthetic stipulated comparison only; not a model prediction."],
                "suggestions": suggestions,
            },
        )
    )
    db.commit()


def fixture_review(db, report, reviewer, decision="approved"):
    assessment, _ = assess_report(db, report)
    return review_report(
        db,
        report,
        reviewer,
        ReviewRequest(
            assessment_id=assessment.id,
            request_id=stable_id(report.id + "/review"),
            decision=decision,
            reason="Authored synthetic decision for isolated test fixtures.",
        ),
    )


def run_case(db, scenario):
    name = scenario["id"]
    site = StreamSite(
        id=stable_id(name + "/site"), name="Synthetic benchmark site", latitude=0, longitude=0, is_demo=True
    )
    db.add(site)
    user = fixture_user(db, name + "-author")
    reviewer = fixture_user(db, name + "-reviewer", True)
    report, photo = fixture_report(db, site, user, name, scenario.get("fields"), scenario.get("photo", True))
    fixture_ai(db, report, photo, scenario)
    for index, peer in enumerate(scenario.get("peers", [])):
        peer_user = fixture_user(db, name + f"-peer-{index}")
        peer_report, _ = fixture_report(
            db,
            site,
            peer_user,
            name + f"/peer/{index}",
            peer,
            digest=photo.stored_sha256 if scenario.get("duplicate_photo") and photo else None,
        )
        fixture_review(db, peer_report, reviewer)
    for index, decision in enumerate(scenario.get("history", [])):
        previous, _ = fixture_report(
            db, site, user, name + f"/history/{index}", observed_at=FIXED_TIME - timedelta(days=index + 2)
        )
        fixture_review(db, previous, reviewer, decision)
    result = calculate_assessment(db, report)
    return {
        "id": name,
        "expected_review": scenario["expected_review"],
        "predicted_review": result["requires_review"],
        "score": result["score"],
        "evidence_coverage": result["evidence_coverage"],
        "flags": [flag["code"] for flag in result["flags"]],
    }


def evaluate(dataset=DATASET):
    data = json.loads(Path(dataset).read_text())
    outcomes = []
    with TemporaryDirectory(prefix="streamtrust-") as directory:
        engine = make_engine(f"sqlite:///{Path(directory) / 'benchmark.db'}")
        Base.metadata.create_all(engine)
        try:
            with make_session_factory(engine)() as db:
                outcomes = [run_case(db, scenario) for scenario in data["cases"]]
        finally:
            engine.dispose()
    tp = sum(x["expected_review"] and x["predicted_review"] for x in outcomes)
    fp = sum(not x["expected_review"] and x["predicted_review"] for x in outcomes)
    fn = sum(x["expected_review"] and not x["predicted_review"] for x in outcomes)
    tn = len(outcomes) - tp - fp - fn
    return {
        "dataset_version": data["version"],
        "scoring_version": SCORING_VERSION,
        "cases": len(outcomes),
        "positive_class": "requires_review",
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
        },
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "accuracy": (tp + tn) / len(outcomes) if outcomes else None,
        "limitations": "Authored synthetic policy scenarios, not an independent ecological benchmark or a measurement of AI vision accuracy. No photos or real model predictions were evaluated.",
        "results": outcomes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.dataset)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    else:
        print(content)
    raise SystemExit(
        0 if all(row["expected_review"] == row["predicted_review"] for row in result["results"]) else 1
    )


if __name__ == "__main__":
    main()
