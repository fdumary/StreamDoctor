from uuid import uuid4

import pytest

from app.models.user import Role, User


@pytest.fixture
def submitted(client, auth_headers, report, photo):
    path = f"/api/v1/reports/{report['id']}"
    assert client.post(path + "/submit", headers=auth_headers).status_code == 200
    return path


def payload(assessment, decision="approved"):
    return {
        "assessment_id": assessment["id"],
        "request_id": str(uuid4()),
        "decision": decision,
        "reason": "Reviewed the evidence and original observations independently.",
    }


def test_automatic_assessment_queue_and_independent_review(client, auth_headers, reviewer_headers, submitted):
    assessment = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert assessment["requires_review"] and not assessment["expert_verified"]
    assert assessment["review_status"] == "pending"
    assert "evidence" not in assessment
    queue = client.get("/api/v1/reviews", headers=reviewer_headers)
    assert queue.status_code == 200 and queue.json()["total"] == 1
    data = payload(assessment)
    reviewed = client.post(submitted + "/reviews", headers=reviewer_headers, json=data)
    assert reviewed.status_code == 200
    assert client.post(submitted + "/reviews", headers=reviewer_headers, json=data).json() == reviewed.json()
    assert client.get("/api/v1/reviews", headers=reviewer_headers).json()["total"] == 0
    final = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert final["expert_verified"] and final["eligible_for_trusted_use"]
    assert final["review_status"] == "approved"
    assert client.get(submitted + "/review", headers=auth_headers).json()["reason"] == data["reason"]
    assert (
        client.post(
            submitted + "/reviews", headers=reviewer_headers, json=payload(assessment, "rejected")
        ).status_code
        == 409
    )
    assert client.post(submitted + "/assessment", headers=auth_headers).json() == final


def test_rejected_report_is_preserved_and_ineligible(client, auth_headers, reviewer_headers, submitted):
    assessment = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert (
        client.post(
            submitted + "/reviews", headers=reviewer_headers, json=payload(assessment, "rejected")
        ).status_code
        == 200
    )
    final = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert not final["expert_verified"] and not final["eligible_for_trusted_use"]
    assert client.get(submitted, headers=auth_headers).status_code == 200
    assert client.get("/api/v1/reviews?status=rejected", headers=reviewer_headers).json()["total"] == 1


def test_review_permissions_and_self_review(
    client, auth_headers, other_headers, reviewer_headers, account, submitted
):
    assessment = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert client.get("/api/v1/reviews", headers=auth_headers).status_code == 403
    assert (
        client.post(submitted + "/reviews", headers=auth_headers, json=payload(assessment)).status_code == 403
    )
    assert client.get(submitted + "/assessment", headers=other_headers).status_code == 404
    assert client.post(submitted + "/assessment", headers=other_headers).status_code == 404
    with client.app.state.session_factory() as db:
        db.get(User, account["id"]).role = Role.reviewer
        db.commit()
    assert (
        client.post(submitted + "/reviews", headers=auth_headers, json=payload(assessment)).status_code == 403
    )
    assert client.get("/api/v1/reviews", headers=auth_headers).json()["total"] == 0


def test_drafts_cannot_be_assessed_and_unknown_review_is_404(client, auth_headers, report):
    path = f"/api/v1/reports/{report['id']}"
    assert client.post(path + "/assessment", headers=auth_headers).status_code == 409
    assert client.get(path + "/assessment", headers=auth_headers).status_code == 404
    assert client.get(path + "/review", headers=auth_headers).status_code == 404


def test_invalid_review_reason_and_client_score_rejected(client, auth_headers, reviewer_headers, submitted):
    assessment = client.get(submitted + "/assessment", headers=auth_headers).json()
    assert (
        client.post(
            submitted + "/reviews", headers=reviewer_headers, json={**payload(assessment), "reason": "  "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            submitted + "/reviews", headers=reviewer_headers, json={**payload(assessment), "score": 100}
        ).status_code
        == 422
    )
    assert (
        client.post(
            submitted + "/reviews",
            headers=reviewer_headers,
            json={**payload(assessment), "assessment_id": str(uuid4())},
        ).status_code
        == 409
    )


def test_queue_synthetic_filter_and_pagination(client, auth_headers, reviewer_headers, submitted):
    assert client.get("/api/v1/reviews?synthetic=true", headers=reviewer_headers).json()["total"] == 0
    page = client.get("/api/v1/reviews?synthetic=false&limit=1", headers=reviewer_headers).json()
    assert page["total"] == 1 and len(page["items"]) == 1
    assert client.get("/api/v1/reviews?offset=1", headers=reviewer_headers).json()["items"] == []
