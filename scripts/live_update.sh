#!/bin/bash
# Live-update loop: watches for new PCAP segments, extracts features,
# labels flows, retrains models, so the dashboard always has fresh data.
#
# Usage:
#   ./scripts/live_update.sh [--train-every N]
#
#   --train-every N   Retrain after every N new segments (default: 5)

set -euo pipefail

TRAIN_EVERY=5
if [ "${1:-}" = "--train-every" ]; then
    TRAIN_EVERY="${2:-5}"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

SEG_DIR="data/segments"
FLOWS_CSV="data/flows.csv"
LABELED_CSV="data/labeled_flows.csv"
ATTACK_LOG="data/attack_log.csv"
MODEL_DIR="models"
STATE_FILE="data/.live_state"

mkdir -p "$SEG_DIR" "$MODEL_DIR"

# Activate venv if present
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

declare -A PROCESSED
if [ -f "$STATE_FILE" ]; then
    while IFS= read -r line; do
        PROCESSED["$line"]=1
    done < "$STATE_FILE"
fi

SEG_SINCE_TRAIN=0
LAST_LOG_MTIME=""

echo "[live] Watching $SEG_DIR for new pcap segments (train every $TRAIN_EVERY)"

while true; do
    NEW_COUNT=0

    while IFS= read -r -d '' segfile; do
        name=$(basename "$segfile")
        if [ "$name" = "capture.pcap" ]; then
            continue
        fi
        if [ "${PROCESSED[$name]:-}" = "1" ]; then
            continue
        fi

        age=$(( $(date +%s) - $(stat -c %Y "$segfile" 2>/dev/null || echo 0) ))
        if [ "$age" -lt 5 ]; then
            continue
        fi

        echo "[live] Processing segment $name"
        python3 ml/extract_features.py --pcap "$segfile" --out /tmp/live_seg_$$.csv

        if [ ! -s /tmp/live_seg_$$.csv ]; then
            rm -f /tmp/live_seg_$$.csv
            PROCESSED["$name"]=1
            echo "$name" >> "$STATE_FILE"
            continue
        fi

        if [ -f "$FLOWS_CSV" ]; then
            tail -n +2 /tmp/live_seg_$$.csv >> "$FLOWS_CSV"
        else
            cp /tmp/live_seg_$$.csv "$FLOWS_CSV"
        fi
        rm -f /tmp/live_seg_$$.csv

        PROCESSED["$name"]=1
        echo "$name" >> "$STATE_FILE"
        NEW_COUNT=$((NEW_COUNT + 1))
    done < <(find "$SEG_DIR" -maxdepth 1 -name 'capture.pcap*' -print0 2>/dev/null)

    LOG_MTIME="$(stat -c %Y "$ATTACK_LOG" 2>/dev/null || echo 0)"
    LABEL_NEEDED=0
    [ "$NEW_COUNT" -gt 0 ] && LABEL_NEEDED=1
    if [ -n "$LAST_LOG_MTIME" ] && [ "$LOG_MTIME" != "$LAST_LOG_MTIME" ]; then
        echo "[live] Attack log changed -- re-labeling"
        LABEL_NEEDED=1
    fi
    LAST_LOG_MTIME="$LOG_MTIME"

    if [ "$LABEL_NEEDED" -eq 1 ] && [ -f "$ATTACK_LOG" ]; then
        echo "[live] Labeling flows..."
        python3 ml/label_flows.py --flows "$FLOWS_CSV" --log "$ATTACK_LOG" --out "$LABELED_CSV"
    fi

    SEG_SINCE_TRAIN=$((SEG_SINCE_TRAIN + NEW_COUNT))
    if [ "$SEG_SINCE_TRAIN" -ge "$TRAIN_EVERY" ] && [ -f "$LABELED_CSV" ]; then
        ROWS=$(wc -l < "$LABELED_CSV")
        if [ "$ROWS" -gt 20 ]; then
            echo "[live] Retraining models..."
            python3 ml/train_models.py --data "$LABELED_CSV" --outdir "$MODEL_DIR" 2>/dev/null || true
            echo "[live] Evaluating..."
            python3 ml/evaluate.py --outdir "$MODEL_DIR" --data "$LABELED_CSV" 2>/dev/null || true
        fi
        SEG_SINCE_TRAIN=0
    fi

    sleep 10
done
