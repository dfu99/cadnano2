#!/bin/bash
# Automated pipeline: build tapered design with verification loop
# Each attempt runs in a separate subprocess (cadnano can't reinitialize)
# Tries: 1) taper+centered midseams, 2) taper only, 3-10) fallback strategies

set -o pipefail
cd "$(dirname "$0")/.."

MAX_ATTEMPTS=10
OUT_JSON="results/stress_test/tapered_centered_2x12.json"
VERIFY="tools/verify_design.py"

echo "=== Tapered Design Pipeline ==="
echo "Max attempts: $MAX_ATTEMPTS"

for attempt in $(seq 1 $MAX_ATTEMPTS); do
    echo ""
    echo "--- Attempt $attempt/$MAX_ATTEMPTS ---"

    # Run build attempt
    timeout 60 conda run -n cn24-agentic env QT_QPA_PLATFORM=offscreen \
        python tools/build_tapered_attempt.py 2>&1 | \
        grep -v "plugin\|Signal\|Backend\|QFont\|propagate\|removeOligo"

    # Verify in a separate process
    echo "  Verifying..."
    VERIFY_OUT=$(timeout 30 conda run -n cn24-agentic env QT_QPA_PLATFORM=offscreen \
        python "$VERIFY" "$OUT_JSON" 1 2>&1 | grep -E "PASS|FAIL")

    echo "  $VERIFY_OUT"

    if echo "$VERIFY_OUT" | grep -q "PASS"; then
        echo ""
        echo "=== SUCCESS on attempt $attempt ==="
        echo "  Output: $OUT_JSON"
        exit 0
    fi

    # If midseam moves broke it, next attempt will try without moves
    # (The build script handles this internally based on what failed)
    echo "  Failed, will retry..."
done

echo ""
echo "=== FAILED after $MAX_ATTEMPTS attempts ==="
echo "  Last verification: $VERIFY_OUT"
exit 1
