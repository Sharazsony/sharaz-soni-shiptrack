from fastapi.testclient import TestClient


def test_audit_log_written(
    client: TestClient, auth_headers: dict[str, str], audit_log_path: str
) -> None:
    resp = client.post(
        "/applications",
        json={"name": "audit-app", "repo_url": "https://github.com/acme/audit-app"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    app_id = resp.json()["id"]

    with open(audit_log_path, encoding="utf-8") as f:
        lines = f.readlines()

    assert any(
        "CREATE_APPLICATION" in line and f"application_id={app_id}" in line
        for line in lines
    )
