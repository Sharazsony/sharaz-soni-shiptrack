from fastapi.testclient import TestClient


def _make_application(client: TestClient, auth_headers: dict[str, str], name: str = "checkout-api") -> int:
    resp = client.post(
        "/applications",
        json={"name": name, "repo_url": "https://github.com/acme/checkout-api"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_deployment(client: TestClient, auth_headers: dict[str, str]) -> None:
    app_id = _make_application(client, auth_headers)
    resp = client.post(
        "/deployments",
        json={"application_id": app_id, "version": "1.0.0", "environment": "prod"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["application_id"] == app_id


def test_bad_semver_rejected(client: TestClient, auth_headers: dict[str, str]) -> None:
    app_id = _make_application(client, auth_headers, name="billing-worker")
    resp = client.post(
        "/deployments",
        json={"application_id": app_id, "version": "v1.2", "environment": "prod"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert "version" in body["error"]["message"]


def test_deployment_not_found(client: TestClient) -> None:
    resp = client.get("/deployments/99999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"]


def test_write_requires_api_key(client: TestClient, auth_headers: dict[str, str]) -> None:
    app_id = _make_application(client, auth_headers, name="worker-svc")
    payload = {"application_id": app_id, "version": "1.0.0", "environment": "prod"}

    no_key = client.post("/deployments", json=payload)
    assert no_key.status_code == 401
    assert no_key.json()["error"]["code"] == "unauthorized"

    wrong_key = client.post(
        "/deployments", json=payload, headers={"X-API-Key": "wrong-key"}
    )
    assert wrong_key.status_code == 401
    assert wrong_key.json()["error"]["code"] == "unauthorized"

    reads_public = client.get("/deployments")
    assert reads_public.status_code == 200
