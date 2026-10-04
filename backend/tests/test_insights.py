from datetime import timedelta
from uuid import uuid4

from app.models.report import ReportStatus, utcnow
from app.models.user import Role
from app.services.diagnosis import diagnose
from tests.test_trust import add_ai, approve, make_report, new_user


def populate(db, site_id, *, fields=None, approved=True, synthetic=False, count=2, observed_at=None):
    reviewer = new_user(db, Role.reviewer)
    reports = []
    for _ in range(count):
        report, _ = make_report(
            db, new_user(db), site_id, synthetic=synthetic, observed_at=observed_at, **(fields or {})
        )
        if approved:
            approve(db, report, reviewer)
        reports.append(report)
    return reports


def test_empty_and_sparse_are_unknown(client, site, auth_headers):
    path = f"/api/v1/sites/{site['id']}/diagnosis"
    response = client.get(path, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["trusted"]["status"] == "unknown"
    with client.app.state.session_factory() as db:
        populate(db, site["id"], count=1)
    card = client.get(path, headers=auth_headers).json()
    assert card["trusted"]["status"] == "unknown"
    assert set(card["audiences"]) == {"citizens", "researchers", "planners"}


def test_trust_lens_filters_concerning_rejected_reports(client, site, auth_headers):
    with client.app.state.session_factory() as db:
        populate(db, site["id"])
        concerning, _ = make_report(
            db, new_user(db), site["id"], smell="sewage", notes="private contributor note"
        )
        approve(db, concerning, new_user(db, Role.reviewer), "rejected")
    card = client.get(f"/api/v1/sites/{site['id']}/diagnosis", headers=auth_headers).json()
    assert card["trusted"]["status"] == "green"
    assert card["unfiltered"]["status"] == "red"
    assert card["trust_lens_changed"]
    assert card["trusted"]["excluded_by_trust"] == 1
    assert "private contributor note" not in str(card)
    assert concerning.id not in str(card)
    assert concerning.contributor_id not in str(card)


def test_auto_eligible_reports_contribute(client, site):
    from app.services.assessments import assess_report

    with client.app.state.session_factory() as db:
        for _ in range(2):
            report, photo = make_report(db, new_user(db), site["id"], clarity="cloudy")
            add_ai(db, report, photo, original="cloudy", suggested="cloudy")
            assess_report(db, report)
        card = diagnose(db, site["id"])
        assert card["trusted"]["status"] == "yellow"
        assert card["trusted"]["contributing_reports"] == 2


def test_synthetic_and_real_never_mix_and_drafts_are_excluded(client, site):
    with client.app.state.session_factory() as db:
        populate(db, site["id"], synthetic=True, fields={"smell": "chemical"})
        drafts = populate(db, site["id"])
        for report in drafts:
            report.status = ReportStatus.draft
        db.commit()
        assert diagnose(db, site["id"])["trusted"]["status"] == "unknown"
        assert diagnose(db, site["id"], synthetic=True)["trusted"]["status"] == "red"


def test_repeat_contributors_and_duplicate_photos_do_not_inflate_evidence(client, site):
    with client.app.state.session_factory() as db:
        user, reviewer = new_user(db), new_user(db, Role.reviewer)
        for _ in range(3):
            report, _ = make_report(db, user, site["id"], photo_hash="a" * 64)
            approve(db, report, reviewer)
        report, _ = make_report(db, new_user(db), site["id"], photo_hash="a" * 64)
        approve(db, report, reviewer)
        card = diagnose(db, site["id"])
        assert card["trusted"]["status"] == "unknown"
        assert card["trusted"]["contributing_reports"] == 1
        assert card["trusted"]["excluded_repeats"] == 3


def test_time_windows_do_not_overlap_and_trend_is_measured(client, site):
    now = utcnow()
    with client.app.state.session_factory() as db:
        populate(db, site["id"], observed_at=now - timedelta(days=7), fields={"smell": "chemical"})
        populate(db, site["id"], observed_at=now - timedelta(hours=1))
        populate(db, site["id"], observed_at=now - timedelta(days=15), fields={"smell": "sewage"})
        card = diagnose(db, site["id"], now=now)
        assert card["trusted"]["submitted_reports"] == 2
        assert card["trend"] == {"previous_status": "red", "direction": "improving"}


def test_sparse_known_values_cannot_be_green(client, site):
    fields = dict(clarity="unknown", smell="unknown", flow="unknown", foam="unknown", water_color="unknown")
    with client.app.state.session_factory() as db:
        populate(db, site["id"], fields=fields)
        card = diagnose(db, site["id"])
        assert card["trusted"]["status"] == "unknown"
        assert card["trusted"]["excluded_incomplete"] == 2


def test_monitoring_gap_storm_idempotency_and_followup(client, site, auth_headers, reviewer_headers):
    base = f"/api/v1/sites/{site['id']}"
    payload = {
        "kind": "storm",
        "request_id": str(uuid4()),
        "occurred_at": (utcnow() - timedelta(hours=2)).isoformat(),
    }
    assert client.post(base + "/monitoring-events", json=payload, headers=auth_headers).status_code == 403
    response = client.post(base + "/monitoring-events", json=payload, headers=reviewer_headers)
    assert response.status_code == 200, response.text
    assert (
        client.post(base + "/monitoring-events", json=payload, headers=reviewer_headers).json()
        == response.json()
    )
    changed = {**payload, "is_synthetic": True}
    assert client.post(base + "/monitoring-events", json=changed, headers=reviewer_headers).status_code == 409
    codes = {n["code"] for n in client.get(base + "/monitoring-needs", headers=auth_headers).json()["needs"]}
    assert {"post_storm", "coverage_gap", "stale_observations"} <= codes
    synthetic = client.get(base + "/monitoring-needs?synthetic=true", headers=auth_headers).json()
    assert "post_storm" not in {n["code"] for n in synthetic["needs"]}
    with client.app.state.session_factory() as db:
        populate(db, site["id"])
    codes = {n["code"] for n in client.get(base + "/monitoring-needs", headers=auth_headers).json()["needs"]}
    assert "post_storm" not in codes and "stale_observations" not in codes


def test_insights_require_auth_and_validate_parameters(client, site, auth_headers, reviewer_headers):
    path = f"/api/v1/sites/{site['id']}/diagnosis"
    assert client.get(path).status_code == 401
    assert client.get(path + "?days=0", headers=auth_headers).status_code == 422
    assert client.get(path + "?days=31", headers=auth_headers).status_code == 422
    assert client.get(f"/api/v1/sites/{uuid4()}/diagnosis", headers=auth_headers).status_code == 404
    payload = {
        "kind": "storm",
        "request_id": str(uuid4()),
        "occurred_at": (utcnow() + timedelta(days=1)).isoformat(),
    }
    assert (
        client.post(
            f"/api/v1/sites/{site['id']}/monitoring-events", json=payload, headers=reviewer_headers
        ).status_code
        == 422
    )
    questionnaire = client.get("/api/v1/questionnaire", headers=auth_headers).json()
    assert len(questionnaire["questions"]) == 6
    assert all("unknown" in {o["value"] for o in q["options"]} for q in questionnaire["questions"])


def test_hotspots_use_trusted_status_and_page_metadata(client, site, auth_headers):
    with client.app.state.session_factory() as db:
        populate(db, site["id"], fields={"smell": "chemical"})
    response = client.get("/api/v1/insights/hotspots?limit=1", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1 and body["items"][0]["status"] == "red"
    assert client.get("/api/v1/insights/hotspots?offset=1", headers=auth_headers).json()["items"] == []
