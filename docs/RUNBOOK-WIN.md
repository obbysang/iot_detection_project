# Runbook (Windows) — IoT Ransomware/Malware Network-Traffic Detection Lab

Windows/PowerShell version of `RUNBOOK.md`. All commands below run in **PowerShell** unless stated otherwise.

## Prerequisites

- **Docker Desktop** (installed, with WSL2 backend) — must be running before any `docker` command
- **Python 3.12** (exactly — required by TensorFlow, see §0) + venv
- **pnpm** — for building the dashboard frontend (`npm install -g pnpm`)
- **Git for Windows** (or WSL) — provides `bash`, required by the ML pipeline 

## 0. Required: Python 3.12

This lab **requires Python 3.12**. TensorFlow (needed for the LSTM and Autoencoder models) ships no Windows wheels for newer versions — 3.12 is the maximum it supports, so installing Python 3.14 and omitting TensorFlow would silently disable two of the three models.

**Install Python 3.12 from https://www.python.org/downloads/windows/ and check "Add python.exe to PATH" during setup.**

Verify:

```powershell
py -3.12 --version
```

Then always create the venv with the 3.12 launcher, not the default `python`:

```powershell
py -3.12 -m venv venv
```

## 1. Install Dependencies

Install the **full** dependency set, including TensorFlow (deep-learning models are part of the lab, not optional):

```powershell
py -3.12 -m venv venv
venv\Scripts\python -m pip install -r ml/requirements.txt
venv\Scripts\python -m pip install -r dashboard/server/requirements.txt
```

(No `chmod` needed on Windows — NTFS bind mounts work with Docker Desktop.)

## 2. Create Data Directories

The lab expects `data/` and `data/segments/` to exist (they are gitignored and not in the repo):

```powershell
New-Item -ItemType Directory -Force -Path data\segments, models
```

## 3. Build & Launch the Lab

```powershell
docker compose build
docker compose up -d
docker ps
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

```powershell
docker exec -d attacker python3 /scripts/listener.py
```

## 5. Build the Dashboard Frontend

```powershell
cd dashboard
pnpm install
pnpm build
cd ..
```

## 6. Start the Dashboard API

Run directly on the host (not in Docker, so it can run the ML pipeline against the local filesystem):

```powershell
venv\Scripts\python -m uvicorn dashboard.server.main:app --host 0.0.0.0 --port 8000
```

Keep this window open. Open http://localhost:8000 in a browser — the dashboard appears but is empty.

(Optional: `venv\Scripts\Activate.ps1` then `uvicorn dashboard.server.main:app --host 0.0.0.0 --port 8000`. Note: `source` is Linux-only.)

## 7. Start Packet Capture

**Verify you capture the right traffic first** (must show `192.168.50.x` addresses, not `192.168.65.x`):

```powershell
docker exec iot-capture tcpdump -i any -n -c 20 "net 192.168.50.0/24"
```

Then paste this as **one line** in PowerShell (single quotes are required — the `$` inside must not be expanded):

```powershell
docker exec iot-capture sh -c 'SEG_DIR="/data/segments"; COUNTER=500; while true; do FILE="$SEG_DIR/capture.pcap$COUNTER"; timeout 30 tcpdump -i any -n "net 192.168.50.0/24" -w "$FILE" 2>/dev/null; COUNTER=$((COUNTER + 1)); [ "$COUNTER" -ge 1000 ] && COUNTER=500; sleep 1; done &'
```

This writes 30-second rotating segments `data/segments/capture.pcapN` (the `-G` flag doesn't produce the filenames the pipeline expects).

- The `net 192.168.50.0/24` filter is **required**: the IoT sim network is `192.168.50.0/24`. Without it, tcpdump on `-i any` also captures `192.168.65.x` Docker-engine API traffic and the pipeline labels that as `NORMAL`.
- The counter starts at **500** on purpose: the pipeline skips any segment listed in `data/.live_state` (0–499 were already consumed by an earlier run). Starting at 500 guarantees the new capture is processed. If you wiped the data (below), restart the counter at 0.
- **If your previous capture only produced NORMAL flows, start clean** (in PowerShell, with the pipeline stopped):

```powershell
Remove-Item data\flows.csv, data\labeled_flows.csv, data\.live_state -ErrorAction SilentlyContinue
Remove-Item data\segments\capture.pcap* -ErrorAction SilentlyContinue
```

Then restart the pipeline (§9), capture with counter 0, and only then run attacks.

## 8. Start Normal Traffic Generation

```powershell
docker exec -d iot-sensor python3 /scripts/normal_traffic.py
```

## 9. Start the ML Pipeline

`live_update.sh` is a bash script — run it from **Git Bash** (or WSL), not PowerShell:

```bash
# Git Bash only
source venv/Scripts/activate
bash scripts/live_update.sh --train-every 5
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

