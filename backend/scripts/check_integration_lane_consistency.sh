#!/usr/bin/env bash
# TASK-070 — the lane's verdict must not depend on the order its files run in.
#
# The defect this guards against is not a failing test: it is a lane that is
# green file by file and red end to end, because one module left the database in
# a state the next one could not use. That difference is invisible to `pytest
# tests/integration` alone, which is why it needs its own check.
#
# Runs the whole lane, then each file on its own, and compares the two counts.
# Usage:
#   TEST_DATABASE_URL_PG=... TEST_REDIS_URL=... scripts/check_integration_lane_consistency.sh
set -uo pipefail

PYTHON="${PYTHON:-../.venv/bin/python}"
PYTEST=("$PYTHON" -m pytest -o addopts='' -p no:cacheprovider -q)

if [[ -z "${TEST_DATABASE_URL_PG:-}" ]]; then
  echo "TEST_DATABASE_URL_PG is not set; the lane would skip and prove nothing." >&2
  exit 2
fi

# Reported as "N passed" / "N failed" / "N errors" on pytest's summary line.
count_of() { grep -oE "[0-9]+ $2" <<<"$1" | tail -1 | grep -oE '^[0-9]+' || echo 0; }

echo "### whole lane ###"
whole_output=$("${PYTEST[@]}" tests/integration 2>&1 | tail -3)
echo "$whole_output"
whole_passed=$(count_of "$whole_output" passed)
whole_failed=$(count_of "$whole_output" failed)
whole_errors=$(count_of "$whole_output" errors)

echo "### file by file ###"
sum_passed=0
sum_failed=0
sum_errors=0
for file in tests/integration/test_*.py; do
  file_output=$("${PYTEST[@]}" "$file" 2>&1 | tail -3)
  passed=$(count_of "$file_output" passed)
  failed=$(count_of "$file_output" failed)
  errors=$(count_of "$file_output" errors)
  printf '%-55s passed=%-4s failed=%-4s errors=%s\n' "$(basename "$file")" "$passed" "$failed" "$errors"
  sum_passed=$((sum_passed + passed))
  sum_failed=$((sum_failed + failed))
  sum_errors=$((sum_errors + errors))
done

echo
printf 'whole lane : passed=%s failed=%s errors=%s\n' "$whole_passed" "$whole_failed" "$whole_errors"
printf 'sum of files: passed=%s failed=%s errors=%s\n' "$sum_passed" "$sum_failed" "$sum_errors"

if [[ "$whole_passed" == "$sum_passed" && "$whole_failed" == "$sum_failed" && "$whole_errors" == "$sum_errors" ]]; then
  echo "OK: the lane's verdict does not depend on file order."
  exit 0
fi

echo "MISMATCH: running the lane together gives a different verdict than running its files apart." >&2
echo "That is the cascade this check exists to catch, not an ordinary test failure." >&2
exit 1
