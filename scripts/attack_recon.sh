#!/bin/bash
TARGET="192.168.50.20"
SRC_IP=$(hostname -i | awk '{print $1}')
START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$START,RECON_START,$SRC_IP,$TARGET"

# Run 3 sequential scans with pauses so traffic spans >= 1 segment (30s).
# Scan 1: common ports (fast)
nmap -sS -p 22,80,443,1883,8080 "$TARGET" -oN /data/nmap_scan.txt 2>/dev/null || \
    nmap -sT -p 22,80,443,1883,8080 "$TARGET" -oN /data/nmap_scan.txt 2>/dev/null
sleep 10

# Scan 2: extended range
nmap -sS -p 1-500 "$TARGET" 2>/dev/null || \
    nmap -sT -p 1-500 "$TARGET" 2>/dev/null
sleep 10

# Scan 3: full range
nmap -sS -p 1-1000 "$TARGET" 2>/dev/null || \
    nmap -sT -p 1-1000 "$TARGET" 2>/dev/null

END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "$END,RECON_END,$SRC_IP,$TARGET"
