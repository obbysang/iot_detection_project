# Report Notes — IoT Ransomware/Malware Network-Traffic Detection Lab

## Architecture
- Dockerised IoT network with isolated `iot_sim_net` bridge (192.168.50.0/24)
- Normal traffic: MQTT sensor readings, HTTP GETs, ICMP pings
- Simulated attacks: port recon, SSH brute force, C2 beacon, ransomware exfil
- ML pipeline: Random Forest (supervised), LSTM (sequential), Autoencoder (unsupervised anomaly)

## Attack Log Format
All attack scripts emit structured `_START`/`_END` log lines:
```
<ISO8601 UTC>,<EVENT>_START,<src_ip>,<dst_ip>
<ISO8601 UTC>,<EVENT>_END,<src_ip>,<dst_ip>
```

## Feature Set (15 features per flow)
duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes,
bwd_bytes, mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec,
bytes_per_sec, uncommon_port, dst_ip_entropy (rolling 10s window)

## Models
1. Random Forest — class_weight="balanced", 200 trees
2. LSTM — SEQ_LEN=5 sliding windows per src_ip (skipped if <20 sequences)
3. Autoencoder — trained on NORMAL only, threshold = mean + 3*std
