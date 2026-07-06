#!/bin/bash
TARGET="192.168.50.20"
SRC_IP=$(hostname -i | awk '{print $1}')
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,RECON_START,$SRC_IP,$TARGET"

nmap -sS -p 1-1000 "$TARGET" -oN /data/nmap_scan.txt 2>/dev/null
if [ $? -ne 0 ]; then
    nmap -sT -p 1-1000 "$TARGET" -oN /data/nmap_scan.txt 2>/dev/null
fi

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,RECON_END,$SRC_IP,$TARGET"
