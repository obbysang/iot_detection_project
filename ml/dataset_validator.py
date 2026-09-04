#!/usr/bin/env python3
"""
Pre-training validation gate.

Refuses to proceed if the dataset does not meet minimum requirements.
Run before training to prevent the "RECON=0, BRUTEFORCE=0" problem
from happening again.

Usage:
    python ml/dataset_validator.py --data data/labeled_flows.csv
    python ml/dataset_validator.py --data data/labeled_flows.csv --min-per-class 50
"""
import argparse
import json
import sys

import pandas as pd

# ── Requirements ──────────────────────────────────────────────────────────────
# Minimum number of flows per class required before training is allowed.
# These can be overridden via CLI args.
DEFAULT_MINIMUM_PER_CLASS = {
    "NORMAL":           1000,
    "RECON":              10,
    "BRUTEFORCE":         10,
    "C2_BEACON":         100,
    "EXFIL_RANSOMWARE":   10,
}

# Optional: require at least this many distinct attack episodes per class
DEFAULT_MIN_EPISODES = {
    "RECON":              2,
    "BRUTEFORCE":         2,
    "C2_BEACON":          2,
    "EXFIL_RANSOMWARE":   2,
}


def validate(csv_path, min_per_class=None, min_episodes=None):
    df = pd.read_csv(csv_path, low_memory=False)
    total = len(df)
    class_counts = df["label"].value_counts().to_dict()
    n_classes = len(class_counts)

    errors = []
    warnings = []

    # ── Check class counts ──
    requirements = min_per_class or DEFAULT_MINIMUM_PER_CLASS
    for cls, req in requirements.items():
        actual = class_counts.get(cls, 0)
        if actual < req:
            errors.append(
                f"INSUFFICIENT {cls}: {actual} flows (minimum {req} required)")
        else:
            print(f"  OK  {cls}: {actual} flows (>= {req})")

    # Check for unexpected classes
    known = set(requirements.keys())
    for cls in class_counts:
        if cls not in known:
            warnings.append(f"UNKNOWN class '{cls}': {class_counts[cls]} flows "
                            f"(will be treated as NORMAL or excluded)")

    # ── Check attack episodes ──
    episodes = min_episodes or DEFAULT_MIN_EPISODES
    if "attack_run" in df.columns or "experiment_run" in df.columns:
        run_col = "attack_run" if "attack_run" in df.columns else "experiment_run"
        for cls, req in episodes.items():
            cls_runs = df[df["label"] == cls][run_col].nunique()
            cls_flows = class_counts.get(cls, 0)
            if cls_runs == 0 and cls_flows > 0:
                warnings.append(
                    f"NO annotated episodes for {cls}: {cls_flows} flows exist "
                    f"but 0 runs matched (all flows will be assigned to training)")
            elif cls_runs < req:
                warnings.append(
                    f"LOW episodes for {cls}: {cls_runs} runs "
                    f"({req} recommended for event-level split)")
            else:
                print(f"  OK  {cls}: {cls_runs} distinct episodes (>= {req})")
    else:
        warnings.append(
            "No 'attack_run' or 'experiment_run' column found — cannot verify "
            "episode count. Event-level split will not be available.")

    # ── Check feature columns ──
    required_features = [
        "duration", "total_packets", "total_bytes",
        "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
        "mean_pkt_len", "std_pkt_len", "mean_iat", "std_iat",
        "pkts_per_sec", "bytes_per_sec", "uncommon_port", "dst_ip_entropy",
    ]
    missing = [f for f in required_features if f not in df.columns]
    if missing:
        errors.append(f"Missing feature columns: {missing}")
    else:
        print(f"  OK  All 15 features present")

    # ── Check for NaN/Inf ──
    for f in required_features:
        nans = df[f].isna().sum()
        infs = (df[f] == float("inf")).sum() + (df[f] == float("-inf")).sum()
        if nans > 0:
            warnings.append(f"  {f}: {nans} NaN values (will be dropped)")
        if infs > 0:
            warnings.append(f"  {f}: {infs} Inf values (will be dropped)")

    # ── Check minimum total ──
    if total < 100:
        errors.append(f"TOTAL flows too low: {total} (minimum 100)")
    else:
        print(f"  OK  Total flows: {total}")

    # ── Report ──
    print(f"\n{'=' * 50}")
    print(f"Dataset: {csv_path}")
    print(f"Total flows: {total}")
    print(f"Classes: {n_classes}")
    for cls, count in sorted(class_counts.items()):
        print(f"  {cls}: {count} ({count/total*100:.1f}%)")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  WARN {w}")

    if errors:
        print(f"\nERRORS ({len(errors)}) -- TRAINING BLOCKED:")
        for e in errors:
            print(f"  FAIL {e}")
        print(f"\nFix the dataset and re-run.")
        return False

    print(f"\n>> Dataset validation PASSED")
    return True


def main():
    parser = argparse.ArgumentParser(description="Validate dataset before training")
    parser.add_argument("--data", required=True, help="Path to labelled flows CSV")
    parser.add_argument("--min-per-class", type=json.loads, default=None,
                        help='JSON dict of minimum flows per class, e.g. \'{"NORMAL": 1000}\'')
    args = parser.parse_args()
    ok = validate(args.data, min_per_class=args.min_per_class)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
