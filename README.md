# IoT Ransomware/Malware Network-Traffic Detection Lab

Defensive security research lab for MSc Cybersecurity project.

## Structure
```
├── docker-compose.yml         # 4 services on iot_sim_net (192.168.50.0/24)
├── docker/
│   ├── iot-sensor/            # Custom image: sshd, MQTT, auto-traffic
│   ├── attacker/              # Custom image: nmap, hydra, wordlist
│   └── mqtt-broker/           # Mosquitto config
├── scripts/
│   ├── normal_traffic.py      # Runs inside iot-sensor (MQTT, HTTP, ping)
│   ├── listener.py            # Runs inside attacker (HTTP server)
│   ├── attack_recon.sh        # SYN/TCP connect scan
│   ├── attack_bruteforce.sh   # Hydra SSH brute force
│   ├── attack_beacon.sh       # C2 beacon simulation
│   ├── attack_exfil.sh        # Ransomware exfil simulation
│   └── capture_host.sh        # Host-side tcpdump on bridge interface
├── ml/
│   ├── requirements.txt
│   ├── extract_features.py    # Pcap -> bidir flow features
│   ├── label_flows.py         # Attack log interval labeling
│   ├── train_models.py        # RF + LSTM + Autoencoder
│   └── evaluate.py            # Confusion matrices, F1, ROC-AUC, FPR
├── data/                      # PCAPs + CSVs (gitignored)
├── models/                    # Trained models + results (gitignored)
└── docs/report_notes.md
```

## Quick Start
```bash
docker compose build
docker compose up -d
sudo bash scripts/capture_host.sh data/capture.pcap &
# ... run attacks, then:
kill %1
docker compose down
cd ml && python3 extract_features.py --pcap ../data/capture.pcap --out ../data/flows.csv
```
