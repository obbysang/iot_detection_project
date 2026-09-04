#!/usr/bin/env python3
"""Shared, authoritative definitions for the ML pipeline.

Single source of truth for:
  - the 15 network-traffic features (order matters),
  - the stratified 80/20 split,
  - LSTM sequence construction (per src_ip, time-sorted, post-split),
  - persistence of the scaler and label encoder.
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

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
    df = pd.read_csv(path, low_memory=False)
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


def make_event_level_split(df, min_test_runs=1):
    """Event-level split: entire attack runs go to train OR test.

    Strategy:
    - For each attack class, the last min_test_runs experiment_run IDs
      are held out as test.  The rest are training.
    - NORMAL flows (no experiment_run) are split randomly to fill
      approximately 80/20 proportions while keeping the overall ratio.
    - Every attack class must have at least min_test_runs + 1 runs
      or it cannot be split; raise an error.

    Returns (train_idx, test_idx) as pandas Index objects.
    """
    import warnings

    ATTACK_CLASSES = ["RECON", "BRUTEFORCE", "C2_BEACON", "EXFIL_RANSOMWARE"]
    # Determine which column holds the run identifier
    run_col = None
    for col in ["attack_run", "experiment_run"]:
        if col in df.columns and df[col].notna().any():
            run_col = col
            break

    if run_col is None:
        warnings.warn(
            "No 'attack_run' or 'experiment_run' column — falling back to "
            "stratified 80/20 split")
        return make_split(df)

    test_idx = []
    train_idx = []

    # ── Attack flows: split by run ──
    for cls in ATTACK_CLASSES:
        cls_mask = df[LABEL_COL] == cls
        cls_df = df[cls_mask]
        if len(cls_df) == 0:
            continue  # class not present in dataset
        runs = sorted(str(r) for r in cls_df[run_col].unique() if pd.notna(r) and str(r).strip())

        if len(runs) < min_test_runs + 1:
            # Not enough runs to split — put all flows in training
            # and warn (this class will not appear in the test set)
            warnings.warn(
                f"{cls}: only {len(runs)} run(s) — all assigned to training "
                f"(need >= {min_test_runs + 1} for test)")
            train_idx.extend(cls_df.index.tolist())
            continue

        test_runs = runs[-min_test_runs:]
        train_runs = runs[:-min_test_runs]

        test_idx.extend(cls_df[cls_df[run_col].isin(test_runs)].index.tolist())
        train_idx.extend(cls_df[cls_df[run_col].isin(train_runs)].index.tolist())

    # ── NORMAL flows: split randomly to maintain approximate 80/20 ──
    normal_mask = df[LABEL_COL] == "NORMAL"
    normal_idx = df[normal_mask].index.tolist()

    # How many attack flows are in each partition?
    n_attack_train = len(train_idx)
    n_attack_test = len(test_idx)
    n_attack_total = n_attack_train + n_attack_test

    # Target: train should be ~80% of total
    target_train_total = int(len(df) * (1 - TEST_SIZE))
    target_normal_train = max(0, target_train_total - n_attack_train)
    target_normal_test = len(normal_idx) - target_normal_train

    rng = np.random.RandomState(RANDOM_STATE)
    shuffled = rng.permutation(normal_idx)
    train_idx.extend(shuffled[:target_normal_train].tolist())
    test_idx.extend(shuffled[target_normal_train:].tolist())

    # ── Verify all classes appear in both ──
    train_labels = set(df.loc[train_idx, LABEL_COL].unique())
    test_labels = set(df.loc[test_idx, LABEL_COL].unique())
    missing_in_test = train_labels - test_labels
    missing_in_train = test_labels - train_labels
    if missing_in_test:
        warnings.warn(f"Classes in train but not test: {missing_in_test}")
    if missing_in_train:
        warnings.warn(f"Classes in test but not train: {missing_in_train}")

    return pd.Index(train_idx), pd.Index(test_idx)


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
