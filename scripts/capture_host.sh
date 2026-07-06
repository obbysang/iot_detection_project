#!/bin/bash
PCAP_FILE="${1:-capture.pcap}"
NET_ID=$(docker network inspect iot_sim_net -f '{{.Id}}' 2>/dev/null)
if [ -z "$NET_ID" ]; then
    echo "ERROR: iot_sim_net not found. Are the containers running?" >&2
    exit 1
fi
BR_ID="${NET_ID:0:12}"
BRIDGE="br-${BR_ID}"
echo "Capturing on interface $BRIDGE -> $PCAP_FILE" >&2
exec tcpdump -i "$BRIDGE" -w "$PCAP_FILE" -n
