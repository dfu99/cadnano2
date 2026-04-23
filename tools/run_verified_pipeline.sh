#!/bin/bash
# General-purpose verify-and-retry pipeline for any cadnano design script.
#
# Usage:
#   tools/run_verified_pipeline.sh <build_script> <output_json> [expected_oligos] [max_attempts]
#
# The build_script must:
#   - Accept the output JSON path as its first argument
#   - Exit 0 on success, non-zero on failure
#   - Be runnable with: conda run -n cn24-agentic env QT_QPA_PLATFORM=offscreen python <script> <output_json>
#
# Example:
#   tools/run_verified_pipeline.sh tools/build_tapered_attempt.py results/stress_test/tapered.json 1 10

set -euo pipefail
cd "$(dirname "$0")/.."

BUILD_SCRIPT="${1:?Usage: $0 <build_script> <output_json> [expected_oligos] [max_attempts]}"
OUT_JSON="${2:?Usage: $0 <build_script> <output_json> [expected_oligos] [max_attempts]}"
EXPECTED_OLIGOS="${3:-1}"
MAX_ATTEMPTS="${4:-10}"
VERIFY="tools/verify_design.py"

echo "=== Verified Build Pipeline ==="
echo "  Script: $BUILD_SCRIPT"
echo "  Output: $OUT_JSON"
echo "  Expected oligos: $EXPECTED_OLIGOS"
echo "  Max attempts: $MAX_ATTEMPTS"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo ""
    echo "--- Attempt $attempt/$MAX_ATTEMPTS ---"

    # Run build
    timeout 120 conda run -n cn24-agentic env QT_QPA_PLATFORM=offscreen \
        python "$BUILD_SCRIPT" "$OUT_JSON" 2>&1 | \
        grep -v "plugin\|Signal\|Backend\|QFont\|propagate\|removeOligo"

    BUILD_EXIT=$?
    if [ $BUILD_EXIT -ne 0 ]; then
        echo "  Build script exited with error $BUILD_EXIT"
        continue
    fi

    if [ ! -f "$OUT_JSON" ]; then
        echo "  Output file not found: $OUT_JSON"
        continue
    fi

    # Verify
    echo "  Verifying..."
    VERIFY_OUT=$(timeout 60 conda run -n cn24-agentic env QT_QPA_PLATFORM=offscreen \
        python "$VERIFY" "$OUT_JSON" "$EXPECTED_OLIGOS" 2>&1 | grep -E "PASS|FAIL")

    echo "  $VERIFY_OUT"

    if echo "$VERIFY_OUT" | grep -q "PASS"; then
        echo ""
        echo "=== PASS on attempt $attempt ==="
        exit 0
    fi

    echo "  Failed, will retry..."
done

echo ""
echo "=== FAILED after $MAX_ATTEMPTS attempts ==="
exit 1
