from time import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models.ai_analysis import AIAnalysis
from app.services.ai_provider import MockPhotoProvider, ProviderError


def request_body(photo):
    return {"photo_id": photo["id"], "request_id": str(uuid4())}


@pytest.fixture
def synthetic(client, auth_headers, report, photo):
    path = f"/api/v1/reports/{report['id']}"
    assert (
        client.patch(path, headers=auth_headers, json={"is_synthetic": True, "clarity": "clear"}).status_code
        == 200
    )
    client.app.state.settings.ai_mode = "mock"
    client.app.state.ai_provider = MockPhotoProvider()
    return path


@pytest.fixture
def analyzed(client, auth_headers, synthetic, photo):
    response = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "succeeded"
    return response.json()


def feedback(clarity="accept", value=None):
    first = {"field": "clarity", "action": clarity}
    if value is not None:
        first["value"] = value
    return {"decisions": [first, {"field": "foam", "action": "reject", "reason": "I did not observe foam"}]}


def test_disabled_and_mock_real_report_rejected(client, auth_headers, report, photo):
    path = f"/api/v1/reports/{report['id']}/analysis"
    assert client.post(path, headers=auth_headers, json=request_body(photo)).status_code == 503
    client.app.state.settings.ai_mode = "mock"
    client.app.state.ai_provider = MockPhotoProvider()
    assert client.post(path, headers=auth_headers, json=request_body(photo)).status_code == 422
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AIAnalysis)) == 0


def test_mock_is_labelled_and_does_not_change_observations(client, auth_headers, synthetic, analyzed):
    assert analyzed["is_mock"] is True
    assert analyzed["result"]["is_mock"] is True
    assert analyzed["input_snapshot"]["clarity"] == "clear"
    assert all(item["confidence"] is None for item in analyzed["result"]["suggestions"])
    assert "SIMULATED" in analyzed["result"]["limitations"][0]
    report = client.get(synthetic, headers=auth_headers).json()
    assert report["clarity"] == "clear"
    assert report["ai_status"] == "succeeded"
    assert report["latest_analysis_id"] == analyzed["id"]
    assert not report["ai_decision_recorded"]
    assert client.post(synthetic + "/submit", headers=auth_headers).status_code == 409


@pytest.mark.parametrize(
    "action,value,expected",
    [("accept", None, "cloudy"), ("edit", "opaque", "opaque"), ("reject", None, "clear")],
)
def test_decisions_preserve_original_and_only_apply_authorized_changes(
    client, auth_headers, synthetic, analyzed, action, value, expected
):
    path = synthetic + f"/analyses/{analyzed['id']}/feedback"
    body = feedback(action, value)
    response = client.post(path, headers=auth_headers, json=body)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["input_snapshot"]["clarity"] == "clear"
    assert saved["feedback"]["before"]["clarity"] == "clear"
    assert saved["feedback"]["after"]["clarity"] == expected
    current = client.get(synthetic, headers=auth_headers).json()
    assert current["clarity"] == expected and current["foam"] == "none"
    assert client.post(path, headers=auth_headers, json=body).json() == saved
    assert client.post(path, headers=auth_headers, json=feedback("edit", "unknown")).status_code == 409
    submitted = client.post(synthetic + "/submit", headers=auth_headers)
    assert submitted.status_code == 200
    assert analyzed["id"] in submitted.json()["submitted_snapshot"]["ai_analysis_ids"]
    assert not client.get(synthetic + f"/analyses/{analyzed['id']}", headers=auth_headers).json()["is_stale"]


def test_idempotency_and_conflicting_reuse(client, auth_headers, synthetic, photo, analyzed):
    body = {"photo_id": photo["id"], "request_id": analyzed["request_id"]}
    response = client.post(synthetic + "/analysis", headers=auth_headers, json=body)
    assert response.status_code == 200
    assert response.json()["id"] == analyzed["id"]
    assert (
        client.post(
            synthetic + "/analysis", headers=auth_headers, json={**body, "photo_id": str(uuid4())}
        ).status_code
        == 409
    )
    assert client.get(synthetic + "/analyses", headers=auth_headers).json()["total"] == 1


def test_stale_after_edit_and_new_analysis(client, auth_headers, synthetic, photo, analyzed):
    assert (
        client.patch(synthetic, headers=auth_headers, json={"notes": "changed after AI"}).status_code == 200
    )
    old = synthetic + f"/analyses/{analyzed['id']}"
    assert client.get(old, headers=auth_headers).json()["is_stale"] is True
    assert client.post(old + "/feedback", headers=auth_headers, json=feedback()).status_code == 409
    new = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert new.status_code == 201
    assert not new.json()["is_stale"]
    assert new.json()["input_snapshot"]["notes"] == "changed after AI"


def test_deleted_photo_retains_audit_but_cannot_apply(client, auth_headers, synthetic, photo, analyzed):
    assert client.delete(synthetic + f"/photos/{photo['id']}", headers=auth_headers).status_code == 204
    old = synthetic + f"/analyses/{analyzed['id']}"
    assert client.get(old, headers=auth_headers).json()["is_stale"]
    assert client.post(old + "/feedback", headers=auth_headers, json=feedback()).status_code == 409


def test_mock_history_cannot_be_relabelled_real(client, auth_headers, synthetic, analyzed):
    assert client.patch(synthetic, headers=auth_headers, json={"is_synthetic": False}).status_code == 422


