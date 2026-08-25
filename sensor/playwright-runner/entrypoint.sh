#!/bin/bash
#
# Container entrypoint for the Playwright Transaction Tester
# Runs the python tester script on a continuous loop.
# Handles errors gracefully — a single test failure does NOT kill the loop.
#

# Trap SIGTERM/SIGINT for clean Docker stop behavior
trap 'echo "[$(date)] Received shutdown signal. Exiting gracefully."; exit 0' SIGTERM SIGINT

TARGET_URL=${TARGET_URL:-"https://google.com"}
TEST_TYPE=${TEST_TYPE:-"page"}
TEST_INTERVAL_SECONDS=${TEST_INTERVAL_SECONDS:-300}
METRICS_DIR=${METRICS_DIR:-"/metrics"}

echo "Starting Playwright Transaction Loop..."
echo "Target URL: $TARGET_URL"
echo "Test Type:  $TEST_TYPE"
echo "Interval:   ${TEST_INTERVAL_SECONDS}s"
echo "Output Dir: $METRICS_DIR"

mkdir -p "$METRICS_DIR"

while true; do
  echo "[$(date)] Executing transaction check..."
  
  # Run the python script; capture exit code but never abort the loop
  python3 /app/browser_transaction.py "$TARGET_URL" "$TEST_TYPE" "$METRICS_DIR/browser_transaction.prom" || \
    echo "[$(date)] WARNING: Transaction check failed with exit code $?. Will retry next interval."
  
  echo "[$(date)] Check complete. Sleeping for ${TEST_INTERVAL_SECONDS}s..."
  sleep "$TEST_INTERVAL_SECONDS" &
  wait $!
done
