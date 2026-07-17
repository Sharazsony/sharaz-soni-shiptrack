"""API key authentication dependency for write endpoints."""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Guard write endpoints behind a constant-time X-API-Key comparison.

    FastAPI's Header() is case-insensitive by default, so `x-api-key` works
    too. Never returns 403 — always 401 on missing/empty/wrong key.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing X-API-Key header"},
        )
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Invalid API key"},
        )