def test_permissions(client, auth_headers, other_headers, reviewer_headers, synthetic, photo, analyzed):
    path = synthetic + f"/analyses/{analyzed['id']}"
    for headers in (other_headers, reviewer_headers):
        assert client.get(path, headers=headers).status_code == 404
        assert client.get(synthetic + "/analyses", headers=headers).status_code == 404
        assert (
            client.post(synthetic + "/analysis", headers=headers, json=request_body(photo)).status_code == 404
        )
        assert client.post(path + "/feedback", headers=headers, json=feedback()).status_code == 404
    assert client.post(path + "/feedback", headers=auth_headers, json=feedback()).status_code == 200
    assert client.post(synthetic + "/submit", headers=auth_headers).status_code == 200
    response = client.get(path, headers=reviewer_headers)
    assert response.status_code == 200 and not response.json()["can_decide"]
    assert client.get(path, headers=other_headers).status_code == 404
    assert (
        client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo)).status_code
        == 409
    )
    assert client.post(path + "/feedback", headers=reviewer_headers, json=feedback()).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"decisions": [{"field": "clarity", "action": "accept"}]},
        {"decisions": [{"field": "clarity", "action": "accept", "value": "clear"}]},
        {"decisions": [{"field": "clarity", "action": "edit", "value": "sewage"}]},
        {"decisions": [{"field": "ph", "action": "edit", "value": "7"}]},
        {"decisions": [{"field": "clarity", "action": "reject"}, {"field": "clarity", "action": "accept"}]},
        feedback("edit", "cloudy"),
    ],
)
def test_invalid_feedback(client, auth_headers, synthetic, analyzed, body):
    response = client.post(
        synthetic + f"/analyses/{analyzed['id']}/feedback", headers=auth_headers, json=body
    )
    assert response.status_code == 422
    assert client.get(synthetic, headers=auth_headers).json()["clarity"] == "clear"


def test_provider_failure_saved_no_mock_fallback(client, auth_headers, synthetic, photo):
    class BrokenProvider:
        def analyze(self, *args):
            raise ProviderError("provider_timeout", "AI service timed out; the report is still saved")

    client.app.state.ai_provider = BrokenProvider()
    result = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert result.status_code == 201
    assert result.json()["status"] == "failed" and result.json()["result"] is None
    assert result.json()["error_code"] == "provider_timeout"
    assert client.get(synthetic, headers=auth_headers).json()["clarity"] == "clear"
    assert client.post(synthetic + "/submit", headers=auth_headers).status_code == 200


def test_running_attempt_blocks_duplicate_then_recovers(client, auth_headers, synthetic, photo, analyzed):
    with client.app.state.session_factory() as db:
        item = db.get(AIAnalysis, analyzed["id"])
        item.status = "running"
        item.result = None
        item.active_report_id = item.report_id
        item.lease_expires_at = int(time()) + 500
        db.commit()
    assert (
        client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo)).status_code
        == 409
    )
    assert client.post(synthetic + "/submit", headers=auth_headers).status_code == 409
    with client.app.state.session_factory() as db:
        db.get(AIAnalysis, analyzed["id"]).lease_expires_at = int(time()) - 1
        db.commit()
    assert (
        client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo)).status_code
        == 201
    )
    old = client.get(synthetic + f"/analyses/{analyzed['id']}", headers=auth_headers).json()
    assert old["status"] == "failed" and old["error_code"] == "analysis_interrupted"


def test_rate_limit_and_restart_persistence(client, auth_headers, synthetic, photo, analyzed):
    client.app.state.ai_limiter.limit = 1
    assert (
        client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo)).status_code
        == 429
    )
    api = create_app(client.app.state.settings)
    with TestClient(api) as restarted:
        response = restarted.get(synthetic + f"/analyses/{analyzed['id']}", headers=auth_headers)
        assert response.status_code == 200 and response.json()["input_snapshot"] == analyzed["input_snapshot"]
    api.state.engine.dispose()


def test_unexpected_adapter_error_is_recorded(client, auth_headers, synthetic, photo):
    class Broken:
        def analyze(self, *args):
            raise RuntimeError("private internal failure")

    client.app.state.ai_provider = Broken()
    response = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "internal_error"
    assert "private internal failure" not in response.text


def test_late_result_does_not_overwrite_recovery(client, auth_headers, synthetic, photo):
    class Recovering:
        def analyze(self, path, digest, analysis_id):
            with client.app.state.session_factory() as db:
                item = db.get(AIAnalysis, analysis_id)
                item.status = "failed"
                item.active_report_id = None
                item.error_code = "analysis_interrupted"
                db.commit()
            return MockPhotoProvider().analyze(path, digest, analysis_id)

    client.app.state.ai_provider = Recovering()
    response = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["result"] is None


def test_unusable_image_result_never_updates_answers(client, auth_headers, synthetic, photo):
    from app.schemas.analysis import ProviderResult

    class Unusable:
        def analyze(self, *args):
            return ProviderResult(
                schema_version="1.0",
                model_name="fixture",
                model_version="1",
                is_mock=True,
                image_usable=False,
                limitations=["Synthetic unusable-image fixture"],
                suggestions=[],
            )

    client.app.state.ai_provider = Unusable()
    response = client.post(synthetic + "/analysis", headers=auth_headers, json=request_body(photo))
    assert response.status_code == 201 and not response.json()["can_decide"]
    assert client.get(synthetic, headers=auth_headers).json()["clarity"] == "clear"
    assert client.post(synthetic + "/submit", headers=auth_headers).status_code == 200
