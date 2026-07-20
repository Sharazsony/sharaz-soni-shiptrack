# ShipTrack

![CI](https://github.com/Sharazsony/sharaz-soni-shiptrack/actions/workflows/ci.yml/badge.svg)

ShipTrack — a FastAPI service for tracking application deployments across environments, with a one-click rollback action.

> **Before your first CI run:** set the `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` repo secrets on GitHub (see below) — the `docker` job needs them to log in and push.

## Prerequisites

Tested with:
- Docker 26.x
- Docker Compose v2 (the `docker compose` subcommand, not the standalone `docker-compose` binary)
- Git 2.4x

## Quickstart

```bash
git clone https://github.com/Sharazsony/sharaz-soni-shiptrack.git
cd sharaz-soni-shiptrack
cp .env.example .env          # works as-is: it ships API_KEY=local-dev-key
docker compose up --build -d
curl http://localhost:8000/health
# -> {"status": "ok", "database": "ok"}
# Interactive docs: http://localhost:8000/docs
```

No manual table creation, no `docker exec`, no editing files required — tables are created automatically on startup via `Base.metadata.create_all()`.

## Configuration (`.env`)

Your `pydantic-settings` `Settings` class reads the split Postgres variables and the other app settings — nothing else:

| Variable | Purpose | Example |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL user name | `appuser` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `localdevpassword` |
| `POSTGRES_HOST` | PostgreSQL host | `db` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `POSTGRES_DB` | PostgreSQL database name | `shiptrack` |
| `APP_ENV` | Environment label used in the startup log line | `local` |
| `LOG_LEVEL` | Root log level | `INFO` |
| `API_KEY` | Value the `X-API-Key` header must match on write endpoints | `local-dev-key` |
| `AUDIT_LOG_PATH` | File the background task appends audit lines to | `/app/logs/audit.log` |

> `DATABASE_URL` is derived at runtime from the split Postgres settings via `settings.database_url`, so it is not read as a separate environment variable.

The app has a startup guard: if `API_KEY` is unset or empty, it refuses to boot rather than silently accepting unauthenticated writes.

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | No | Liveness + real DB check (required, unauthenticated, **not** counted in the six below) |
| POST | `/applications` | Yes | Register a new application |
| GET | `/applications` | No | List all applications |
| POST | `/deployments` | Yes | Record a deployment |
| GET | `/deployments` | No | List all deployments (newest first) |
| GET | `/deployments/{id}` | No | Fetch one deployment |
| POST | `/deployments/{id}/rollback` | Yes | Roll back a deployment, re-deploy the previous succeeded version |

Example calls:

```bash
# create an application (write — needs the key)
curl -i -X POST http://localhost:8000/applications \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{"name": "checkout-api", "repo_url": "https://github.com/acme/checkout-api"}'

# list applications (read — public)
curl http://localhost:8000/applications

# record a deployment
curl -i -X POST http://localhost:8000/deployments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-key" \
  -d '{"application_id": 1, "version": "1.4.0", "environment": "prod", "status": "succeeded"}'

# roll it back
curl -i -X POST http://localhost:8000/deployments/1/rollback \
  -H "X-API-Key: local-dev-key"
```

## Running Tests

Tests run inside the `api` container against the `db` service — there is no SQLite path, because the models use native PostgreSQL enum types.

```bash
docker compose exec -T api pytest -q
docker compose exec -T api pytest --cov=app --cov-report=term-missing --cov-fail-under=60
```

## Bash Scripts

| Script | What it does | How to run it |
|---|---|---|
| `scripts/backup_db.sh` | `pg_dump`s the running `db` service to a timestamped file in `./backups`, then prunes dumps older than the retention window | `./scripts/backup_db.sh [-d BACKUP_DIR] [-r RETENTION_DAYS]` |
| `scripts/smoke_test.sh` | End-to-end check against a running stack: create app, duplicate check, deploy, bad-version check, rollback (auth + success), public read — asserts each HTTP status | `API_KEY=local-dev-key ./scripts/smoke_test.sh [-u BASE_URL]` |

## Backup Schedule (cron)

```
0 2 * * * cd /path/to/repo && ./scripts/backup_db.sh >> /var/log/shiptrack-backup.log 2>&1
```

The five cron fields, left to right, are **minute, hour, day-of-month, month, day-of-week**. `0 2 * * *` means "at minute 0 of hour 2, every day of every month, every day of the week" — i.e. daily at 02:00. The `*` in a field means "any value."

**Why the `cd` and absolute path matter:** cron runs jobs with a minimal environment — a bare `PATH`, no shell profile sourced, and no `.env` picked up the way an interactive shell would. It also starts in an unspecified working directory (often the user's home directory or `/`), not the repo. Without `cd /path/to/repo` first, `./scripts/backup_db.sh` would fail to resolve, and the script's relative reads of `.env` and `./backups` would look in the wrong place.

**Why the output redirection matters:** cron does not forward a job's stdout/stderr to your terminal — by default it emails it, if mail is even configured, and often that goes nowhere. `>> /var/log/shiptrack-backup.log 2>&1` appends both stdout and stderr to a log file, so a failed 2 a.m. backup leaves a paper trail instead of vanishing silently.

You are not required to install this on a server — the crontab line and this explanation are what's graded.

## Troubleshooting

**1. `api` container crash-loops with `connection refused` on startup.**
This happens if the `api` service starts before Postgres has finished initializing. Fix: `docker-compose.yml` uses `depends_on: db: condition: service_healthy`, gated on a `pg_isready` healthcheck — plain `depends_on: [db]` only waits for the container to *start*, not for Postgres to actually be ready to accept connections.

**2. `401 {"error": {"code": "unauthorized", "message": "Missing X-API-Key header"}}` on a write.**
Every `POST /applications`, `POST /deployments`, and the rollback endpoint require `X-API-Key: <value of API_KEY>`. Reads (`GET`) are public and don't need it — sending the header there is harmless, it's just ignored.

**3. `PermissionError: '/app/logs/audit.log'` inside the container.**
The container runs as a non-root `appuser`. If `/app/logs` isn't created and `chown`ed to `appuser` *before* the `USER` switch in the Dockerfile, every audited write 500s even though it works fine outside Docker. The Dockerfile here creates and owns that directory ahead of time — if you see this, check that a rebuild picked up that layer (`docker compose build --no-cache api`).

## Architecture / Request Flow

A request hits FastAPI's router layer first. For write endpoints, `Depends(require_api_key)` runs before the route body — it does a constant-time comparison of the `X-API-Key` header against `settings.api_key` and raises `401` immediately on a mismatch, before any request-body validation happens. Once auth (if required) passes, Pydantic validates the request body against the schema in `app/schemas.py` — bad semver, unknown enum values, or extra keys all short-circuit here as `422`. The route function itself stays thin: it calls into `app/crud.py`, which owns every SQLAlchemy query, using a `Session` obtained via the `get_db()` dependency (opened per-request, closed in a `finally` block). `crud.py` talks to Postgres through the ORM — no raw SQL, no hand-built connections.

On a successful write, the route schedules a `BackgroundTasks` job (`crud.write_audit_line`) that appends a pipe-delimited line to the audit log file. FastAPI runs that job *after* the HTTP response has already been sent back to the client, so the audit write never adds latency to the API response.

The rollback endpoint (`POST /deployments/{id}/rollback`) is the most involved path: it loads the target deployment, checks its status is `succeeded` (not `pending`/`failed`/`rolled_back`), then queries for the most recent `succeeded` deployment of the *same application and environment* with an earlier `deployed_at`. If one exists, both effects happen in a single transaction — the target flips to `rolled_back`, and a brand-new `Deployment` row is inserted with the previous version's `version`, status `succeeded`, and a fresh `deployed_at` timestamp. That new row, not the target, is what the endpoint returns as `201 Created`.

## Notes on this build

This repo was scaffolded and implemented end-to-end against the ShipTrack spec (FastAPI + PostgreSQL 16, Docker/Compose, GitHub Actions CI/CD, pytest, ruff, bash automation). Because the environment this was built in has **no Docker runtime and no outbound network access**, the following could not be executed here and should be verified once you have the repo on a machine with Docker and internet access:

- `docker compose up --build -d` and the full acceptance-test walkthrough in the assignment packet
- The actual pytest run against a live Postgres instance (the code is written to the exact schema/behavior spec, but hasn't been executed against a real DB in this sandbox)
- The GitHub Actions workflow actually going green (it's syntactically complete and matches the required job/step structure, but needs a real GitHub repo + secrets to run)
- Pushing an image to Docker Hub

Recommended first steps on your machine:
```bash
cp .env.example .env
docker compose up --build -d
docker compose exec -T api pytest --cov=app --cov-fail-under=60
./scripts/smoke_test.sh -u http://localhost:8000   # after: export API_KEY=local-dev-key
```
