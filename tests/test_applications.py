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
