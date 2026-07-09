# Runbook — IoT Ransomware/Malware Network-Traffic Detection Lab

## Prerequisites

- Docker & Docker Compose
- Python 3 + venv
- sudo access for packet capture

## 1. Install ML Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r ml/requirements.txt
```

## 2. Build & Launch the Lab

```bash
docker compose build
docker compose up -d
```

Containers: MQTT broker (.10), Nginx web server (.11), IoT sensor (.20, auto-generates normal traffic), Attacker (.99, Kali).

## 3. Start Packet Capture

```bash
sudo bash scripts/capture_host.sh data/capture.pcap &
```

## 4. Run Attacks

```bash
docker exec attacker bash /scripts/attack_recon.sh      >> data/attack_log.csv
docker exec attacker bash /scripts/attack_bruteforce.sh  >> data/attack_log.csv
docker exec attacker bash /scripts/attack_beacon.sh 180  >> data/attack_log.csv
docker exec attacker bash /scripts/attack_exfil.sh       >> data/attack_log.csv
```

## 5. Stop Capture & Tear Down

```bash
kill %1
docker compose down
```

## 6. Extract Flow Features

```bash
source venv/bin/activate
python3 ml/extract_features.py --pcap data/capture.pcap --out data/flows.csv
```

## 7. Label Flows with Ground Truth

```bash
python3 ml/label_flows.py --flows data/flows.csv --log data/attack_log.csv --out data/labeled_flows.csv
```

## 8. Train Models

```bash
python3 ml/train_models.py --data data/labeled_flows.csv --outdir models/
```

Trains Random Forest, LSTM, and Autoencoder. Saves model files, scaler, and holdout test set to `models/`.

## 9. Evaluate

```bash
python3 ml/evaluate.py --outdir models/ --data data/labeled_flows.csv
```

Outputs confusion matrix PNGs, F1 scores, ROC-AUC, FPR, and `evaluation_results.csv`.
