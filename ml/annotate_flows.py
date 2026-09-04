#!/usr/bin/env python3
"""Annotate labeled_flows.csv with attack_run from experiment metadata.

Uses closest-match (not first-match) to handle overlapping buffered windows.
"""
import pandas as pd
import json
import glob
import os
from datetime import datetime

BUFFER_SEC = 15  # narrow buffer to reduce overlap

df = pd.read_csv("data/labeled_flows.csv", low_memory=False)
df["attack_run"] = ""

exp_dirs = sorted(glob.glob("data/experiment_20260827_*"))
exp_dir = None
for d in reversed(exp_dirs):
    if glob.glob(os.path.join(d, "*_run*.json")):
        exp_dir = d
        break
if not exp_dir:
    print("No experiment with run metadata found")
    exit(1)

print(f"Using: {exp_dir}")

runs = []
for f in sorted(glob.glob(os.path.join(exp_dir, "*_run*.json"))):
    meta = json.load(open(f))
    try:
        start = datetime.fromisoformat(
            meta["attack_start_utc"].replace("Z", "+00:00")).timestamp()
        end = datetime.fromisoformat(
            meta["attack_end_utc"].replace("Z", "+00:00")).timestamp()
    except Exception:
        continue
    runs.append({
        "attack_run": meta["attack_run"],
        "start_raw": start,
        "end_raw": end,
        "start": start - BUFFER_SEC,
        "end": end + BUFFER_SEC,
        "mid": (start + end) / 2,
    })
    print(f"  {meta['attack_run']}: {start:.0f} - {end:.0f}")

annotated = 0
for idx, row in df.iterrows():
    fs, fe = row["start_time"], row["end_time"]
    flow_mid = (fs + fe) / 2

    # Find all runs whose buffered window overlaps this flow
    candidates = []
    for r in runs:
        if fs <= r["end"] and fe >= r["start"]:
            # Distance from flow midpoint to attack midpoint
            dist = abs(flow_mid - r["mid"])
            candidates.append((dist, r["attack_run"]))

    if candidates:
        # Pick the closest attack
        candidates.sort()
        df.at[idx, "attack_run"] = candidates[0][1]
        annotated += 1

df.to_csv("data/labeled_flows.csv", index=False)

print(f"\nAnnotated {annotated} flows")
for cls in ["RECON", "BRUTEFORCE", "C2_BEACON", "EXFIL_RANSOMWARE"]:
    sub = df[df["label"] == cls]
    runs_found = sub["attack_run"].dropna()
    runs_found = runs_found[runs_found != ""]
    print(f"  {cls}: {len(sub)} flows, {len(runs_found)} annotated, "
          f"runs: {sorted(runs_found.unique())}")
