#!/usr/bin/env python3
"""Shared, authoritative definitions for the ML pipeline.

Single source of truth for:
  - the 15 network-traffic features (order matters),
  - the stratified 80/20 split,
  - LSTM sequence construction (per src_ip, time-sorted, post-split),
  - persistence of the scaler and label encoder.
"""
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

RANDOM_STATE = 42
TEST_SIZE = 0.2
SEQ_LEN = 5

FEATURE_COLS = [
    "duration", "total_packets", "total_bytes",
    "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
    "mean_pkt_len", "std_pkt_len", "mean_iat", "std_iat",
    "pkts_per_sec", "bytes_per_sec", "uncommon_port", "dst_ip_entropy",
]

LABEL_COL = "label"


def load_labeled_data(path):
    df = pd.read_csv(path)
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"ERROR: missing required feature columns: {missing}")
    if LABEL_COL not in df.columns:
        raise SystemExit("ERROR: missing label column 'label'")
    return df


def make_split(df):
    """Deterministic stratified 80/20 index split."""
    train_idx, test_idx = train_test_split(
        df.index, test_size=TEST_SIZE,
        random_state=RANDOM_STATE, stratify=df[LABEL_COL],
    )
    return train_idx, test_idx


def build_sequences(partition_df, scaler=None):
    """Build LSTM sequences from ONE partition only.

    Sequences are formed per src_ip over flows sorted by start_time;
    the sequence label is the label of its last flow. A sequence never
    spans two partitions because it is built exclusively from rows of
    the partition it belongs to.
    """
    sequences = []
    labels = []
    cols = FEATURE_COLS + ["src_ip", "start_time", LABEL_COL]
    data = partition_df[cols].copy().dropna(subset=FEATURE_COLS)
    for _, group in data.groupby("src_ip"):
        group = group.sort_values("start_time")
        values = group[FEATURE_COLS].values.astype(np.float32)
        if scaler is not None:
            values = scaler.transform(values).astype(np.float32)
        seq_labels = group[LABEL_COL].values
        for i in range(len(group) - SEQ_LEN + 1):
            sequences.append(values[i:i + SEQ_LEN])
            labels.append(seq_labels[i + SEQ_LEN - 1])
    if not sequences:
        return np.empty((0, SEQ_LEN, len(FEATURE_COLS)), dtype=np.float32), np.array([])
    return np.array(sequences), np.array(labels)


def save_label_encoder(le, outdir):
    import joblib
    path = os.path.join(outdir, "label_encoder.joblib")
    joblib.dump(le, path)
    return path
