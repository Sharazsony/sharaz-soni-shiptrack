from fastapi.testclient import TestClient


def _make_application(client: TestClient, auth_headers: dict[str, str], name: str) -> int:
    resp = client.post(
        "/applications",
        json={"name": name, "repo_url": "https://github.com/acme/repo"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _make_deployment(
    client: TestClient,
    auth_headers: dict[str, str],
    app_id: int,
    version: str,
    environment: str = "prod",
    dep_status: str = "succeeded",
) -> dict:
    resp = client.post(
        "/deployments",
        json={
            "application_id": app_id,
            "version": version,
            "environment": environment,
            "status": dep_status,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


def test_rollback_creates_new_deployment(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    app_id = _make_application(client, auth_headers, "rollback-app")
    _make_deployment(client, auth_headers, app_id, "1.0.0")
    v2 = _make_deployment(client, auth_headers, app_id, "2.0.0")

    before_count = len(client.get("/deployments").json())

    resp = client.post(f"/deployments/{v2['id']}/rollback", headers=auth_headers)
    assert resp.status_code == 201
    new_row = resp.json()
    assert new_row["version"] == "1.0.0"
    assert new_row["environment"] == "prod"
    assert new_row["status"] == "succeeded"

    v2_after = client.get(f"/deployments/{v2['id']}").json()
    assert v2_after["status"] == "rolled_back"

    after_count = len(client.get("/deployments").json())
    assert after_count == before_count + 1


def test_rollback_no_previous_version(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    app_id = _make_application(client, auth_headers, "single-deploy-app")
    only = _make_deployment(client, auth_headers, app_id, "1.0.0")

    before_count = len(client.get("/deployments").json())

    resp = client.post(f"/deployments/{only['id']}/rollback", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_rollback"

    after_count = len(client.get("/deployments").json())
    assert after_count == before_count
