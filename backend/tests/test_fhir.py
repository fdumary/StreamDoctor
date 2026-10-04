import copy
import json

from sqlalchemy import select

from app.models.user import Role, User
from app.services.fhir_export import export_report, validate_bundle
from tests.test_trust import approve, make_report, new_user


def test_fhir_approved_synthetic_has_resolved_references_and_no_private_fields(
    client, site, auth_headers, account
):
    with client.app.state.session_factory() as db:
        owner = db.get(User, account["id"])
        report, _ = make_report(
            db, owner, site["id"], synthetic=True, ph=7.2, notes="NEVER EXPORT THIS PRIVATE NOTE"
        )
        approve(db, report, new_user(db, Role.reviewer))
    response = client.get(f"/api/v1/reports/{report.id}/fhir", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/fhir+json"
    bundle = response.json()
    assert validate_bundle(bundle)["valid"]
    assert bundle == client.get(f"/api/v1/reports/{report.id}/fhir", headers=auth_headers).json()
    encoded = json.dumps(bundle)
    for private in ("NEVER EXPORT", owner.email, owner.display_name, owner.id, site["name"]):
        assert private not in encoded
    resources = [entry["resource"] for entry in bundle["entry"]]
    assert {r["resourceType"] for r in resources} == {"Location", "Observation", "DiagnosticReport"}
    assert all(r["meta"]["tag"][0]["code"] == "synthetic" for r in resources)
    assert "position" not in resources[0]
    ph = next(r for r in resources if r.get("code", {}).get("text") == "Stream ph")
    assert ph["valueQuantity"]["value"] == 7.2
    assert ph["valueQuantity"]["code"] == "[pH]"
    result = client.get(f"/api/v1/reports/{report.id}/fhir/validation", headers=auth_headers).json()
    assert result["valid"] and "Structural" in result["scope"]


def test_fhir_rejects_real_unreviewed_rejected_and_other_owners(
    client, site, auth_headers, other_headers, account
):
    with client.app.state.session_factory() as db:
        owner = db.get(User, account["id"])
        reviewer = new_user(db, Role.reviewer)
        real, _ = make_report(db, owner, site["id"])
        approve(db, real, reviewer)
        pending, _ = make_report(db, owner, site["id"], synthetic=True)
        from app.services.assessments import assess_report

        assess_report(db, pending)
        rejected, _ = make_report(db, owner, site["id"], synthetic=True)
        approve(db, rejected, reviewer, "rejected")
    for report, status in [(real, 403), (pending, 409), (rejected, 409)]:
        assert client.get(f"/api/v1/reports/{report.id}/fhir", headers=auth_headers).status_code == status
        assert client.get(f"/api/v1/reports/{report.id}/fhir", headers=other_headers).status_code == 404


def test_official_schema_catches_structure_and_reference_errors(client, site):
    with client.app.state.session_factory() as db:
        report, _ = make_report(db, new_user(db), site["id"], synthetic=True)
        approve(db, report, new_user(db, Role.reviewer))
        bundle = export_report(db, report)
    broken = copy.deepcopy(bundle)
    del broken["entry"][-1]["resource"]["status"]
    assert not validate_bundle(broken)["valid"]
    broken = copy.deepcopy(bundle)
    broken["entry"][-1]["resource"]["subject"]["reference"] = "urn:uuid:missing"
    assert not validate_bundle(broken)["valid"]
    broken = copy.deepcopy(bundle)
    broken["entry"][1]["resource"]["unexpected"] = "value"
    assert not validate_bundle(broken)["valid"]


def test_unknown_fields_are_omitted_not_invented(client, site):
    with client.app.state.session_factory() as db:
        report, _ = make_report(db, new_user(db), site["id"], synthetic=True, ph=None, foam="unknown")
        approve(db, report, new_user(db, Role.reviewer))
        bundle = export_report(db, report)
    codes = {e["resource"].get("code", {}).get("text") for e in bundle["entry"]}
    assert "Stream ph" not in codes and "Stream foam" not in codes


def test_benchmark_uses_isolated_database(client, site):
    from app.benchmark import evaluate
    from app.models.report import Report

    result = evaluate()
    assert result["cases"] == 22
    assert result["confusion_matrix"]["false_negative"] == 0
    assert result["confusion_matrix"]["false_positive"] == 0
    with client.app.state.session_factory() as db:
        assert db.scalar(select(Report)) is None
