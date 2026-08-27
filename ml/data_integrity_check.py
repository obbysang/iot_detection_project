#!/usr/bin/env python3
"""Quantifies duplicates and cross-split contamination in the labelled flows.

Produces docs/data_integrity_report.md with measured values only.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_common import FEATURE_COLS, LABEL_COL, make_split, load_labeled_data

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "docs", "data_integrity_report.md")


def main():
    df = load_labeled_data(os.path.join(ROOT, "data", "labeled_flows.csv"))
    train_idx, test_idx = make_split(df)
    train = df.loc[train_idx]
    test = df.loc[test_idx]

    n_total, n_train, n_test = len(df), len(train), len(test)

    dup_feature_rows_train = int(train.duplicated(subset=FEATURE_COLS).sum())
    dup_feature_rows_test = int(test.duplicated(subset=FEATURE_COLS).sum())
    dup_full_rows = int(df.duplicated().sum())

    # Identical full feature vectors appearing in BOTH partitions
    t_keys = set(map(tuple, train[FEATURE_COLS].round(10).values))
    s_keys = set(map(tuple, test[FEATURE_COLS].round(10).values))
    identical_across = len(t_keys & s_keys)

    # Exact flow-identity (5-tuple + start_time) across partitions
    id_cols = ["src_ip", "src_port", "dst_ip", "dst_port", "proto", "start_time"]
    train_ids = set(map(tuple, train[id_cols].values))
    test_ids = set(map(tuple, test[id_cols].values))
    identical_ids_across = len(train_ids & test_ids)

    # Temporal overlap: flows whose [start,end] intervals overlap between
    # partitions (sampled via interval tree approximation using sorted arrays)
    tr_start = train["start_time"].values
    tr_end = train["end_time"].values
    order = np.argsort(tr_start)
    s_sorted = tr_start[order]
    e_sorted = tr_end[order]
    overlap_count = 0
    for s, e in zip(test["start_time"].values, test["end_time"].values):
        lo = np.searchsorted(s_sorted, s, side="right")
        hi = np.searchsorted(s_sorted, e, side="left")
        if hi > lo and np.any(e_sorted[lo:hi] >= s):
            overlap_count += 1

    # Attack episodes represented in both partitions
    attacks = df[LABEL_COL].unique()
    episode_lines = []
    for a in sorted(attacks):
        sub = df[df[LABEL_COL] == a].sort_values("start_time")
        # split into episodes by gaps > 300s
        ep_breaks = (sub["start_time"].diff() > 300).cumsum()
        eps = sub.groupby(ep_breaks)["start_time"].agg(["min", "max"])
        in_tr = [i for i, r in eps.iterrows()
                 if ((train["start_time"] <= r["max"]) &
                     (train["end_time"] >= r["min"])).any()]
        in_te = [i for i, r in eps.iterrows()
                 if ((test["start_time"] <= r["max"]) &
                     (test["end_time"] >= r["min"])).any()]
        both = set(in_tr) & set(in_te)
        episode_lines.append(
            f"| {a} | {len(eps)} | {len(in_tr)} | {len(in_te)} | {len(both)} |")

    lines = [
        "# Data Integrity Report (measured values)",
        "",
        f"- Total labelled flows: {n_total}",
        f"- Training flows (stratified 80/20, seed 42): {n_train}",
        f"- Testing flows: {n_test}",
        f"- Exact duplicate full rows within whole dataset: {dup_full_rows}",
        f"- Duplicate feature-vector rows within training partition: {dup_feature_rows_train}",
        f"- Duplicate feature-vector rows within test partition: {dup_feature_rows_test}",
        f"- Distinct feature vectors present in BOTH partitions: {identical_across} "
        f"(of {len(t_keys)} train / {len(s_keys)} test distinct vectors)",
        f"- Identical flow identities (5-tuple + start_time) in BOTH partitions: {identical_ids_across}",
        f"- Test flows temporally overlapping at least one training flow "
        f"(interleaved capture windows): {overlap_count}",
        "",
        "## Attack episodes per partition",
        "",
        "| label | episodes | in train | in test | in BOTH |",
        "|---|---|---|---|---|",
        *episode_lines,
        "",
        "## Notes",
        "",
        "- Duplicated feature vectors arise from the periodic simulated normal "
        "traffic (MQTT/HTTP/ICMP loops), which produces byte-identical flows.",
        "- Because the dataset is split at flow level (per the documented 80/20 "
        "methodology), near-identical periodic normal flows inevitably appear on "
        "both sides of the split. This was quantified above and NOT removed.",
        "- RECON and BRUTEFORCE attack intervals contain 0 captured flows "
        "(attacks ran outside capture windows), so only NORMAL, C2_BEACON and "
        "EXFIL_RANSOMWARE are represented in the dataset.",
        "- EXFIL_RANSOMWARE consists of a single ~1-second episode (100 flows); an "
        "event-level split would have to place all of it on one side, so an "
        "attack/session-aware Experiment B is not statistically performable on "
        "this dataset without inventing additional data.",
    ]
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print(f"[+] Wrote {OUT}")


if __name__ == "__main__":
    main()
