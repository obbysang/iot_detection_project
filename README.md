# IoT Ransomware/Malware Network-Traffic Detection Lab

Defensive security research lab — simulates an IoT network with normal and attack traffic, extracts flow features, and trains ML models (Random Forest, LSTM, Autoencoder) for intrusion detection. Built for MSc Cybersecurity.

## Prerequisites

- **Docker Desktop** (with Docker Compose V2)
- **Python 3.11+** (3.12 recommended for Windows)
- **Node.js 18+** with **pnpm** (for dashboard frontend build)
- **Git Bash** or WSL (for shell scripts on Windows)
- **4 GB+ RAM** available for Docker and TensorFlow

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd iot_detection_project

# 2. Create Python venv and install dependencies
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r ml/requirements.txt -r dashboard/server/requirements.txt

# 3. Build and launch Docker containers
docker compose build
docker compose up -d

# 4. Start the attack listener (in attacker container)
docker exec -d attacker python3 /scripts/listener.py

# 5. Build the dashboard frontend
cd dashboard && pnpm install && pnpm build && cd ..

# 6. Start the dashboard API
uvicorn dashboard.server.main:app --host 0.0.0.0 --port 8000

# 7. Open the dashboard
# Navigate to http://localhost:8000 in your browser
```

For the full step-by-step setup with troubleshooting, see **[docs/RUNBOOK.md](docs/RUNBOOK.md)** (Linux/macOS) or **[docs/RUNBOOK-WIN.md](docs/RUNBOOK-WIN.md)** (Windows).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Host                        │
│                                                      │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────┐  │
│  │  iot-sensor  │   │   attacker   │   │capture   │  │
│  │  192.168.50.20│  │  192.168.50.99│  │(host net)│  │
│  │  sshd, MQTT  │   │  nmap, hydra │  │ tcpdump  │  │
│  │  normal_traffic│  │  listener.py │  │          │  │
│  └──────┬───────┘   └──────┬───────┘  └────┬─────┘  │
│         │                  │               │         │
│  ┌──────┴───────┐   ┌──────┴───────┐       │         │
│  │ mqtt-broker  │   │   iot-web    │       │         │
│  │ 192.168.50.10│   │ 192.168.50.11│       │         │
│  │  Mosquitto   │   │   Nginx      │       │         │
│  └──────────────┘   └──────────────┘       │         │
│                                            │         │
│  ┌─────────────────────────────────────────┘         │
│  │  data/segments/capture.pcapN (rotating 30s)       │
│  ▼                                                    │
│  ┌────────────────┐    ┌──────────────┐               │
│  │  ML Pipeline    │    │  Dashboard   │               │
│  │ live_update.sh  │◄──►│  uvicorn     │               │
│  │ extract_features│    │  port 8000   │               │
│  │ label_flows     │    │  controls +  │               │
│  │ train_models    │    │  live view   │               │
│  │ evaluate        │    └──────────────┘               │
│  └────────────────┘                                    │
└─────────────────────────────────────────────────────┘
```

## Structure

