import json
from functools import lru_cache
from html import escape
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from jsonschema import Draft6Validator

from app.services.assessments import current_assessment
from app.services.diagnosis import utc

VERSION = "4.0.1"
TAG = {
    "system": "https://streamdoctor.example.org/tags",
    "code": "synthetic",
    "display": "Synthetic test data",
}
FIELDS = ("clarity", "smell", "flow", "foam", "visible_life", "water_color", "ph")


def identifier(value):
    return str(uuid5(NAMESPACE_URL, "https://streamdoctor.example.org/export/" + value))


def reference(resource_id):
    return {"reference": "urn:uuid:" + resource_id}


def resource(kind, resource_id, narrative):
    return {
        "resourceType": kind,
        "id": resource_id,
        "meta": {"tag": [TAG]},
        "text": {
            "status": "generated",
            "div": '<div xmlns="http://www.w3.org/1999/xhtml"><p>' + escape(narrative) + "</p></div>",
        },
    }


def export_report(db, report):
    if not report.is_synthetic:
        raise HTTPException(403, "FHIR test export is restricted to synthetic reports")
    assessment, case = current_assessment(db, report.id)
    if case.status != "approved":
        raise HTTPException(409, "An independent expert must approve the report before FHIR export")
    from sqlalchemy import select

    from app.models.review import Review

    review = db.scalar(select(Review).where(Review.report_id == report.id))
    if review is None or review.reviewer_id == report.contributor_id:
        raise HTTPException(409, "Independent review evidence is missing")
    location_id = identifier("site/" + report.site_id)
    location = resource(
        "Location",
        location_id,
        "Fictional stream location for synthetic testing. No real coordinates exported.",
    )
    location.update({"status": "active", "name": "Synthetic stream site", "mode": "instance"})
    resources = [location]
    results = []
    observed = utc(report.observed_at).isoformat()
    issued = utc(review.created_at).isoformat()
    for field in FIELDS:
        value = getattr(report, field)
        if value in (None, "unknown"):
            continue
        item_id = identifier(report.id + "/" + field)
        item = resource("Observation", item_id, f"Synthetic stream {field.replace('_', ' ')}: {value}.")
        item.update(
            {
                "status": "final",
                "code": {"text": "Stream " + field.replace("_", " ")},
                "subject": reference(location_id),
                "effectiveDateTime": observed,
                "issued": issued,
            }
        )
        if field == "ph":
            item["valueQuantity"] = {
                "value": value,
                "unit": "pH",
                "system": "http://unitsofmeasure.org",
                "code": "[pH]",
            }
        else:
            item["valueCodeableConcept"] = {"text": value.replace("_", " ")}
        resources.append(item)
        results.append(reference(item_id))
    if not results:
        raise HTTPException(409, "No known observations are available for export")
    conclusion = f"Synthetic environmental observations independently reviewed. Prototype trust score {assessment.score}/100; evidence coverage {assessment.evidence_coverage:.0%}. This is not a clinical diagnosis or a water-safety certification."
    diagnostic = resource("DiagnosticReport", identifier(report.id + "/diagnostic"), conclusion)
    diagnostic.update(
        {
            "status": "final",
            "code": {"text": "Stream environmental observation report"},
            "subject": reference(location_id),
            "effectiveDateTime": observed,
            "issued": issued,
            "result": results,
            "conclusion": conclusion,
        }
    )
    resources.append(diagnostic)
    bundle = {
        "resourceType": "Bundle",
        "id": identifier(report.id + "/bundle/" + assessment.id),
        "meta": {"tag": [TAG]},
        "type": "collection",
        "entry": [{"fullUrl": "urn:uuid:" + item["id"], "resource": item} for item in resources],
    }
    outcome = validate_bundle(bundle)
    if not outcome["valid"]:
        raise HTTPException(500, "Generated FHIR bundle failed local validation")
    return bundle


@lru_cache
def validator():
    schema = json.loads((Path(__file__).resolve().parents[1] / "fhir" / "fhir.schema.json").read_text())
    return Draft6Validator(schema)


def validate_bundle(bundle):
    errors = []
    for error in validator().iter_errors(bundle):
        errors.append({"path": "/" + "/".join(map(str, error.absolute_path)), "message": error.message[:300]})
        if len(errors) >= 20:
            break
    if not errors:
        entries = bundle.get("entry", [])
        urls = [entry.get("fullUrl") for entry in entries]
        if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection":
            errors.append({"path": "/", "message": "Expected a collection Bundle"})
        if len(urls) != len(set(urls)) or any(not url for url in urls):
            errors.append({"path": "/entry", "message": "Every entry needs a unique fullUrl"})
        for entry in entries:
            item = entry["resource"]
            if item["resourceType"] in ("Observation", "DiagnosticReport") and item.get("status") != "final":
                errors.append(
                    {"path": "/entry", "message": "Exported observations and reports require final status"}
                )
            refs = ([item["subject"]] if "subject" in item else []) + item.get("result", [])
            for ref in refs:
                if ref.get("reference") not in urls:
                    errors.append({"path": "/entry", "message": "Unresolved subject or result reference"})
    return {
        "valid": not errors,
        "fhir_version": VERSION,
        "validator": "HL7 R4 JSON Schema (Draft 6) and local reference checks",
        "scope": "Structural validation only; terminology bindings, profiles, and all FHIRPath invariants are not checked.",
        "errors": errors,
    }
