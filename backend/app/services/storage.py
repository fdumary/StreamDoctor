import hashlib
import io
import logging
import re
import uuid
import warnings
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)


class LocalPhotoStorage:
    """Private local storage. Nothing in this directory is served as static content."""

    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def path(self, key: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{32}\.png", key) is None:
            raise ValueError("Invalid internal storage key")
        return self.directory / key

    def save(self, content: bytes) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        key = uuid.uuid4().hex + ".png"
        path = self.path(key)
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except OSError:
            path.unlink(missing_ok=True)
            raise
        return key

    def delete(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def cleanup(self, key: str):
        try:
            self.delete(key)
        except OSError:
            logger.exception("Could not remove orphan photo %s", key)


def normalize_photo(file: UploadFile, settings):
    raw = file.file.read(settings.max_photo_bytes + 1)
    if not raw:
        raise HTTPException(422, "Photo is empty")
    if len(raw) > settings.max_photo_bytes:
        raise HTTPException(413, "Photo exceeds the upload size limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(415, "Use a JPEG, PNG, or WebP photo")
                if getattr(image, "n_frames", 1) != 1:
                    raise HTTPException(415, "Animated images are not supported")
                if image.width * image.height > settings.max_photo_pixels:
                    raise HTTPException(413, "Photo dimensions exceed the pixel limit")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                oriented = ImageOps.exif_transpose(image)

                converted = oriented.convert(
                    "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
                )
                clean = Image.new(converted.mode, converted.size)
                clean.paste(converted)
                output = io.BytesIO()
                clean.save(output, format="PNG")
                content = output.getvalue()
                width, height = clean.size
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise HTTPException(413, "Photo dimensions exceed the pixel limit") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "File is not a supported, decodable photo") from exc
    if len(content) > settings.max_stored_photo_bytes:
        raise HTTPException(413, "Decoded photo exceeds the storage size limit")
    return content, hashlib.sha256(raw).hexdigest(), hashlib.sha256(content).hexdigest(), width, height
