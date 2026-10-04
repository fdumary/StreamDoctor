from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.dependencies import CurrentUser, Database
from app.services.fhir_export import export_report, validate_bundle
from app.services.reports import get_report

router = APIRouter(tags=["FHIR test export"])


@router.get("/reports/{report_id}/fhir", response_class=JSONResponse)
def download(report_id: str, db: Database, user: CurrentUser):
    bundle = export_report(db, get_report(db, report_id, user))
    return JSONResponse(
        bundle,
        media_type="application/fhir+json",
        headers={"Content-Disposition": 'attachment; filename="streamdoctor-synthetic-fhir.json"'},
    )


@router.get("/reports/{report_id}/fhir/validation")
def validation(report_id: str, db: Database, user: CurrentUser):
    return validate_bundle(export_report(db, get_report(db, report_id, user)))
