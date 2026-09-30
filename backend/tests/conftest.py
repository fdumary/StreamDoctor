import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    api = create_app(
        Settings(
            _env_file=None,
            database_url=url,
            environment="test",
            auth_rate_limit=100,
            upload_dir=tmp_path / "photos",
        )
    )
    with TestClient(api) as test_client:
        yield test_client
    api.state.engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def credentials():
    return {"email": "waad@example.com", "password": "A-long-demo-password-123"}


@pytest.fixture
def account(client, credentials):
    result = client.post("/api/v1/auth/register", json={**credentials, "display_name": "Waad"})
    assert result.status_code == 201
    return result.json()


@pytest.fixture
def auth_headers(client, credentials, account):
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def reviewer_headers(client):
    from sqlalchemy import select

    from app.models.user import Role, User

    data = {"email": "reviewer@example.com", "password": "reviewer-demo-password", "display_name": "Reviewer"}
    assert client.post("/api/v1/auth/register", json=data).status_code == 201
    with client.app.state.session_factory() as db:
        user = db.scalar(select(User).where(User.email == data["email"]))
        user.role = Role.reviewer
        db.commit()
    response = client.post("/api/v1/auth/login", json={key: data[key] for key in ("email", "password")})
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def other_headers(client):
    data = {"email": "other@example.com", "password": "other-demo-password", "display_name": "Other"}
    assert client.post("/api/v1/auth/register", json=data).status_code == 201
    response = client.post("/api/v1/auth/login", json={key: data[key] for key in ("email", "password")})
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def site(client, reviewer_headers):
    response = client.post(
        "/api/v1/sites",
        headers=reviewer_headers,
        json={"name": "Test stream", "latitude": 32.3, "longitude": 35.3},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def report_data(site):
    from datetime import datetime, timezone

    return {
        "site_id": site["id"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "clarity": "cloudy",
        "smell": "unknown",
        "flow": "slow",
        "foam": "none",
        "visible_life": "none_observed",
        "water_color": "brown",
        "notes": "Field observation",
    }


@pytest.fixture
def report(client, auth_headers, report_data):
    response = client.post("/api/v1/reports", headers=auth_headers, json=report_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def photo_bytes():
    from io import BytesIO

    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (32, 24), "blue").save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def photo(client, auth_headers, report, photo_bytes):
    response = client.post(
        f"/api/v1/reports/{report['id']}/photos",
        headers=auth_headers,
        files={"file": ("stream.png", photo_bytes, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()
