"""Application resource routes. Thin — delegates to app.crud."""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.auth import require_api_key
from app.database import get_db
from app.schemas import ApplicationCreate, ApplicationOut

logger = logging.getLogger("shiptrack")

router = APIRouter(tags=["applications"])


@router.post(
    "/applications",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new application",
    dependencies=[Depends(require_api_key)],
)
def create_application(
    payload: ApplicationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    existing = crud.get_application_by_name(db, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_name",
                "message": f"Application '{payload.name}' already exists",
            },
        )

    app_row = crud.create_application(db, payload.name, payload.repo_url)

    background_tasks.add_task(
        crud.write_audit_line,
        "CREATE_APPLICATION",
        {"application_id": app_row.id, "name": app_row.name},
    )
    logger.info("application created id=%s name=%s", app_row.id, app_row.name)
    return app_row


@router.get(
    "/applications",
    response_model=list[ApplicationOut],
    status_code=status.HTTP_200_OK,
    summary="List all applications",
)
def list_applications(db: Session = Depends(get_db)) -> list[ApplicationOut]:
    return crud.list_applications(db)
