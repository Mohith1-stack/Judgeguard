#!/usr/bin/env bash
set -euo pipefail

REPORT="acceptance-report.txt"
: > "$REPORT"

echo "JudgeGuard final acceptance" | tee -a "$REPORT"
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$REPORT"
echo | tee -a "$REPORT"

echo "[T1/T2/T3/T4] Source compilation" | tee -a "$REPORT"
python -m compileall -q apps/api/app
echo "PASS: Python compilation" | tee -a "$REPORT"

echo "[ENGINE] Automated tests" | tee -a "$REPORT"
PYTHONPATH=. python -m pytest -q | tee -a "$REPORT"

echo "[DOCKER] Compose config" | tee -a "$REPORT"
docker compose config >/dev/null
echo "PASS: docker-compose configuration" | tee -a "$REPORT"

echo "[DOCKER] Build + start" | tee -a "$REPORT"
docker compose up -d --build
docker compose ps | tee -a "$REPORT"

echo "[HEALTH] API" | tee -a "$REPORT"
curl --fail http://localhost:8000/api/v1/health >/dev/null
echo "PASS: API health" | tee -a "$REPORT"
curl --fail http://localhost:8000/api/v1/health/db >/dev/null
echo "PASS: database health" | tee -a "$REPORT"

echo | tee -a "$REPORT"
echo "Live acceptance still required on the target laptop:" | tee -a "$REPORT"
echo "- backend role isolation (judge cannot access peer scores)" | tee -a "$REPORT"
echo "- deadline enforcement" | tee -a "$REPORT"
echo "- evaluation submission ownership" | tee -a "$REPORT"
echo "- duplicate/rate-limited public voting" | tee -a "$REPORT"
echo "- organizer-readable audit log" | tee -a "$REPORT"
echo "- webhook signature verification" | tee -a "$REPORT"
echo "- public Ed25519 participation-record verification" | tee -a "$REPORT"
echo "- bulk export/import round trip" | tee -a "$REPORT"

echo | tee -a "$REPORT"
echo "PASS: automated final acceptance stages completed; live abuse/role checks are explicitly listed above." | tee -a "$REPORT"