```
├── docker-compose.yml         # 6 containers on iot_sim_net (192.168.50.0/24)
├── docker/
│   ├── iot-sensor/            # sshd, normal traffic generator
│   ├── attacker/              # Kali — nmap, hydra, wordlist
│   ├── capture/               # Privileged tcpdump container
│   ├── dashboard-api/         # FastAPI + uvicorn
│   └── mqtt-broker/           # Mosquitto config
├── dashboard/
│   ├── src/                   # TypeScript frontend (Chart.js)
│   ├── dist/                  # Bundled frontend (built, gitignored)
│   └── server/main.py         # FastAPI — data API + control endpoints
├── scripts/
│   ├── normal_traffic.py      # MQTT, HTTP, ICMP inside iot-sensor
│   ├── listener.py            # HTTP listener inside attacker (C2/exfil target)
│   ├── attack_recon.sh        # Nmap SYN scan
│   ├── attack_bruteforce.sh   # Hydra SSH brute-force
│   ├── attack_beacon.sh       # C2 beacon simulation
│   ├── attack_exfil.sh        # Ransomware exfil simulation
│   ├── capture_host.sh        # Host-side tcpdump on bridge interface
│   ├── capture_rotate.sh      # Rotating tcpdump segments
│   ├── run_experiment.py      # Full orchestrated experiment runner
│   └── live_update.sh         # Watch pcap segments → extract → label → train
├── ml/
│   ├── requirements.txt       # Python ML dependencies
│   ├── extract_features.py    # Pcap → bidirectional flow features
│   ├── label_flows.py         # Label flows by attack_log.csv time intervals
│   ├── annotate_flows.py      # Add experiment run IDs to labeled flows
│   ├── dataset_validator.py   # Pre-training validation gate
│   ├── data_integrity_check.py# Quantify duplicates and cross-split contamination
│   ├── train_models.py        # Random Forest + LSTM + Autoencoder
│   ├── evaluate.py            # Confusion matrices, F1, ROC-AUC, FPR
│   └── pipeline_common.py     # Shared constants, split logic, sequence builder
├── models/                    # Trained .joblib / .keras / results (gitignored)
├── data/                      # PCAPs, CSVs, attack_log (gitignored)
├── results/                   # ML evaluation results (tracked)
│   ├── evaluation_results.csv
│   ├── confusion_matrix_*.csv
│   └── thesis_results.md
└── docs/
    ├── RUNBOOK.md             # Linux/macOS setup guide
    └── RUNBOOK-WIN.md         # Windows/PowerShell setup guide
```

## Data Flow

1. **Capture** — `tcpdump` runs inside `iot-capture`, writing 30-second segments to `data/segments/capture.pcapN`
2. **Normal traffic** — `normal_traffic.py` generates MQTT sensor readings, HTTP requests, and ICMP pings
3. **Attacks** — Dashboard buttons or CLI scripts trigger recon, brute-force, C2 beacon, and exfil from the attacker container
4. **Feature extraction** — `extract_features.py` reads each pcap segment and outputs bidirectional flow features (packet/byte counts, IAT stats, entropy, etc.) into `data/flows.csv`
5. **Labeling** — `label_flows.py` cross-references flow timestamps against `data/attack_log.csv` START/END intervals, producing `data/labeled_flows.csv`
6. **Training** — `train_models.py` trains a Random Forest, an LSTM sequence classifier, and an Autoencoder anomaly detector
7. **Evaluation** — `evaluate.py` generates confusion matrices, weighted F1 scores, and ROC-AUC metrics → `models/evaluation_results.csv`
8. **Dashboard** — The FastAPI backend serves KPIs, flow table, timeline chart, and event stream from these CSVs in near real-time

## Running the Experiment

### Automated (full pipeline)

```bash
# Run 3 full experiment repetitions
python scripts/run_experiment.py --repetitions 3
```

### Manual (step by step)

```bash
# Start capture (on host, after containers are up)
bash scripts/capture_rotate.sh

# In another terminal — start the live pipeline (watches for new segments)
bash scripts/live_update.sh --train-every 5

# Trigger attacks (via dashboard buttons or CLI)
docker exec attacker bash /scripts/attack_recon.sh
docker exec attacker bash /scripts/attack_bruteforce.sh
docker exec attacker bash /scripts/attack_beacon.sh
docker exec attacker bash /scripts/attack_exfil.sh

# Train models manually
python ml/train_models.py --data data/labeled_flows.csv --outdir models/

# Evaluate
python ml/evaluate.py --outdir models/ --data data/labeled_flows.csv
```

## Dashboard

The web dashboard provides a real-time view of network activity:

- **KPI cards** — Total flows, attack count, detection rate
- **Flow table** — Sortable/filterable table of all detected flows
- **Timeline chart** — Network activity over time with attack markers
- **Event stream** — Live feed of detected events (SSE)

The frontend is built with TypeScript + Chart.js and bundled with esbuild. The backend is FastAPI serving REST + SSE endpoints.


## License

MSc project — use freely for educational and research purposes.
