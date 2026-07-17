"""All SQLAlchemy queries and business logic live here. Routers stay thin."""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, Deployment, DeploymentStatus, Environment

logger = logging.getLogger("shiptrack")


# ---------------------------------------------------------------------------
# Audit log (background task target — never call this inline in a request)
# ---------------------------------------------------------------------------
def write_audit_line(action: str, fields: dict[str, object]) -> None:
    """Append a single pipe-delimited audit line. Never logs secrets."""
    path = settings.audit_log_path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ts = datetime.now(UTC).isoformat()
    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    line = f"{ts} | {action} | {kv}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
def get_application_by_name(db: Session, name: str) -> Application | None:
    return db.execute(
        select(Application).where(Application.name == name)
    ).scalar_one_or_none()


def get_application(db: Session, application_id: int) -> Application | None:
    return db.get(Application, application_id)


def create_application(db: Session, name: str, repo_url: str) -> Application:
    app_row = Application(name=name, repo_url=repo_url)
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    return app_row


def list_applications(db: Session) -> list[Application]:
    return list(
        db.execute(select(Application).order_by(Application.id.asc())).scalars().all()
    )


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------
def get_deployment(db: Session, deployment_id: int) -> Deployment | None:
    return db.get(Deployment, deployment_id)


def create_deployment(
    db: Session,
    application_id: int,
    version: str,
    environment: Environment,
    status: DeploymentStatus,
) -> Deployment:
    row = Deployment(
        application_id=application_id,
        version=version,
        environment=environment,
        status=status,
        deployed_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_deployments(db: Session) -> list[Deployment]:
    return list(
        db.execute(
            select(Deployment).order_by(
                Deployment.deployed_at.desc(), Deployment.id.desc()
            )
        )
        .scalars()
        .all()
    )


def get_previous_succeeded_deployment(
    db: Session, application_id: int, environment: Environment, before: datetime
) -> Deployment | None:
    """The most recent succeeded deployment for the same app+env strictly
    before `before`. Ties broken by highest id."""
    stmt = (
        select(Deployment)
        .where(
            Deployment.application_id == application_id,
            Deployment.environment == environment,
            Deployment.status == DeploymentStatus.succeeded,
            Deployment.deployed_at < before,
        )
        .order_by(Deployment.deployed_at.desc(), Deployment.id.desc())
    )
    return db.execute(stmt).scalars().first()


def perform_rollback(db: Session, target: Deployment) -> Deployment:
    """Mark `target` rolled_back and create+return a new succeeded row
    pointing at the previous succeeded version. Single transaction.

    Caller is responsible for precondition checks (status, previous exists)
    before calling this — this function assumes both have already passed.
    """
    previous = get_previous_succeeded_deployment(
        db, target.application_id, target.environment, target.deployed_at
    )
    assert previous is not None  # precondition checked by caller

    target.status = DeploymentStatus.rolled_back

    new_row = Deployment(
        application_id=target.application_id,
        environment=target.environment,
        version=previous.version,
        status=DeploymentStatus.succeeded,
        deployed_at=datetime.now(UTC),
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    db.refresh(target)
    return new_row
