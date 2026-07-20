from fastapi.testclient import TestClient


def test_create_application(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/applications",
        json={"name": "checkout-api", "repo_url": "https://github.com/acme/checkout-api"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == "checkout-api"
    assert body["repo_url"] == "https://github.com/acme/checkout-api"
    assert "created_at" in body
    assert body["created_at"].endswith("+00:00")


def test_create_deployment_returns_timezone_aware_timestamp(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    app_resp = client.post(
        "/applications",
        json={"name": "checkout-api-deploy", "repo_url": "https://github.com/acme/checkout-api-deploy"},
        headers=auth_headers,
    )
    app_id = app_resp.json()["id"]

    dep_resp = client.post(
        "/deployments",
        json={
            "application_id": app_id,
            "version": "1.2.3",
            "environment": "prod",
            "status": "succeeded",
        },
        headers=auth_headers,
    )

    assert dep_resp.status_code == 201
    body = dep_resp.json()
    assert body["deployed_at"].endswith("+00:00")
