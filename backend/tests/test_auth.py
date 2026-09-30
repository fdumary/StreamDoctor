from time import time

import pytest
from sqlalchemy import select

from app.core.security import token_digest, verify_password
from app.models.auth_session import AuthSession
from app.models.user import Role, User


def test_register_hashes_password_and_hides_it(client, account, credentials):
    assert account["role"] == "volunteer"
    assert "password" not in account and "password_hash" not in account
    with client.app.state.session_factory() as db:
        user = db.get(User, account["id"])
        assert user.password_hash != credentials["password"]
        assert verify_password(credentials["password"], user.password_hash)


def test_duplicate_email_case_insensitive(client, account, credentials):
    response = client.post(
        "/api/v1/auth/register", json={**credentials, "email": "WAAD@example.com", "display_name": "Other"}
    )
    assert response.status_code == 409


def test_cannot_register_as_reviewer(client, credentials):
    response = client.post(
        "/api/v1/auth/register", json={**credentials, "display_name": "Waad", "role": "reviewer"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("changes", [{"password": "short"}, {"email": "not-email"}, {"display_name": "   "}])
def test_invalid_input(client, credentials, changes):
    response = client.post("/api/v1/auth/register", json={**credentials, "display_name": "Waad", **changes})
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]
    assert credentials["password"] not in response.text


def test_login_me_and_hashed_session(client, auth_headers, account):
    response = client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == account["id"]
    raw = auth_headers["Authorization"].split()[1]
    with client.app.state.session_factory() as db:
        session = db.scalar(select(AuthSession))
        assert session.token_hash == token_digest(raw)
        assert session.token_hash != raw


def test_invalid_login_has_generic_message(client, account, credentials):
    wrong = client.post("/api/v1/auth/login", json={**credentials, "password": "wrong-password-long"})
    absent = client.post("/api/v1/auth/login", json={**credentials, "email": "absent@example.com"})
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json() == absent.json()


@pytest.mark.parametrize("header", [None, "Bearer nonsense", "Basic nonsense"])
def test_unauthorized(client, header):
    response = client.get("/api/v1/users/me", headers={"Authorization": header} if header else {})
    assert response.status_code == 401


def test_logout_revokes_session(client, auth_headers):
    assert client.post("/api/v1/auth/logout", headers=auth_headers).status_code == 204
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 401


def test_expired_session(client, auth_headers):
    with client.app.state.session_factory() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = int(time()) - 1
        db.commit()
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 401


def test_disabled_user(client, auth_headers, account):
    with client.app.state.session_factory() as db:
        db.get(User, account["id"]).is_active = False
        db.commit()
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 401


def test_reviewer_permissions_follow_database(client, auth_headers, account):
    path = "/api/v1/reviewer/access"
    assert client.get(path, headers=auth_headers).status_code == 403
    with client.app.state.session_factory() as db:
        db.get(User, account["id"]).role = Role.reviewer
        db.commit()
    assert client.get(path, headers=auth_headers).status_code == 200
    with client.app.state.session_factory() as db:
        db.get(User, account["id"]).role = Role.volunteer
        db.commit()
    assert client.get(path, headers=auth_headers).status_code == 403


def test_auth_rate_limit(client, credentials):
    client.app.state.auth_limiter.limit = 2
    for _ in range(2):
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 429
    assert response.headers["retry-after"]


def test_health_and_cors(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
    response = client.options("/api/v1/auth/login", headers=headers)
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    response = client.options("/api/v1/auth/login", headers=headers)
    assert "access-control-allow-origin" not in response.headers


def test_cli_role_change_revokes_sessions(client, auth_headers, account, monkeypatch):
    from app.cli import main

    monkeypatch.setattr("sys.argv", ["cli", "set-role", account["email"], "reviewer"])
    main()
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 401
    with client.app.state.session_factory() as db:
        assert db.get(User, account["id"]).role == Role.reviewer
