# Runbook — IoT Ransomware/Malware Network-Traffic Detection Lab

## Prerequisites

- Docker & Docker Compose (with Compose V2 — `docker compose` not `docker-compose`)
- Python 3.10+ + venv
- sudo access for host-based packet capture (optional — capture runs in Docker)
- npm / pnpm (for building the dashboard frontend)



## 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r ml/requirements.txt
pip install -r dashboard/server/requirements.txt
```

## 2. Fix Directory Permissions

Containers run as `root` but the host directories are owned by your user. Without this, tcpdump inside the capture container gets **Permission denied** when writing pcap files.

```bash
chmod 777 data data/segments
```

## 3. Build & Launch the Lab

```bash
docker compose build
docker compose up -d
```

All 6 containers come up:

| Container | IP | Purpose |
|---|---|---|
| `mqtt-broker` | 192.168.50.10 | Eclipse Mosquitto |
| `iot-web` | 192.168.50.11 | Nginx (fake web server) |
| `iot-sensor` | 192.168.50.20 | IoT device (sshd + normal traffic generator) |
| `attacker` | 192.168.50.99 | Kali (nmap, hydra, curl) |
| `dashboard-api` | (bridge) | FastAPI backend — serves UI + control endpoints |
| `iot-capture` | host network | Privileged tcpdump container |

## 4. Start HTTP Listener (for C2 beacon & exfil)

```bash
docker exec -d attacker python3 /scripts/listener.py
```

## 5. Build the Dashboard Frontend

```bash
cd dashboard && pnpm install && pnpm build && cd ..
```

## 6. Start the Dashboard API

Run this directly on the host (not in Docker, so it can run the ML pipeline against the local filesystem):

```bash
source venv/bin/activate
uvicorn dashboard.server.main:app --host 0.0.0.0 --port 8000
```

Keep this terminal open. Open http://localhost:8000 in a browser — you'll see the dashboard but it will be empty.

## 7. Start Packet Capture

The capture container's tcpdump must use a **numbered-file loop** (the built-in `-G` flag does not produce the filenames the pipeline expects):

```bash
docker exec iot-capture sh -c '
  SEG_DIR="/data/segments"
  COUNTER=0
  while true; do
    FILE="$SEG_DIR/capture.pcap$COUNTER"
    timeout 30 tcpdump -i any -n -w "$FILE" 2>/dev/null
    COUNTER=$((COUNTER + 1))
    [ "$COUNTER" -ge 500 ] && COUNTER=0
    sleep 1
  done &
'
```

## 8. Start Normal Traffic Generation

This makes the iot-sensor send MQTT/HTTP/ICMP traffic to create background flows:

```bash
docker exec -d iot-sensor python3 /scripts/normal_traffic.py
```

## 9. Start the ML Pipeline

```bash
source venv/bin/activate
nohup bash scripts/live_update.sh --train-every 5 > /tmp/live_update.log 2>&1 &
```

The pipeline watches `data/segments/` for new `capture.pcapN` files, extracts features into `data/flows.csv`, labels them against `data/attack_log.csv` into `data/labeled_flows.csv`, and retrains models every 5 segments.

After ~30–60 seconds, refresh the dashboard — you should see flows appearing.

## 10. Run Attacks Via the Dashboard

In the dashboard, click these buttons **in order** (or use the CLI commands below):

| Button | What it does |
|---|---|
| **Recon** | Nmap SYN scan from attacker→iot-sensor |
| **Brute Force** | Hydra SSH brute-force from attacker→iot-sensor |
| **Beacon** | Periodic HTTP beacon from attacker→attacker listener |
| **Exfil** | Simulated ransomware exfil via netcat |

Each attack appends a START/END entry to `data/attack_log.csv`. After ~30 seconds (next segment rotation), the pipeline re-labels all flows and the dashboard updates.

**What to expect:**
- Flows with labels **RECON**, **BRUTEFORCE**, **C2_BEACON** appear in the table
- **Detection Rate** KPI rises above 0%
- Use the **Label** dropdown filter to view specific attack types
- The **Network Activity** chart shows traffic spikes correlating with attacks

## 11. Alternative: Manual CLI Workflow

If you prefer the terminal over the dashboard buttons:

### 11a. Run Attacks

```bash
docker exec attacker bash /scripts/attack_recon.sh      >> data/attack_log.csv
docker exec attacker bash /scripts/attack_bruteforce.sh  >> data/attack_log.csv
docker exec attacker bash /scripts/attack_beacon.sh 180  >> data/attack_log.csv
docker exec attacker bash /scripts/attack_exfil.sh       >> data/attack_log.csv
```

### 11b. Re-label Flows (after attack completes)

```bash
source venv/bin/activate
python3 ml/label_flows.py \
  --flows data/flows.csv \
  --log data/attack_log.csv \
  --out data/labeled_flows.csv
```

The dashboard picks up the new file within 10 seconds.

## 12. Train Models (Optional)

Once you have enough labeled data (~100+ attack flows):

```bash
source venv/bin/activate
python3 ml/train_models.py --data data/labeled_flows.csv --outdir models/
python3 ml/evaluate.py --outdir models/ --data data/labeled_flows.csv
```

The dashboard will show **F1 scores** for Random Forest, LSTM, and Autoencoder models.

## 13. Stop Everything

```bash
pkill -f live_update.sh        # stop the ML pipeline
docker compose down
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Dashboard shows 404 | Frontend not built | `cd dashboard && pnpm build` |
| Capture starts but no .pcap files appear | Directory permissions | `chmod 777 data data/segments` |
| All flows labeled NORMAL | Timezone bug in `label_flows.py` | Apply Patch A (see §0) |
| Pipeline crashes with `EDecimal` error | numpy/scapy type bug | Apply Patch B (see §0) |
| Pipeline errors about missing venv | Dependencies not installed | `pip install -r ml/requirements.txt` in venv |
| Attacks hang / timeout | Listener not running on attacker | `docker exec -d attacker python3 /scripts/listener.py` |
| `docker start dashboard-api` fails (port 8000 in use) | Already running on host | Use the host uvicorn process instead (see §6) |
| Empty `evaluation_results.csv` in models/ | Pipeline ran eval without models | Run training first (see §12) or delete the file |
