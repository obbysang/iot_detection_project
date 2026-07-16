#!/bin/bash
SEG_DIR="${1:-data/segments}"
mkdir -p "$SEG_DIR"
NET_ID=$(docker network inspect iot_sim_net -f '{{.Id}}' 2>/dev/null)
if [ -z "$NET_ID" ]; then
    echo "ERROR: iot_sim_net not found. Are the containers running?" >&2
    exit 1
fi
BR_ID="${NET_ID:0:12}"
BRIDGE="br-${BR_ID}"
echo "Capturing on $BRIDGE -> $SEG_DIR/capture.pcap (30s rotation, 500 files)" >&2
exec tcpdump -i "$BRIDGE" -G 30 -W 500 -w "$SEG_DIR/capture.pcap" -n
