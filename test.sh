#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_EXIT=0
JAVA_EXIT=0
TOTAL_PASSED=0
TOTAL_FAILED=0

log() {
  printf '%s\n' "$1"
}

wait_for_service() {
  local name="$1"
  local retries=30
  local delay=5

  while [ "$retries" -gt 0 ]; do
    if docker compose ps "$name" 2>/dev/null | grep -q "running"; then
      return 0
    fi
    retries=$((retries - 1))
    sleep "$delay"
  done

  return 1
}

log "[1/4] Starting docker compose services"
if ! docker compose up -d; then
  log "docker compose failed to start"
  exit 1
fi

log "[2/4] Waiting for postgres, redis, airflow-webserver"
wait_for_service postgres || { log "postgres did not become ready"; exit 1; }
wait_for_service redis || { log "redis did not become ready"; exit 1; }
wait_for_service airflow-webserver || { log "airflow-webserver did not become ready"; exit 1; }

log "[3/4] Running Python tests"
if uv run pytest etl/tests/test_transform.py; then
  TOTAL_PASSED=$((TOTAL_PASSED + 1))
else
  PYTHON_EXIT=$?
  TOTAL_FAILED=$((TOTAL_FAILED + 1))
fi

log "[4/4] Running Spring Boot tests"
if gradle -p api test; then
  TOTAL_PASSED=$((TOTAL_PASSED + 1))
else
  JAVA_EXIT=$?
  TOTAL_FAILED=$((TOTAL_FAILED + 1))
fi

log "Test summary: passed=${TOTAL_PASSED} failed=${TOTAL_FAILED}"

if [ "$PYTHON_EXIT" -ne 0 ] || [ "$JAVA_EXIT" -ne 0 ]; then
  exit 1
fi

exit 0
