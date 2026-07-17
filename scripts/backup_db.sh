#!/usr/bin/env bash
set -euo pipefail

# backup_db.sh — dump the running PostgreSQL compose service into a
# timestamped file, then prune dumps older than RETENTION_DAYS.
#
# Usage: ./scripts/backup_db.sh [-d BACKUP_DIR] [-r RETENTION_DAYS] [-h]
#   defaults: BACKUP_DIR=./backups, RETENTION_DAYS=7

BACKUP_DIR="./backups"
RETENTION_DAYS=7

usage() {
    cat <<EOF
Usage: $(basename "$0") [-d BACKUP_DIR] [-r RETENTION_DAYS] [-h]

  -d BACKUP_DIR       Directory to write dumps into (default: ./backups)
  -r RETENTION_DAYS   Delete dumps older than this many days (default: 7)
  -h                  Show this help and exit

Requires POSTGRES_USER and POSTGRES_DB to be set in the environment or in
a .env file in the current directory, and the 'db' compose service to be
running.
EOF
}

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

require_env() {
    local missing=0
    if [[ -z "${POSTGRES_USER:-}" ]]; then
        echo "ERROR: POSTGRES_USER not set. Export it or set it in .env" >&2
        missing=1
    fi
    if [[ -z "${POSTGRES_DB:-}" ]]; then
        echo "ERROR: POSTGRES_DB not set. Export it or set it in .env" >&2
        missing=1
    fi
    if [[ "${missing}" -eq 1 ]]; then
        exit 1
    fi
}

load_dotenv_if_present() {
    if [[ -f .env ]]; then
        # shellcheck disable=SC1091
        set -a
        source .env
        set +a
    fi
}

check_db_running() {
    if ! docker compose ps db 2>/dev/null | grep -q "db"; then
        echo "ERROR: the 'db' compose service is not running. Run: docker compose up -d db" >&2
        exit 1
    fi
    if ! docker compose ps db --format '{{.State}}' 2>/dev/null | grep -qi "running"; then
        echo "ERROR: the 'db' compose service is not in a running state." >&2
        exit 1
    fi
}

do_backup() {
    mkdir -p "${BACKUP_DIR}"
    local ts
    ts="$(date +%Y%m%d_%H%M%S)"
    local outfile="${BACKUP_DIR}/shiptrack_${ts}.sql"

    log "Starting pg_dump -> ${outfile}"
    if ! docker compose exec -T db pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" > "${outfile}"; then
        echo "ERROR: pg_dump failed" >&2
        rm -f "${outfile}"
        exit 1
    fi

    if [[ ! -s "${outfile}" ]]; then
        echo "ERROR: dump file ${outfile} is empty or missing" >&2
        exit 1
    fi

    local size_bytes
    size_bytes="$(wc -c < "${outfile}" | tr -d ' ')"
    log "Backup complete: ${outfile} (${size_bytes} bytes)"
}

prune_old_backups() {
    local pruned_count=0
    while IFS= read -r -d '' old_file; do
        rm -f "${old_file}"
        pruned_count=$((pruned_count + 1))
    done < <(find "${BACKUP_DIR}" -maxdepth 1 -name 'shiptrack_*.sql' -mtime "+${RETENTION_DAYS}" -print0)
    log "Pruned ${pruned_count} backup(s) older than ${RETENTION_DAYS} day(s)"
}

main() {
    while getopts ":d:r:h" opt; do
        case "${opt}" in
            d) BACKUP_DIR="${OPTARG}" ;;
            r) RETENTION_DAYS="${OPTARG}" ;;
            h) usage; exit 0 ;;
            \?) echo "ERROR: invalid option -${OPTARG}" >&2; usage; exit 2 ;;
            :) echo "ERROR: option -${OPTARG} requires an argument" >&2; usage; exit 2 ;;
        esac
    done

    load_dotenv_if_present
    require_env
    check_db_running
    do_backup
    prune_old_backups
}

main "$@"
