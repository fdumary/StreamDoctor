import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.demo import build_demo
from app.main import create_app


def test_demo_runs_with_real_login_photos_lens_and_fhir(tmp_path, monkeypatch):
    directory = tmp_path / "demo"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///do-not-use-this-database.db")
    manifest = build_demo(directory)
    assert manifest["trust_lens"] == {"trusted": "green", "unfiltered": "red"}
    accounts = json.loads((directory / "credentials.json").read_text())
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite:///" + (directory / "streamdoctor.db").as_posix(),
        upload_dir=directory / "photos",
    )
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            credentials = {k: accounts[0][k] for k in ("email", "password")}
            login = client.post("/api/v1/auth/login", json=credentials)
            assert login.status_code == 200
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            assert client.get("/health/ready").status_code == 200
            report_id = manifest["report_ids"][0]
            response = client.get(f"/api/v1/reports/{report_id}", headers=headers)
            assert response.status_code == 200
            path = response.json()["photos"][0]["download_path"]
            assert client.get(path, headers=headers).status_code == 200
            assert client.get(f"/api/v1/reports/{report_id}/fhir", headers=headers).status_code == 200
            card = client.get(
                f"/api/v1/sites/{manifest['site_id']}/diagnosis?synthetic=true", headers=headers
            ).json()
            assert card["trust_lens_changed"]
            real = client.get(f"/api/v1/sites/{manifest['site_id']}/diagnosis", headers=headers).json()
            assert real["trusted"]["status"] == "unknown"
    finally:
        app.state.engine.dispose()
    with pytest.raises(FileExistsError):
        build_demo(directory)
