# syntax=docker/dockerfile:1

# ---------- builder stage ----------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the installed packages and console scripts (uvicorn, etc.) from the
# builder stage's system site-packages -- avoids the "pip install --user"
# permission trap where /root/.local isn't readable by a non-root user.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create the non-root user AND the audit log directory it owns, before
# switching to that user. Without this, every audited write 500s inside
# the container even though it worked on the host (see README troubleshooting).
RUN useradd -m appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser tests ./tests

USER appuser

EXPOSE 8000

# Production CMD -- no --reload here. Local dev live-reload is layered on
# top of this by a `command:` override in docker-compose.yml, not baked
# into the image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
