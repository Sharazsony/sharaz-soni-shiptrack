#!/usr/bin/env bash
set -uo pipefail
# Do NOT set -e — we WANT non-2xx responses, that's the whole point of this script.

# ============================================================================
# ShipTrack API — every documented status code, hit with real curl calls
# ============================================================================
# Requires: curl, jq
# Usage:    API_KEY=local-dev-key ./all_status_codes.sh
#           (defaults to local-dev-key / http://localhost:8000 if not set)
# ============================================================================

BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-local-dev-key}"
WRONG_KEY="totally-wrong-key"
STAMP="$(date +%s)"

sep() { echo; echo "──────────────────────────────────────────────────────────"; echo "$1"; echo "──────────────────────────────────────────────────────────"; }

req() {
  # req <expected_code> <description> <curl args...>
  local expected="$1" desc="$2"; shift 2
  echo
  echo ">>> [$desc] expecting $expected"
  local body code
  body=$(curl -s -o /tmp/_body.json -w '%{http_code}' "$@")
  code="$body"
  echo "STATUS: $code   (expected: $expected)"
  echo "BODY:"
  cat /tmp/_body.json | (jq . 2>/dev/null || cat)
  echo
}

# ============================================================================
sep "0. GET /health"
# ============================================================================

req 200 "health OK (db up)" \
  -X GET "${BASE_URL}/health"

echo
echo ">>> [health degraded - 503] requires stopping the db container manually:"
echo "    docker compose stop db"
echo "    curl -i ${BASE_URL}/health   # -> 503 {\"status\":\"degraded\",\"database\":\"unavailable\"}"
echo "    docker compose start db"

# ============================================================================
sep "1. POST /applications"
# ============================================================================

APP_NAME="smoke-app-${STAMP}"

req 201 "create application - success" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"${APP_NAME}\", \"repo_url\": \"https://github.com/acme/${APP_NAME}\"}"

APP_ID=$(jq -r '.id' /tmp/_body.json 2>/dev/null)

req 401 "create application - missing X-API-Key header" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"no-key-${STAMP}\", \"repo_url\": \"https://github.com/acme/x\"}"

