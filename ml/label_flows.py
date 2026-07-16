#!/usr/bin/env python3
import argparse
import sys
from datetime import datetime, timezone

import pandas as pd


def parse_attack_log(log_path):
    intervals = {}
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 4:
                continue
            timestamp_str, event, src_ip, dst_ip = parts[:4]
            try:
                ts = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue

            base_name = event.rsplit("_", 1)[0]
            is_end = event.endswith("_END")

            if base_name not in intervals:
                intervals[base_name] = []
            if not is_end:
                intervals[base_name].append({"start": ts, "end": None, "src": src_ip, "dst": dst_ip})
            else:
                for iv in reversed(intervals[base_name]):
                    if iv["end"] is None:
                        iv["end"] = ts
                        break

    valid = []
    for name, ivs in intervals.items():
        for iv in ivs:
            if iv["end"] is not None:
                valid.append((name, iv["start"], iv["end"]))
    return valid


def label_flows(flows_df, attack_intervals):
    labels = []
    for _, row in flows_df.iterrows():
        fs = row["start_time"]
        fe = row["end_time"]
        label = "NORMAL"
        for aname, t0, t1 in attack_intervals:
            if fs <= t1 and fe >= t0:
                label = aname
                break
        labels.append(label)
    return labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flows", required=True, help="Path to flows CSV")
    parser.add_argument("--log", required=True, help="Path to attack log CSV")
    parser.add_argument("--out", required=True, help="Path to output labeled CSV")
    args = parser.parse_args()

    print(f"[*] Loading flows: {args.flows}", file=sys.stderr)
    flows_df = pd.read_csv(args.flows)
    print(f"[*] Parsing attack log: {args.log}", file=sys.stderr)
    attack_intervals = parse_attack_log(args.log)

    print(f"[+] Found {len(attack_intervals)} attack intervals:", file=sys.stderr)
    for name, t0, t1 in attack_intervals:
        print(f"    {name}: {t0} - {t1}", file=sys.stderr)

    print(f"[*] Labeling flows...", file=sys.stderr)
    flows_df["label"] = label_flows(flows_df, attack_intervals)

    vc = flows_df["label"].value_counts()
    print(f"[+] Label distribution:", file=sys.stderr)
    for label, count in vc.items():
        print(f"    {label}: {count}", file=sys.stderr)

    print(f"[*] Saving to: {args.out}", file=sys.stderr)
    flows_df.to_csv(args.out, index=False)
    print(f"[+] Done", file=sys.stderr)


if __name__ == "__main__":
    main()
