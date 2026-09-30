from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from app.api.dependencies import CurrentUser, Database
from app.schemas.photos import PhotoMetadata, PhotoResponse
from app.services import photos, reports

router = APIRouter(prefix="/reports/{report_id}/photos", tags=["Report photos"])


@router.post("", response_model=PhotoResponse, status_code=201)
def upload_photo(
    report_id: str,
    db: Database,
    user: CurrentUser,
    request: Request,
    file: Annotated[UploadFile, File()],
    source: Annotated[str, Form(max_length=30)] = "own",
    attribution: Annotated[str | None, Form(max_length=500)] = None,
    license_name: Annotated[str | None, Form(max_length=200)] = None,
    source_url: Annotated[str | None, Form(max_length=2000)] = None,
):
    report = reports.get_report(db, report_id, user, write=True)
    try:
        metadata = PhotoMetadata(
            source=source, attribution=attribution, license_name=license_name, source_url=source_url
        )
    except ValidationError as exc:
        raise HTTPException(
            422, "Invalid photo metadata; open_license requires credit, license, and an HTTP(S) source URL"
        ) from exc
    photo = photos.add_photo(
        db, report, file, metadata, request.app.state.photo_storage, request.app.state.settings
    )
    return reports.photo_response(photo)


@router.get("/{photo_id}/content", response_class=FileResponse)
def download_photo(report_id: str, photo_id: str, db: Database, user: CurrentUser, request: Request):
    reports.get_report(db, report_id, user)
    photo = photos.get_photo(db, report_id, photo_id)
    path = request.app.state.photo_storage.path(photo.storage_key)
    if not path.is_file():
        raise HTTPException(503, "Photo file is temporarily unavailable")
    return FileResponse(
        path, media_type="image/png", filename=f"{photo.id}.png", content_disposition_type="inline"
    )


@router.delete("/{photo_id}", status_code=204)
def delete_photo(report_id: str, photo_id: str, db: Database, user: CurrentUser, request: Request):
    report = reports.get_report(db, report_id, user, write=True)
    photo = photos.get_photo(db, report_id, photo_id)
    photos.delete_photo(db, report, photo, request.app.state.photo_storage)
    return Response(status_code=204)