req 401 "create application - empty X-API-Key header" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: " \
  -d "{\"name\": \"empty-key-${STAMP}\", \"repo_url\": \"https://github.com/acme/x\"}"

req 401 "create application - wrong X-API-Key" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${WRONG_KEY}" \
  -d "{\"name\": \"wrong-key-${STAMP}\", \"repo_url\": \"https://github.com/acme/x\"}"

req 409 "create application - duplicate name" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"${APP_NAME}\", \"repo_url\": \"https://github.com/acme/${APP_NAME}\"}"

req 422 "create application - missing repo_url" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"missing-field-${STAMP}\"}"

req 422 "create application - blank name" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"   \", \"repo_url\": \"https://github.com/acme/x\"}"

req 422 "create application - name > 100 chars" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"$(printf 'a%.0s' {1..101})\", \"repo_url\": \"https://github.com/acme/x\"}"

req 422 "create application - repo_url not https://" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"bad-url-${STAMP}\", \"repo_url\": \"http://github.com/acme/x\"}"

req 422 "create application - extra/unknown key (extra=forbid)" \
  -X POST "${BASE_URL}/applications" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"name\": \"extra-key-${STAMP}\", \"repo_url\": \"https://github.com/acme/x\", \"id\": 999}"

# ============================================================================
sep "2. GET /applications"
# ============================================================================

req 200 "list applications - public, no key needed" \
  -X GET "${BASE_URL}/applications"

# ============================================================================
sep "3. POST /deployments"
# ============================================================================

req 201 "create deployment (v1.0.0, prod, succeeded) - success" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.0\", \"environment\": \"prod\", \"status\": \"succeeded\"}"
DEPLOY_V1_ID=$(jq -r '.id' /tmp/_body.json 2>/dev/null)

req 201 "create deployment (v2.0.0, prod, succeeded) - success" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"2.0.0\", \"environment\": \"prod\", \"status\": \"succeeded\"}"
DEPLOY_V2_ID=$(jq -r '.id' /tmp/_body.json 2>/dev/null)

req 401 "create deployment - missing X-API-Key" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.1\", \"environment\": \"prod\"}"

req 401 "create deployment - wrong X-API-Key" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${WRONG_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.1\", \"environment\": \"prod\"}"

req 404 "create deployment - application_id does not exist" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"application_id": 999999, "version": "1.0.0", "environment": "prod"}'

req 422 "create deployment - bad semver (v1.4)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"v1.4\", \"environment\": \"prod\"}"

req 422 "create deployment - bad semver (1.4, missing patch)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.4\", \"environment\": \"prod\"}"

req 422 "create deployment - bad semver (leading zero 1.04.0)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.04.0\", \"environment\": \"prod\"}"

req 422 "create deployment - bad semver (pre-release suffix 1.4.0-rc1)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.4.0-rc1\", \"environment\": \"prod\"}"

req 422 "create deployment - unknown environment (production)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.0\", \"environment\": \"production\"}"

req 422 "create deployment - status rolled_back not allowed on create" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.0\", \"environment\": \"prod\", \"status\": \"rolled_back\"}"

req 422 "create deployment - application_id <= 0" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{"application_id": 0, "version": "1.0.0", "environment": "prod"}'

req 422 "create deployment - missing required field (version)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"environment\": \"prod\"}"

req 422 "create deployment - extra key (deployed_at sent by client)" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.0\", \"environment\": \"prod\", \"deployed_at\": \"2026-01-01T00:00:00Z\"}"

# ============================================================================
sep "4. GET /deployments"
# ============================================================================

req 200 "list deployments - public, no key needed" \
  -X GET "${BASE_URL}/deployments"

# ============================================================================
sep "5. GET /deployments/{deployment_id}"
# ============================================================================

req 200 "get deployment by id - success" \
  -X GET "${BASE_URL}/deployments/${DEPLOY_V1_ID}"

req 404 "get deployment - id does not exist" \
  -X GET "${BASE_URL}/deployments/999999"

req 422 "get deployment - non-integer id" \
  -X GET "${BASE_URL}/deployments/abc"

# ============================================================================
sep "6. POST /deployments/{deployment_id}/rollback"
# ============================================================================

req 401 "rollback - missing X-API-Key" \
  -X POST "${BASE_URL}/deployments/${DEPLOY_V2_ID}/rollback"

req 404 "rollback - id does not exist" \
  -X POST "${BASE_URL}/deployments/999999/rollback" \
  -H "X-API-Key: ${API_KEY}"

req 422 "rollback - non-integer id" \
  -X POST "${BASE_URL}/deployments/abc/rollback" \
  -H "X-API-Key: ${API_KEY}"

# --- 409: target status is pending (create a fresh pending deployment) ---
req 201 "create deployment (pending, staging) - setup for 409 test" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"9.9.9\", \"environment\": \"staging\", \"status\": \"pending\"}"
DEPLOY_PENDING_ID=$(jq -r '.id' /tmp/_body.json 2>/dev/null)

req 409 "rollback - target status is 'pending' (invalid_rollback)" \
  -X POST "${BASE_URL}/deployments/${DEPLOY_PENDING_ID}/rollback" \
  -H "X-API-Key: ${API_KEY}"

# --- 409: no previous succeeded deployment (single succeeded row, isolated env) ---
req 201 "create deployment (dev, succeeded, only one in this env) - setup for 409 test" \
  -X POST "${BASE_URL}/deployments" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "{\"application_id\": ${APP_ID}, \"version\": \"1.0.0\", \"environment\": \"dev\", \"status\": \"succeeded\"}"
DEPLOY_ONLY_DEV_ID=$(jq -r '.id' /tmp/_body.json 2>/dev/null)

req 409 "rollback - no previous succeeded deployment for app+env (invalid_rollback)" \
  -X POST "${BASE_URL}/deployments/${DEPLOY_ONLY_DEV_ID}/rollback" \
  -H "X-API-Key: ${API_KEY}"

# --- 201: successful rollback (v2.0.0 prod -> falls back to v1.0.0 prod) ---
req 201 "rollback - success (v2.0.0 prod rolls back to v1.0.0 prod)" \
  -X POST "${BASE_URL}/deployments/${DEPLOY_V2_ID}/rollback" \
  -H "X-API-Key: ${API_KEY}"

# --- 409: target already rolled_back (rollback the same one again) ---
req 409 "rollback - target already rolled_back (invalid_rollback)" \
  -X POST "${BASE_URL}/deployments/${DEPLOY_V2_ID}/rollback" \
  -H "X-API-Key: ${API_KEY}"

sep "DONE — every documented status code has been exercised above"
