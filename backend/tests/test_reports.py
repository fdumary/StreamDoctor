from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models.report import Report
from app.schemas.reports import ReportPatch
from app.services.reports import patch_report


def test_complete_flow_persists_and_submission_is_frozen(client, auth_headers, report, photo):
    base = f"/api/v1/reports/{report['id']}"
    edited = client.patch(base, headers=auth_headers, json={"notes": "Updated field notes", "ph": 11})
    assert edited.status_code == 200
    assert edited.json()["ph"] == 11
    submitted = client.post(base + "/submit", headers=auth_headers)
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["submitted_snapshot"]["notes"] == "Updated field notes"
    assert body["submitted_snapshot"]["photo_ids"] == [photo["id"]]
    assert client.post(base + "/submit", headers=auth_headers).json() == body
    assert client.patch(base, headers=auth_headers, json={"notes": "changed"}).status_code == 409
    assert client.delete(base + f"/photos/{photo['id']}", headers=auth_headers).status_code == 409
    assert client.get(photo["download_path"], headers=auth_headers).status_code == 200
    restarted = create_app(client.app.state.settings)
    with TestClient(restarted) as next_client:
        assert next_client.get(base, headers=auth_headers).json() == body
        assert next_client.get(photo["download_path"], headers=auth_headers).status_code == 200
    restarted.state.engine.dispose()


def test_draft_cannot_submit_without_answers_or_photo(client, auth_headers, site, report_data):
    body = {k: report_data[k] for k in ("site_id", "observed_at")}
    draft = client.post("/api/v1/reports", headers=auth_headers, json=body).json()
    response = client.post(f"/api/v1/reports/{draft['id']}/submit", headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["detail"]["photo_required"] is True
    assert "clarity" in response.json()["detail"]["missing_fields"]


def test_photo_is_required(client, auth_headers, report):
    result = client.post(f"/api/v1/reports/{report['id']}/submit", headers=auth_headers)
    assert result.status_code == 422
    assert result.json()["detail"]["missing_fields"] == []


def test_owner_reviewer_and_other_user_permissions(
    client, auth_headers, other_headers, reviewer_headers, report, photo, photo_bytes
):
    base = f"/api/v1/reports/{report['id']}"
    for headers in (other_headers, reviewer_headers):
        assert client.get(base, headers=headers).status_code == 404
        assert client.get(photo["download_path"], headers=headers).status_code == 404
        assert client.patch(base, headers=headers, json={"notes": "overwrite"}).status_code == 404
        assert (
            client.post(base + "/photos", headers=headers, files={"file": ("x.png", photo_bytes)}).status_code
            == 404
        )
    assert client.get("/api/v1/reports", headers=other_headers).json()["total"] == 0
    assert client.get("/api/v1/reports?scope=submitted", headers=auth_headers).status_code == 403
    assert client.post(base + "/submit", headers=auth_headers).status_code == 200
    assert client.get(base, headers=other_headers).status_code == 404
    assert client.get(base, headers=reviewer_headers).status_code == 200
    assert client.get(photo["download_path"], headers=reviewer_headers).status_code == 200
    assert client.post(base + "/submit", headers=reviewer_headers).status_code == 404
    assert client.patch(base, headers=reviewer_headers, json={"notes": "overwrite"}).status_code == 404
    assert client.get("/api/v1/reports?scope=submitted", headers=reviewer_headers).json()["total"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"clarity": "murky"},
        {"observed_at": "2026-01-01T12:00:00"},
        {"observed_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()},
        {"ph": 99},
        {"contributor_id": "pretend"},
        {"status": "submitted"},
        {"trust_score": 100},
    ],
)
def test_invalid_report_input(client, auth_headers, report_data, change):
    response = client.post("/api/v1/reports", headers=auth_headers, json={**report_data, **change})
    assert response.status_code == 422


def test_patch_only_changes_supplied_fields(client, auth_headers, report):
    path = f"/api/v1/reports/{report['id']}"
    response = client.patch(path, headers=auth_headers, json={"notes": "new"})
    assert response.json()["clarity"] == report["clarity"]
    assert response.json()["observed_at"] == report["observed_at"]
    assert client.patch(path, headers=auth_headers, json={"observed_at": None}).status_code == 422
    assert client.patch(path, headers=auth_headers, json={"clarity": None}).status_code == 200


def test_reports_paginated_and_filtered(client, auth_headers, report, report_data):
    assert client.post("/api/v1/reports", headers=auth_headers, json=report_data).status_code == 201
    page = client.get("/api/v1/reports?limit=1&offset=1&status=draft", headers=auth_headers).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert client.get("/api/v1/reports?site_id=missing", headers=auth_headers).json()["total"] == 0
    assert client.get("/api/v1/reports?limit=1000", headers=auth_headers).status_code == 422


def test_missing_site(client, auth_headers, report_data):
    response = client.post(
        "/api/v1/reports",
        headers=auth_headers,
        json={**report_data, "site_id": "00000000-0000-4000-8000-000000000099"},
    )
    assert response.status_code == 404


def test_stale_write_does_not_overwrite_submitted_report(client, auth_headers, report, photo):
    factory = client.app.state.session_factory
    with factory() as stale:
        old = stale.get(Report, report["id"])
        assert old.status.value == "draft"
        assert client.post(f"/api/v1/reports/{report['id']}/submit", headers=auth_headers).status_code == 200
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as error:
            patch_report(stale, old, ReportPatch(notes="stale change"))
        assert error.value.status_code == 409
    with factory() as db:
        final = db.scalar(select(Report).where(Report.id == report["id"]))
        assert final.status.value == "submitted" and final.notes != "stale change"
