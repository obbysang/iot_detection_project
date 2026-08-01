#!/bin/bash
PCAP_FILE="${1:-capture.pcap}"
NET_NAME=$(docker network ls --format '{{.Name}}' | grep 'iot_sim_net' | head -n1)
NET_ID=$(docker network inspect "$NET_NAME" -f '{{.Id}}' 2>/dev/null)
if [ -z "$NET_ID" ]; then
    echo "ERROR: iot_sim_net network not found. Are the containers running?" >&2
    exit 1
fi
BR_ID="${NET_ID:0:12}"
BRIDGE="br-${BR_ID}"
echo "Capturing on interface $BRIDGE -> $PCAP_FILE" >&2
exec tcpdump -i "$BRIDGE" -w "$PCAP_FILE" -n
