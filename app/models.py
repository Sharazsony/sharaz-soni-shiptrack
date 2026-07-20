"""SQLAlchemy ORM models only. No Pydantic classes belong in this file."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Environment(str, enum.Enum):  # noqa: UP042
    dev = "dev"
    staging = "staging"
    prod = "prod"


class DeploymentStatus(str, enum.Enum):  # noqa: UP042
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    rolled_back = "rolled_back"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    repo_url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    deployments: Mapped[list[Deployment]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (
        Index("ix_deployments_application_id", "application_id"),
        Index(
            "ix_deployments_lookup",
            "application_id",
            "environment",
            "status",
            "deployed_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[Environment] = mapped_column(
        SAEnum(
            Environment,
            name="environment_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(
            DeploymentStatus,
            name="deployment_status_enum",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=DeploymentStatus.pending,
        server_default=DeploymentStatus.pending.value,
    )
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    application: Mapped[Application] = relationship(back_populates="deployments")