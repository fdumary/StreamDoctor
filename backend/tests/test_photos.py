import hashlib
from io import BytesIO

from PIL import Image, PngImagePlugin
from sqlalchemy import select

from app.models.photo import Photo


def test_content_validated_metadata_removed_and_paths_hidden(client, auth_headers, report):
    output = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private_location", "do not retain")
    Image.new("RGB", (16, 16), "red").save(output, format="PNG", pnginfo=metadata)
    raw = output.getvalue()
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("../../escape.exe", raw, "application/octet-stream")},
    )
    assert response.status_code == 201
    body = response.json()
    assert "storage_key" not in body
    assert body["original_sha256"] == hashlib.sha256(raw).hexdigest()
    downloaded = client.get(body["download_path"], headers=auth_headers)
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == body["stored_sha256"]
    with Image.open(BytesIO(downloaded.content)) as image:
        assert "private_location" not in image.info
    assert client.get(body["download_path"]).status_code == 401


def test_duplicate_photo_and_delete_cleanup(client, auth_headers, report, photo, photo_bytes):
    path = f"/api/v1/reports/{report['id']}/photos"
    assert client.post(path, headers=auth_headers, files={"file": ("x.png", photo_bytes)}).status_code == 409
    assert len(list(client.app.state.settings.upload_dir.glob("*.png"))) == 1
    assert client.delete(path + "/" + photo["id"], headers=auth_headers).status_code == 204
    assert not list(client.app.state.settings.upload_dir.glob("*.png"))
    assert client.get(photo["download_path"], headers=auth_headers).status_code == 404


def test_invalid_empty_and_oversized_files(client, auth_headers, report, photo_bytes):
    path = f"/api/v1/reports/{report['id']}/photos"
    assert (
        client.post(
            path, headers=auth_headers, files={"file": ("fake.png", b"not a photo", "image/png")}
        ).status_code
        == 415
    )
    assert (
        client.post(path, headers=auth_headers, files={"file": ("empty.png", b"", "image/png")}).status_code
        == 422
    )
    client.app.state.settings.max_photo_bytes = 1024
    assert (
        client.post(path, headers=auth_headers, files={"file": ("big.png", b"x" * 1025)}).status_code == 413
    )
    client.app.state.settings.max_photo_pixels = 1
    assert (
        client.post(path, headers=auth_headers, files={"file": ("photo.png", photo_bytes)}).status_code == 413
    )


def test_maximum_photo_count(client, auth_headers, report, photo, photo_bytes):
    client.app.state.settings.max_photos_per_report = 1
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("photo.png", photo_bytes)},
    )
    assert response.status_code == 409


def test_photo_attribution_and_synthetic_rules(client, auth_headers, report, photo_bytes):
    base = f"/api/v1/reports/{report['id']}"
    files = {"file": ("photo.png", photo_bytes)}
    assert (
        client.post(
            base + "/photos", headers=auth_headers, files=files, data={"source": "open_license"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base + "/photos", headers=auth_headers, files=files, data={"source": "synthetic"}
        ).status_code
        == 422
    )
    assert client.patch(base, headers=auth_headers, json={"is_synthetic": True}).status_code == 200
    photo = client.post(base + "/photos", headers=auth_headers, files=files, data={"source": "synthetic"})
    assert photo.status_code == 201
    assert client.patch(base, headers=auth_headers, json={"is_synthetic": False}).status_code == 422
    assert client.delete(base + "/photos/" + photo.json()["id"], headers=auth_headers).status_code == 204
    data = {
        "source": "open_license",
        "attribution": "Photographer",
        "license_name": "CC BY 4.0",
        "source_url": "https://example.com/photo",
    }
    response = client.post(base + "/photos", headers=auth_headers, files=files, data=data)
    assert response.status_code == 201
    assert response.json()["attribution"] == "Photographer"


def test_disk_failure_does_not_save_photo(client, auth_headers, report, photo_bytes, monkeypatch):
    def fail(_):
        raise OSError("disk unavailable")

    monkeypatch.setattr(client.app.state.photo_storage, "save", fail)
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("photo.png", photo_bytes)},
    )
    assert response.status_code == 503
    with client.app.state.session_factory() as db:
        assert db.scalar(select(Photo)) is None


def test_database_failure_cleans_saved_photo(client, auth_headers, report, photo_bytes, monkeypatch):
    from fastapi import HTTPException

    def fail(_):
        raise HTTPException(409, "simulated database failure")

    monkeypatch.setattr("app.services.photos.commit_change", fail)
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("photo.png", photo_bytes)},
    )
    assert response.status_code == 409
    assert not list(client.app.state.settings.upload_dir.glob("*.png"))
    with client.app.state.session_factory() as db:
        assert db.scalar(select(Photo)) is None


def test_submitted_report_rejects_new_photo(client, auth_headers, report, photo, photo_bytes):
    base = f"/api/v1/reports/{report['id']}"
    assert client.post(base + "/submit", headers=auth_headers).status_code == 200
    assert (
        client.post(
            base + "/photos", headers=auth_headers, files={"file": ("photo.png", photo_bytes)}
        ).status_code
        == 409
    )


def test_photo_id_cannot_be_used_on_another_report(client, auth_headers, report_data, photo):
    other = client.post("/api/v1/reports", headers=auth_headers, json=report_data).json()
    path = f"/api/v1/reports/{other['id']}/photos/{photo['id']}/content"
    assert client.get(path, headers=auth_headers).status_code == 404


def test_missing_disk_file_returns_503(client, auth_headers, photo):
    for p in client.app.state.settings.upload_dir.glob("*.png"):
        p.unlink()
    assert client.get(photo["download_path"], headers=auth_headers).status_code == 503


def test_animated_image_rejected(client, auth_headers, report):
    output = BytesIO()
    frames = [Image.new("RGB", (10, 10), c) for c in ("red", "blue")]
    frames[0].save(output, format="PNG", save_all=True, append_images=frames[1:], duration=100, loop=0)
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("animated.png", output.getvalue())},
    )
    assert response.status_code == 415
