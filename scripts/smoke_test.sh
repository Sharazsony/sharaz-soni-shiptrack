#!/usr/bin/env bash
set -euo pipefail

# smoke_test.sh — end-to-end check of a running ShipTrack stack.
# Parses JSON responses with python3 -m json.tool / a tiny inline python
# snippet (no jq dependency assumed).
#
# Usage: ./scripts/smoke_test.sh [-u BASE_URL] [-h]
#   default: BASE_URL=http://localhost:8000
#   requires API_KEY in the environment (never hardcode it)

BASE_URL="http://localhost:8000"
PASS_COUNT=0
FAIL_COUNT=0
declare -a RESULTS=()

usage() {
    cat <<EOF
Usage: $(basename "$0") [-u BASE_URL] [-h]

  -u BASE_URL   Base URL of the running API (default: http://localhost:8000)
  -h            Show this help and exit

Requires API_KEY to be set in the environment, e.g.:
  export API_KEY=local-dev-key
  ./scripts/smoke_test.sh
EOF
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

require_env() {
    if [[ -z "${API_KEY:-}" ]]; then
        echo "ERROR: API_KEY not set. Run: export API_KEY=local-dev-key" >&2
        exit 1
    fi
}

json_get() {
    # json_get <file> <key> — tiny stdlib-only JSON field extractor
    python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ''))" "$1" "$2"
}

assert_status() {
    # assert_status <step_num> <expected> <actual>
    local step="$1" expected="$2" actual="$3"
    if [[ "${actual}" == "${expected}" ]]; then
        RESULTS+=("${step}|${expected}|${actual}|PASS")
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        RESULTS+=("${step}|${expected}|${actual}|FAIL")
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

print_report() {
    echo
    printf '%-6s | %-8s | %-6s | %s\n' "STEP" "EXPECTED" "ACTUAL" "RESULT"
    for row in "${RESULTS[@]}"; do
        IFS='|' read -r step expected actual result <<< "${row}"
        printf '%-6s | %-8s | %-6s | %s\n' "${step}" "${expected}" "${actual}" "${result}"
    done
    echo
    echo "PASSED: ${PASS_COUNT}/8"
}

main() {
    while getopts ":u:h" opt; do
        case "${opt}" in
            u) BASE_URL="${OPTARG}" ;;
            h) usage; exit 0 ;;
            \?) echo "ERROR: invalid option -${OPTARG}" >&2; usage; exit 2 ;;
            :) echo "ERROR: option -${OPTARG} requires an argument" >&2; usage; exit 2 ;;
        esac
    done

    require_env

    local app_name="smoke-app-$(date +%s)"
    local body_file="/tmp/shiptrack_smoke_body.json"

    # Step 1: create application -> 201
    local code
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/applications" \
        -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
        -d "{\"name\": \"${app_name}\", \"repo_url\": \"https://github.com/acme/${app_name}\"}")
    assert_status 1 201 "${code}"
    local app_id
    app_id=$(json_get "${body_file}" id)

    # Step 2: duplicate name -> 409
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/applications" \
        -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
        -d "{\"name\": \"${app_name}\", \"repo_url\": \"https://github.com/acme/${app_name}\"}")
    assert_status 2 409 "${code}"

    # Step 3: deployment v1.0.0 prod succeeded -> 201
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/deployments" \
        -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
        -d "{\"application_id\": ${app_id}, \"version\": \"1.0.0\", \"environment\": \"prod\", \"status\": \"succeeded\"}")
    assert_status 3 201 "${code}"

    # Step 4: deployment v2.0.0 prod succeeded -> 201
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/deployments" \
        -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
        -d "{\"application_id\": ${app_id}, \"version\": \"2.0.0\", \"environment\": \"prod\", \"status\": \"succeeded\"}")
    assert_status 4 201 "${code}"
    local v2_id
    v2_id=$(json_get "${body_file}" id)

    # Step 5: bad version -> 422
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/deployments" \
        -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
        -d "{\"application_id\": ${app_id}, \"version\": \"bad-version\", \"environment\": \"prod\"}")
    assert_status 5 422 "${code}"

    # Step 6: rollback without key -> 401
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/deployments/${v2_id}/rollback")
    assert_status 6 401 "${code}"

    # Step 7: rollback with key -> 201
    code=$(curl -s -o "${body_file}" -w '%{http_code}' -X POST "${BASE_URL}/deployments/${v2_id}/rollback" \
        -H "X-API-Key: ${API_KEY}")
    assert_status 7 201 "${code}"

    # Step 8: list deployments, no key -> 200
    code=$(curl -s -o "${body_file}" -w '%{http_code}' "${BASE_URL}/deployments")
    assert_status 8 200 "${code}"

    print_report

    if [[ "${FAIL_COUNT}" -gt 0 ]]; then
        exit 1
    fi
    exit 0
}

main "$@"