### 11a. Run Attacks

```powershell
docker exec attacker bash /scripts/attack_recon.sh       >> data\attack_log.csv
docker exec attacker bash /scripts/attack_bruteforce.sh   >> data\attack_log.csv
docker exec attacker bash /scripts/attack_beacon.sh 180   >> data\attack_log.csv
docker exec attacker bash /scripts/attack_exfil.sh        >> data\attack_log.csv
```

### 11b. Re-label Flows (after attack completes)

```powershell
venv\Scripts\python ml\label_flows.py --flows data\flows.csv --log data\attack_log.csv --out data\labeled_flows.csv
```

The dashboard picks up the new file within 10 seconds.

## 12. Train Models (Optional)

Once you have enough labeled data (~100+ attack flows):

```powershell
venv\Scripts\python ml\train_models.py --data data\labeled_flows.csv --outdir models\
venv\Scripts\python ml\evaluate.py --data data\labeled_flows.csv --outdir models\
```

The dashboard shows **F1 scores** for Random Forest, LSTM, and Autoencoder models.

## 13. Stop Everything

```powershell
# Stop the pipeline in Git Bash (or just close its window):
#   Ctrl+C in the live_update.sh window
docker compose down
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `error during connect ... dockerDesktopLinuxEngine` | Docker Desktop not running | Start Docker Desktop, wait for "Engine running", retry |
| `source : The term 'source' is not recognized` | Linux command in PowerShell | Use `venv\Scripts\Activate.ps1` or call `venv\Scripts\python` directly |
| `ModuleNotFoundError: No module named 'scapy'` | Deps not installed in venv | Run §1, or re-run pip with `venv\Scripts\python -m pip` |
| `No matching distribution found for tensorflow` | Wrong Python version | Install Python 3.12 and recreate the venv with `py -3.12 -m venv venv` (see §0) |
| `bash: not recognized` (pipeline won't start) | Git Bash not installed | Install Git for Windows, or run the pipeline steps manually (extract → label → train) with `venv\Scripts\python` |
| Dashboard shows 404 | Frontend not built | `cd dashboard; pnpm build` |
| Capture starts but no .pcap files appear | `data/segments` missing | `New-Item -ItemType Directory -Force -Path data\segments` |
| All flows labeled NORMAL | Capture ran at a different time than the attacks, or captured the wrong network (`192.168.65.x` Docker-API noise instead of `192.168.50.x`) | Re-capture while attacks are running, with the filter in §7. Verify with `docker exec iot-capture tcpdump -i any -n -c 20 "net 192.168.50.0/24"` — you must see `192.168.50.x` addresses. Wipe stale data and restart (§7) |
| New capture doesn't appear in dashboard | Segment names collide with `data/.live_state` (pipeline skips already-processed names) | Start the counter at a higher number than the previous run, or delete `data/.live_state` + `data/segments/capture.pcap*` (§7) |
| Pipeline crashes with `EDecimal` error | numpy/scapy type bug | Cast `p.time` to `float` before numpy in `extract_features.py` |
| Attacks hang / timeout | Listener not running on attacker | `docker exec -d attacker python3 /scripts/listener.py` |
| Port 8000 already in use | Old uvicorn or `dashboard-api` container | Stop the other process, or skip the container and use the host uvicorn (§6) |
| Empty `evaluation_results.csv` in models/ | Pipeline ran eval without models | Run training first (§12) or delete the file |
