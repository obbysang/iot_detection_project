#!/bin/bash
DURATION=${1:-180}
LISTENER="http://192.168.50.99:8080/checkin"
SRC_IP=$(hostname -i | awk '{print $1}')
TARGET_IP="192.168.50.99"
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,C2_BEACON_START,$SRC_IP,$TARGET_IP"

END_TIME=$((SECONDS + DURATION))
while [ $SECONDS -lt $END_TIME ]; do
    curl -s "${LISTENER}?id=$(hostname)" -o /dev/null 2>/dev/null || true
    SLEEP_SEC=$((40 + RANDOM % 20))
    sleep "$SLEEP_SEC"
done

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,C2_BEACON_END,$SRC_IP,$TARGET_IP"
