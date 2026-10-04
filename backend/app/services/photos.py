from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.photo import Photo
from app.models.report import utcnow
from app.schemas.photos import PhotoMetadata
from app.services.reports import commit_change
from app.services.storage import normalize_photo


def add_photo(db, report, file: UploadFile, metadata: PhotoMetadata, storage, settings):
    if metadata.source == "synthetic" and not report.is_synthetic:
        raise HTTPException(422, "Synthetic photos require is_synthetic=true on the report")
    count = db.scalar(select(func.count()).select_from(Photo).where(Photo.report_id == report.id))
    if count >= settings.max_photos_per_report:
        raise HTTPException(409, "Maximum number of photos reached")
    content, original_hash, stored_hash, width, height = normalize_photo(file, settings)
    duplicate = db.scalar(
        select(Photo.id).where(Photo.report_id == report.id, Photo.original_sha256 == original_hash)
    )
    if duplicate:
        raise HTTPException(409, "This photo is already attached to the report")

    report.updated_at = utcnow()
    from sqlalchemy.orm.exc import StaleDataError

    try:
        db.flush()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(409, "Report changed concurrently. Reload and try again.") from exc
    try:
        key = storage.save(content)
    except OSError as exc:
        db.rollback()
        raise HTTPException(503, "Photo storage is unavailable") from exc
    values = metadata.model_dump(mode="json")
    photo = Photo(
        report_id=report.id,
        storage_key=key,
        original_sha256=original_hash,
        stored_sha256=stored_hash,
        byte_size=len(content),
        width=width,
        height=height,
        **values,
    )
    db.add(photo)
    try:
        commit_change(db)
    except Exception as exc:
        db.rollback()
        storage.cleanup(key)
        if isinstance(exc, IntegrityError):
            raise HTTPException(
                409, "Photo already attached or report changed. Reload and try again."
            ) from exc
        raise
    db.refresh(photo)
    return photo


def get_photo(db, report_id: str, photo_id: str):
    photo = db.get(Photo, photo_id)
    if photo is None or photo.report_id != report_id:
        raise HTTPException(404, "Photo not found")
    return photo


def delete_photo(db, report, photo, storage):
    key = photo.storage_key
    report.updated_at = utcnow()
    db.delete(photo)
    commit_change(db)

    storage.cleanup(key)
