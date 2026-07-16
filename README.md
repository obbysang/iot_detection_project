# IoT Ransomware/Malware Network-Traffic Detection Lab

Defensive security research lab — simulates an IoT network with normal and attack traffic, extracts flow features, and trains ML models (Random Forest, LSTM, Autoencoder) for intrusion detection. Built for MSc Cybersecurity.

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
│   └── server/main.py         # FastAPI — data API + control endpoints
├── scripts/
│   ├── normal_traffic.py      # MQTT, HTTP, ICMP inside iot-sensor
│   ├── listener.py            # HTTP listener inside attacker (C2/exfil target)
│   ├── attack_recon.sh        # Nmap SYN scan
│   ├── attack_bruteforce.sh   # Hydra SSH brute-force
│   ├── attack_beacon.sh       # C2 beacon simulation
│   ├── attack_exfil.sh        # Ransomware exfil simulation
│   ├── capture_host.sh        # Host-side tcpdump on bridge interface
│   └── live_update.sh         # Watch pcap segments → extract → label → train
├── ml/
│   ├── requirements.txt
│   ├── extract_features.py    # Pcap → bidirectional flow features
│   ├── label_flows.py         # Label flows by attack_log.csv time intervals
│   ├── train_models.py        # Random Forest + LSTM + Autoencoder
│   └── evaluate.py            # Confusion matrices, F1, ROC-AUC, FPR
├── data/                      # PCAPs, CSVs, attack_log (gitignored)
├── models/                    # Trained .joblib / .keras / results (gitignored)
└── docs/RUNBOOK.md            # Full setup and usage guide
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

## Quick Start

See **[docs/RUNBOOK.md](docs/RUNBOOK.md)** for the complete step-by-step setup. It includes:

- Required bug patches (timezone parsing, numpy/scapy compatibility)
- Directory permission fixes
- Container launch
- Capture loop, traffic generation, and ML pipeline
- Running attacks and viewing labeled results
- Training and evaluating models

```bash
# Minimal preview (after RUNBOOK steps 1-9):
git clone <repo> && cd iot_detection_project
# apply patches in ml/label_flows.py and ml/extract_features.py
chmod 777 data data/segments
python3 -m venv venv && source venv/bin/activate && pip install -r ml/requirements.txt -r dashboard/server/requirements.txt
docker compose build && docker compose up -d
docker exec -d attacker python3 /scripts/listener.py
cd dashboard && pnpm install && pnpm build && cd ..
uvicorn dashboard.server.main:app --host 0.0.0.0 --port 8000
# ... then capture, pipeline, and attacks (see RUNBOOK)
```

## Key Fixes (as of Jul 2026)

| Issue | File | Fix |
|---|---|---|
| All flows labeled NORMAL | `ml/label_flows.py` | Parse attack timestamps as timezone-aware UTC |
| Pipeline crash on pcap read | `ml/extract_features.py` | Cast `p.time` to `float` before numpy |
| tcpdump -G rotation mismatch | `scripts/live_update.sh` | Rewrote to track files by name, skip in-progress |
| Permission denied for containers | `data/` `data/segments/` | `chmod 777` |
| train_models StringArray crash | `ml/train_models.py` | Split on `df.index` instead of y_test.index |
| evaluate autoencoder multiclass | `ml/evaluate.py` | Binarize labels for anomaly detection |
Add new wheels and scripts for live updates and capture rotation

- Added various Python wheel packages including absl_py, astunparse, certifi, and many others to the ml/wheels directory.
- Introduced capture_rotate.sh script for capturing network traffic using tcpdump with automatic segment rotation.
- Implemented live_update.sh script to monitor new PCAP segments, extract features, label flows, and retrain models automatically.
## License

MSc project — use freely for educational and research purposes.
