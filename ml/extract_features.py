#!/usr/bin/env python3
import argparse
import sys
import math
from collections import defaultdict
from datetime import datetime

import pandas as pd
import numpy as np

try:
    from scapy.all import rdpcap, IP, TCP, UDP, ICMP
except ImportError:
    print("ERROR: scapy not installed. Run: pip install scapy", file=sys.stderr)
    sys.exit(1)


def shannon_entropy(values):
    if not values:
        return 0.0
    n = len(values)
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    entropy = 0.0
    for c in counts.values():
        p = c / n
        entropy -= p * math.log2(p)
    return entropy


def parse_pcap(pcap_path):
    packets = rdpcap(pcap_path)
    return packets


def extract_flows(packets):
    flow_packets = defaultdict(list)
    total = len(packets)
    for i, pkt in enumerate(packets):
        if IP not in pkt:
            continue
        ip = pkt[IP]
        src_ip = ip.src
        dst_ip = ip.dst
        proto = ip.proto
        src_port = 0
        dst_port = 0
        if TCP in pkt:
            src_port = pkt[TCP].sport
            dst_port = pkt[TCP].dport
        elif UDP in pkt:
            src_port = pkt[UDP].sport
            dst_port = pkt[UDP].dport

        key = (src_ip, src_port, dst_ip, dst_port, proto)
        flow_packets[key].append(pkt)

        if (i + 1) % 5000 == 0:
            print(f"  Processed {i+1}/{total} packets...", file=sys.stderr)
    print(f"  Total packets: {total}, Raw flows: {len(flow_packets)}", file=sys.stderr)
    return flow_packets


def compute_features(flow_packets):
    rows = []
    dst_history = defaultdict(list)

    for key, pkts in flow_packets.items():
        src_ip, src_port, dst_ip, dst_port, proto = key

        timestamps = np.array([p.time for p in pkts])
        sizes = np.array([len(p) for p in pkts])

        duration = timestamps[-1] - timestamps[0] if len(timestamps) > 1 else 0.0
        total_packets = len(pkts)
        total_bytes = int(sizes.sum())

        fwd_packets = len(pkts)
        bwd_packets = 0
        fwd_bytes = total_bytes
        bwd_bytes = 0

        mean_pkt_len = float(sizes.mean()) if len(sizes) > 0 else 0.0
        std_pkt_len = float(sizes.std()) if len(sizes) > 1 else 0.0

        if len(timestamps) > 1:
            iats = np.diff(timestamps)
            mean_iat = float(iats.mean())
            std_iat = float(iats.std())
        else:
            mean_iat = 0.0
            std_iat = 0.0

        pkts_per_sec = total_packets / duration if duration > 0 else 0.0
        bytes_per_sec = total_bytes / duration if duration > 0 else 0.0

        uncommon_port = 1 if dst_port not in (80, 443, 22, 1883, 8080, 53) else 0

        flow_start = timestamps[0]
        dst_history[src_ip].append((flow_start, dst_ip))
        cutoff = flow_start - 10.0
        recent = [d for t, d in dst_history[src_ip] if t >= cutoff]
        dst_ip_entropy = shannon_entropy(recent)

        rows.append({
            "src_ip": src_ip,
            "src_port": src_port,
            "dst_ip": dst_ip,
            "dst_port": dst_port,
            "proto": proto,
            "start_time": flow_start,
            "end_time": timestamps[-1],
            "duration": duration,
            "total_packets": total_packets,
            "total_bytes": total_bytes,
            "fwd_packets": fwd_packets,
            "bwd_packets": bwd_packets,
            "fwd_bytes": fwd_bytes,
            "bwd_bytes": bwd_bytes,
            "mean_pkt_len": mean_pkt_len,
            "std_pkt_len": std_pkt_len,
            "mean_iat": mean_iat,
            "std_iat": std_iat,
            "pkts_per_sec": pkts_per_sec,
            "bytes_per_sec": bytes_per_sec,
            "uncommon_port": uncommon_port,
            "dst_ip_entropy": dst_ip_entropy,
        })

    df = pd.DataFrame(rows)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pcap", required=True, help="Path to input pcap file")
    parser.add_argument("--out", required=True, help="Path to output CSV")
    args = parser.parse_args()

    print(f"[*] Loading pcap: {args.pcap}", file=sys.stderr)
    packets = parse_pcap(args.pcap)
    print(f"[*] Extracting flows...", file=sys.stderr)
    flow_packets = extract_flows(packets)
    print(f"[*] Computing features...", file=sys.stderr)
    df = compute_features(flow_packets)
    print(f"[+] Flows extracted: {len(df)}", file=sys.stderr)
    print(f"[+] Saving to: {args.out}", file=sys.stderr)
    df.to_csv(args.out, index=False)
    print(f"[+] Done", file=sys.stderr)


if __name__ == "__main__":
    main()
