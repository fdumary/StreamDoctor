from app.services.sites import seed_demo_sites


def test_sites_permissions_validation_and_search(client, auth_headers, reviewer_headers, site):
    body = {"name": " New Stream ", "latitude": 30, "longitude": 35}
    assert client.get("/api/v1/sites").status_code == 401
    assert client.post("/api/v1/sites", headers=auth_headers, json=body).status_code == 403
    assert (
        client.post("/api/v1/sites", headers=reviewer_headers, json={**body, "latitude": 91}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/sites", headers=reviewer_headers, json={**body, "name": "  "}).status_code == 422
    )
    assert client.post("/api/v1/sites", headers=reviewer_headers, json=body).json()["name"] == "New Stream"
    page = client.get("/api/v1/sites?q=Test&limit=1", headers=auth_headers).json()
    assert page["total"] == 1 and page["items"][0]["id"] == site["id"]
    assert client.get("/api/v1/sites?q=%25", headers=auth_headers).json()["total"] == 0
    assert client.get("/api/v1/sites/missing", headers=auth_headers).status_code == 404


def test_demo_sites_are_idempotent_and_reports_must_be_synthetic(client, auth_headers, report_data):
    with client.app.state.session_factory() as db:
        assert seed_demo_sites(db) == 2
        assert seed_demo_sites(db) == 0
    data = {**report_data, "site_id": "00000000-0000-4000-8000-000000000001"}
    assert client.post("/api/v1/reports", headers=auth_headers, json=data).status_code == 422
    response = client.post("/api/v1/reports", headers=auth_headers, json={**data, "is_synthetic": True})
    assert response.status_code == 201
    report_id = response.json()["id"]
    assert (
        client.patch(
            f"/api/v1/reports/{report_id}", headers=auth_headers, json={"is_synthetic": False}
        ).status_code
        == 422
    )
