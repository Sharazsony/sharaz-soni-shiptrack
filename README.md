# ShipTrack

![CI](https://github.com/Sharazsony/sharaz-soni-shiptrack/actions/workflows/ci.yml/badge.svg)

ShipTrack is a simple FastAPI service for tracking application deployments across environments. It lets you register applications, record deployments, and perform rollbacks with clear API responses and built-in validation.

You can explore the API interactively at http://localhost:8000/docs once the app is running.

## What this project does

ShipTrack helps you manage:

- Applications: register apps with a name and repository URL
- Deployments: record versions deployed to dev, staging, or prod
- Rollbacks: revert a deployment to the previous successful version
- Health checks: confirm the API and database are both running

## Prerequisites

Make sure these are installed on your machine:

- Docker 26+
- Docker Compose v2
- Git

## Quickstart

Run the following commands:

```bash
git clone https://github.com/Sharazsony/sharaz-soni-shiptrack.git
cd sharaz-soni-shiptrack
cp .env.example .env
docker compose up --build -d
```

After the containers are up, check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "ok", "database": "ok"}
```

Open the API docs here:

```text
http://localhost:8000/docs
```

No database setup is required manually. The app creates the tables automatically when it starts.

## Environment variables

Copy [.env.example](.env.example) and fill in the values before starting the app.

| Variable | Required | Description | Example |
|---|---|---|---|
| `POSTGRES_USER` | Yes | PostgreSQL username | `appuser` |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password | `localdevpassword` |
| `POSTGRES_HOST` | Yes | PostgreSQL host | `db` |
| `POSTGRES_PORT` | Yes | PostgreSQL port | `5432` |
| `POSTGRES_DB` | Yes | PostgreSQL database name | `shiptrack` |
| `APP_ENV` | Yes | Environment label | `local` |
| `LOG_LEVEL` | Yes | Logging level | `INFO` |
| `API_KEY` | Yes | API key required for write requests | `local-dev-key` |
| `AUDIT_LOG_PATH` | Yes | Path for audit log file | `/app/logs/audit.log` |

> `DATABASE_URL` is created automatically from the PostgreSQL settings at runtime.

## API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | No | Check API and database health |
| `POST` | `/applications` | Yes | Create an application |
| `GET` | `/applications` | No | List applications |
| `POST` | `/deployments` | Yes | Create a deployment |
| `GET` | `/deployments` | No | List deployments |
| `GET` | `/deployments/{id}` | No | Get one deployment |
| `POST` | `/deployments/{id}/rollback` | Yes | Roll back a deployment |

### Example requests

Create an application:

```bash
curl -i -X POST http://localhost:8000/applications \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{"name": "checkout-api", "repo_url": "https://github.com/acme/checkout-api"}'
```

List applications:

```bash
curl http://localhost:8000/applications
```

Create a deployment:

```bash
curl -i -X POST http://localhost:8000/deployments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{"application_id": 1, "version": "1.4.0", "environment": "prod", "status": "succeeded"}'
```

Rollback a deployment:

```bash
curl -i -X POST http://localhost:8000/deployments/1/rollback \
  -H "X-API-Key: local-dev-key"
```

## Running tests

Run the tests inside the API container:

```bash
docker compose exec -T api pytest -q
docker compose exec -T api pytest --cov=app --cov-report=term-missing --cov-fail-under=60
```

## GitHub Actions secrets

To let the GitHub Actions workflow run successfully, add these repository secrets in GitHub under Settings → Secrets and variables → Actions:

- `CI_POSTGRES_USER`
- `CI_POSTGRES_PASSWORD`
- `CI_POSTGRES_DB`
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

You should add all 5 secrets if you want the full CI pipeline to run including Docker image publishing. If you only want to test the lint and test job, the Docker Hub secrets are optional.

## Useful scripts

- `scripts/backup_db.sh` — create a PostgreSQL backup
- `scripts/smoke_test.sh` — run an end-to-end API smoke test
- `scripts/all_status_codes.sh` — exercise the documented API status codes

Example:

```bash
./scripts/all_status_codes.sh
```
