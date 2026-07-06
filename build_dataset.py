#!/usr/bin/env python3
"""
IoT Ransomware Detection - Dataset Builder
Converts raw PCAP traffic to labeled feature vectors

Requirements: scapy, pandas, numpy
Run: python3 build_dataset.py
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime
from collections import defaultdict

try:
    from scapy.all import rdpcap, IP, TCP, UDP, ICMP
except ImportError:
    print("ERROR: scapy not installed. Run: pip install scapy")
    sys.exit(1)

# Configuration
PCAP_FILE = "data/iot_traffic_full.pcap"
OUTPUT_CSV = "data/iot_labeled_dataset.csv"
ATTACKER_IP = "192.168.50.50"  # Must match docker-compose config
ATTACK_START_TIME = 300  # Attack starts at 5 minutes (in seconds)

def load_pcap(pcap_path):
    """Load PCAP file and extract packets"""
    try:
        print(f"[*] Loading PCAP file: {pcap_path}")
        packets = rdpcap(pcap_path)
        print(f"[+] Loaded {len(packets)} packets")
        return packets
    except FileNotFoundError:
        print(f"[ERROR] PCAP file not found: {pcap_path}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Failed to load PCAP: {e}")
        sys.exit(1)

def extract_flows(packets):
    """Extract bidirectional flows from packets"""
    flows = defaultdict(lambda: {
        'packets': [],
        'bytes': [],
        'timestamps': [],
        'protocols': [],
        'src_ips': [],
        'dst_ips': [],
        'ports': []
    })
    
    base_time = None
    
    for i, packet in enumerate(packets):
        if not IP in packet:
            continue
        
        # Track base time
        if base_time is None:
            base_time = packet.time
        
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = packet[IP].proto
        
        # Extract port if available
        src_port = 0
        dst_port = 0
        if TCP in packet:
            src_port = packet[TCP].sport
            dst_port = packet[TCP].dport
        elif UDP in packet:
            src_port = packet[UDP].sport
            dst_port = packet[UDP].dport
        
        # Create bidirectional flow key (order-independent)
        # This ensures src->dst and dst->src are the same flow
        flow_key = tuple(sorted([(src_ip, src_port), (dst_ip, dst_port)]))
        
        packet_size = len(packet[IP].payload) if IP in packet else 0
        flow_duration_since_start = packet.time - base_time
        
        # Add packet to flow
        flows[flow_key]['packets'].append(len(packet))
        flows[flow_key]['bytes'].append(packet_size)
        flows[flow_key]['timestamps'].append(flow_duration_since_start)
        flows[flow_key]['protocols'].append(protocol)
        flows[flow_key]['src_ips'].append(src_ip)
        flows[flow_key]['dst_ips'].append(dst_ip)
        flows[flow_key]['ports'].append((src_port, dst_port))
        
        if (i + 1) % 100 == 0:
            print(f"  [+] Processed {i+1} packets...")
    
    print(f"[+] Extracted {len(flows)} flows")
    return flows, base_time

def calculate_features(flow_data):
    """Calculate statistical features from flow data"""
    packets = flow_data['packets']
    bytes_list = flow_data['bytes']
    timestamps = flow_data['timestamps']
    
    # Statistical features
    features = {
        'packet_count': len(packets),
        'byte_count': sum(packets),
        'payload_byte_count': sum(bytes_list),
        'avg_packet_size': np.mean(packets) if packets else 0,
        'std_packet_size': np.std(packets) if len(packets) > 1 else 0,
        'min_packet_size': np.min(packets) if packets else 0,
        'max_packet_size': np.max(packets) if packets else 0,
        'avg_payload_size': np.mean(bytes_list) if bytes_list else 0,
        'std_payload_size': np.std(bytes_list) if len(bytes_list) > 1 else 0,
    }
    
    # Temporal features
    if timestamps:
        flow_duration = max(timestamps) - min(timestamps)
        features['flow_duration'] = flow_duration
        features['packets_per_second'] = len(packets) / (flow_duration + 0.001)
        features['bytes_per_second'] = sum(packets) / (flow_duration + 0.001)
    else:
        features['flow_duration'] = 0
        features['packets_per_second'] = 0
        features['bytes_per_second'] = 0
    
    # IP entropy (uniqueness of destination IPs in flow)
    unique_dsts = len(set(flow_data['dst_ips']))
    features['dst_ip_count'] = unique_dsts
    
    # Protocol distribution
    unique_protocols = len(set(flow_data['protocols']))
    features['protocol_count'] = unique_protocols
    
    # Port analysis
    port_pairs = flow_data['ports']
    unique_dst_ports = len(set(p[1] for p in port_pairs))
    features['unique_dst_ports'] = unique_dst_ports
    
    return features

def build_dataset(flows, base_time):
    """Build feature dataframe from flows"""
    print("\n[*] Building feature dataset...")
    
    dataset = []
    
    for flow_key, flow_data in flows.items():
        # Extract IPs from flow key
        src_ip = flow_data['src_ips'][0] if flow_data['src_ips'] else None
        dst_ip = flow_data['dst_ips'][0] if flow_data['dst_ips'] else None
        
        if not src_ip or not dst_ip:
            continue
        
        # Calculate features
        features = calculate_features(flow_data)
        features['src_ip'] = src_ip
        features['dst_ip'] = dst_ip
        
        # Determine label
        # Label as malicious if:
        # 1. Attacker IP is involved, OR
        # 2. Flow occurs during attack window (after 5 minutes)
        is_attacker_involved = (src_ip == ATTACKER_IP or dst_ip == ATTACKER_IP)
        min_timestamp = min(flow_data['timestamps']) if flow_data['timestamps'] else 0
        is_during_attack = min_timestamp >= ATTACK_START_TIME
        
        if is_attacker_involved:
            features['label'] = 1
            features['label_name'] = 'malicious'
            features['label_reason'] = 'attacker_ip'
        elif is_during_attack and features['packet_count'] > 2:
            # Heuristic: suspicious if many packets after attack starts
            features['label'] = 1
            features['label_name'] = 'malicious'
            features['label_reason'] = 'during_attack'
        else:
            features['label'] = 0
            features['label_name'] = 'normal'
            features['label_reason'] = 'baseline'
        
        dataset.append(features)
    
    df = pd.DataFrame(dataset)
    df = df.fillna(0)
    
    print(f"[+] Dataset shape: {df.shape}")
    
    return df

def analyze_dataset(df):
    """Print dataset analysis"""
    print("\n[=] DATASET ANALYSIS [=]")
    print(f"\nClass distribution:")
    print(df['label_name'].value_counts())
    print(f"\nRatio: {(df['label'].sum() / len(df) * 100):.2f}% malicious")
    
    print(f"\nFeature statistics:")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    print(df[numeric_cols].describe())
    
    print(f"\nMalicious flow characteristics:")
    malicious_df = df[df['label'] == 1]
    if len(malicious_df) > 0:
        print(f"  Avg packet count: {malicious_df['packet_count'].mean():.2f}")
        print(f"  Avg byte count: {malicious_df['byte_count'].mean():.2f}")
        print(f"  Avg flow duration: {malicious_df['flow_duration'].mean():.2f}s")
        print(f"  Avg packets/sec: {malicious_df['packets_per_second'].mean():.2f}")

def main():
    print("=" * 60)
    print("IoT Ransomware Detection - PCAP to Dataset Converter")
    print("=" * 60)
    
    # Load PCAP
    packets = load_pcap(PCAP_FILE)
    
    # Extract flows
    flows, base_time = extract_flows(packets)
    
    # Build dataset
    df = build_dataset(flows, base_time)
    
    # Analyze
    analyze_dataset(df)
    
    # Save
    print(f"\n[*] Saving dataset to {OUTPUT_CSV}")
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"[+] Dataset saved successfully")
    
    # Summary for report
    print("\n[=] SUMMARY FOR YOUR REPORT [=]")
    print(f"Total flows captured: {len(df)}")
    print(f"Normal flows: {(df['label'] == 0).sum()}")
    print(f"Malicious flows: {(df['label'] == 1).sum()}")
    print(f"Feature count: {len([c for c in df.columns if c not in ['src_ip', 'dst_ip', 'label', 'label_name', 'label_reason']])}")
    print(f"\nNext step: Run train_models.py")

if __name__ == "__main__":
    main()
