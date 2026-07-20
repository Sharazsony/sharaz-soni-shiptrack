"""Pydantic v2 request/response models only. No SQLAlchemy classes here."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer

from app.models import DeploymentStatus, Environment

_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

# status values a client may set on create; "rolled_back" is server-only
CreatableStatus = DeploymentStatus


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    repo_url: str = Field(max_length=255)

    @field_validator("name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must contain at least one non-whitespace character")
        if len(stripped) > 100:
            raise ValueError("name must be at most 100 characters")
        return stripped

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        if not re.match(r"^https://\S+$", v):
            raise ValueError("repo_url must start with https:// and contain no whitespace")
        return v


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_url: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: datetime | str | None) -> datetime | None:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------
class DeploymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: int = Field(gt=0)
    version: str = Field(max_length=32)
    environment: Environment
    status: CreatableStatus = DeploymentStatus.pending

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        if not _SEMVER_RE.match(v):
            raise ValueError(
                "version must be semver MAJOR.MINOR.PATCH, e.g. 1.4.0"
            )
        return v

    @field_validator("status")
    @classmethod
    def reject_rolled_back(cls, v: DeploymentStatus) -> DeploymentStatus:
        if v == DeploymentStatus.rolled_back:
            raise ValueError(
                "status 'rolled_back' cannot be set directly; use the rollback endpoint"
            )
        return v


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    version: str
    environment: Environment
    status: DeploymentStatus
    deployed_at: datetime

    @field_serializer("deployed_at")
    def serialize_deployed_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    @field_validator("deployed_at", mode="before")
    @classmethod
    def normalize_deployed_at(cls, value: datetime | str | None) -> datetime | None:
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


# ---------------------------------------------------------------------------
# Error envelope (ShipTrack error shape)
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
