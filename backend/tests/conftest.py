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
    api = create_app(Settings(_env_file=None, database_url=url, environment="test", auth_rate_limit=100))
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
