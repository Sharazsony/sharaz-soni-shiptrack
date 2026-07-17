"""FastAPI app entrypoint: startup, /health, exception handlers, routers."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import Base, engine, get_db
from app.routers import applications, deployments

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("shiptrack")

app = FastAPI(title="ShipTrack API", version="1.0.0")

app.include_router(applications.router)
app.include_router(deployments.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    logger.info(
        "ShipTrack API starting, env=%s, db=connected", settings.app_env
    )


@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Liveness and DB connectivity check",
    include_in_schema=True,
)
def health() -> JSONResponse:
    try:
        db = next(get_db())
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": "ok"},
        )
    except Exception:  # noqa: BLE001 - health check must never 500
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "unavailable"},
        )


# ---------------------------------------------------------------------------
# Exception handlers — exactly two, producing the shared error envelope.
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0]
    loc = ".".join(str(p) for p in first["loc"])
    reason = first["msg"]
    if reason.startswith("Value error, "):
        reason = reason[len("Value error, "):]
    message = f"{loc}: {reason}"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "validation_error", "message": message}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        code, message = detail["code"], detail["message"]
    else:
        code, message = "error", str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
    )
