"""Deployment resource routes, including the rollback action. Thin."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app import crud
from app.auth import require_api_key
from app.database import get_db
from app.models import DeploymentStatus
from app.schemas import DeploymentCreate, DeploymentOut

logger = logging.getLogger("shiptrack")

router = APIRouter(tags=["deployments"])


@router.post(
    "/deployments",
    response_model=DeploymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a deployment of an application to an environment",
    dependencies=[Depends(require_api_key)],
)
def create_deployment(
    payload: DeploymentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DeploymentOut:
    app_row = crud.get_application(db, payload.application_id)
    if app_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Application {payload.application_id} not found",
            },
        )

    dep = crud.create_deployment(
        db,
        application_id=payload.application_id,
        version=payload.version,
        environment=payload.environment,
        status=payload.status,
    )

    background_tasks.add_task(
        crud.write_audit_line,
        "CREATE_DEPLOYMENT",
        {
            "deployment_id": dep.id,
            "application_id": dep.application_id,
            "version": dep.version,
            "environment": dep.environment.value,
            "status": dep.status.value,
        },
    )
    logger.info(
        "deployment created id=%s app_id=%s env=%s",
        dep.id,
        dep.application_id,
        dep.environment.value,
    )
    return dep


@router.get(
    "/deployments",
    response_model=list[DeploymentOut],
    status_code=status.HTTP_200_OK,
    summary="List all deployments, newest first",
)
def list_deployments(db: Session = Depends(get_db)) -> list[DeploymentOut]:
    return crud.list_deployments(db)


@router.get(
    "/deployments/{deployment_id}",
    response_model=DeploymentOut,
    status_code=status.HTTP_200_OK,
    summary="Fetch one deployment by id",
)
def get_deployment(
    deployment_id: int = Path(ge=1),
    db: Session = Depends(get_db),
) -> DeploymentOut:
    dep = crud.get_deployment(db, deployment_id)
    if dep is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Deployment {deployment_id} not found",
            },
        )
    return dep


@router.post(
    "/deployments/{deployment_id}/rollback",
    response_model=DeploymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Roll back a deployment and re-deploy the previous succeeded version",
    dependencies=[Depends(require_api_key)],
)
def rollback_deployment(
    background_tasks: BackgroundTasks,
    deployment_id: int = Path(ge=1),
    db: Session = Depends(get_db),
) -> DeploymentOut:
    target = crud.get_deployment(db, deployment_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "not_found",
                "message": f"Deployment {deployment_id} not found",
            },
        )

    if target.status == DeploymentStatus.rolled_back:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_rollback",
                "message": f"Deployment {deployment_id} is already rolled back",
            },
        )

    if target.status != DeploymentStatus.succeeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_rollback",
                "message": (
                    f"Cannot roll back deployment {deployment_id} with status "
                    f"'{target.status.value}'; only 'succeeded' deployments can be "
                    "rolled back"
                ),
            },
        )

    previous = crud.get_previous_succeeded_deployment(
        db, target.application_id, target.environment, target.deployed_at
    )
    if previous is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "invalid_rollback",
                "message": (
                    f"No previous succeeded deployment for application "
                    f"{target.application_id} in environment "
                    f"'{target.environment.value}'"
                ),
            },
        )

    rolled_back_from_version = target.version
    new_row = crud.perform_rollback(db, target)

    background_tasks.add_task(
        crud.write_audit_line,
        "ROLLBACK",
        {
            "deployment_id": target.id,
            "application_id": target.application_id,
            "environment": target.environment.value,
            "rolled_back_from_version": rolled_back_from_version,
            "rolled_back_to_version": new_row.version,
            "new_deployment_id": new_row.id,
        },
    )
    logger.info(
        "deployment rolled back id=%s app_id=%s env=%s new_deployment_id=%s",
        target.id,
        target.application_id,
        target.environment.value,
        new_row.id,
    )
    return new_row
