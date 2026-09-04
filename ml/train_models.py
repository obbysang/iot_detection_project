#!/usr/bin/env python3
"""Authoritative training pipeline (Random Forest, LSTM, Autoencoder).

Corrected evaluation methodology:
  - stratified 80/20 split (random_state=42)
  - StandardScaler fitted on TRAINING data only, saved to models/scaler.joblib
  - one persistent label encoder saved to models/label_encoder.joblib
  - LSTM sequences built independently per partition AFTER the split
    (no sequence crosses the train/test boundary)
  - Autoencoder trained on TRAINING normal flows only; threshold =
    mean + 3*std of reconstruction errors on those same training flows
"""
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # suppress all TF info/warning/err
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import argparse
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler, LabelEncoder

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_common import (
    FEATURE_COLS, LABEL_COL, RANDOM_STATE, SEQ_LEN,
    load_labeled_data, make_split, make_event_level_split,
    build_sequences, save_label_encoder,
)


def train_random_forest(X_train, y_train):
    print("[*] Training Random Forest...", file=sys.stderr)
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    return rf


def train_lstm(X_train_seq, y_train_seq, num_classes):
    try:
        import random
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("[!] TensorFlow not installed -- skipping LSTM", file=sys.stderr)
        return None

    tf.keras.utils.set_random_seed(RANDOM_STATE)
    try:
        tf.config.experimental.enable_op_determinism()
    except Exception:
        pass

    model = keras.Sequential([
        layers.Input(shape=(X_train_seq.shape[1], X_train_seq.shape[2])),
        layers.LSTM(64, return_sequences=False),
        layers.Dense(32, activation="relu"),
        layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    model.fit(X_train_seq, y_train_seq, epochs=20, batch_size=64,
              validation_split=0.1, verbose=0)
    return model


def train_autoencoder(X_train_norm):
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("[!] TensorFlow not installed -- skipping Autoencoder", file=sys.stderr)
        return None

    tf.keras.utils.set_random_seed(RANDOM_STATE)
    input_dim = X_train_norm.shape[1]
    model = keras.Sequential([
        layers.Input(shape=(input_dim,)),
        layers.Dense(16, activation="relu"),
        layers.Dense(8, activation="relu"),
        layers.Dense(16, activation="relu"),
        layers.Dense(input_dim, activation="linear"),
    ])
    model.compile(optimizer="adam", loss="mse")
    model.fit(X_train_norm, X_train_norm, epochs=30, batch_size=16,
              validation_split=0.1, verbose=0)
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to labeled flows CSV")
    parser.add_argument("--outdir", required=True, help="Output directory for models")
    parser.add_argument("--split-mode", choices=["stratified", "event_level"],
                        default="stratified",
                        help="Split mode: stratified (default) or event_level")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"[*] Loading data: {args.data}", file=sys.stderr)
    df = load_labeled_data(args.data)
    n_total = len(df)
    class_dist = df[LABEL_COL].value_counts().to_dict()
    print(f"[+] {n_total} flows; class distribution: {class_dist}", file=sys.stderr)

    # ---- Split FIRST ----
    if args.split_mode == "event_level":
        print("[*] Using EVENT-LEVEL split (attack runs → train/test)", file=sys.stderr)
        train_idx, test_idx = make_event_level_split(df)
    else:
        print("[*] Using STRATIFIED 80/20 split", file=sys.stderr)
        train_idx, test_idx = make_split(df)
    y_all = df[LABEL_COL].values
    X_train = df.loc[train_idx, FEATURE_COLS].values.astype(np.float64)
    X_test = df.loc[test_idx, FEATURE_COLS].values.astype(np.float64)
    y_train = df.loc[train_idx, LABEL_COL].values
    y_test = df.loc[test_idx, LABEL_COL].values
    print(f"[+] Train: {len(train_idx)}  Test: {len(test_idx)}", file=sys.stderr)

    # ---- Scaler fitted on training data ONLY ----
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    joblib.dump(scaler, os.path.join(args.outdir, "scaler.joblib"))
    print("[+] Saved: models/scaler.joblib", file=sys.stderr)

    # ---- One authoritative label encoder (fit on training labels) ----
    le = LabelEncoder()
    le.fit(y_train)
    label_mapping = {str(c): int(i) for i, c in enumerate(le.classes_)}
    save_label_encoder(le, args.outdir)
    print(f"[+] Label mapping: {label_mapping}", file=sys.stderr)

    # Persist holdout test set so evaluate.py uses exactly this partition.
    df.loc[test_idx].to_csv(os.path.join(args.outdir, "holdout_test_set.csv"), index=False)

    # Record which attack runs are in test (for event-level split)
    metadata = {}
    run_col = None
    for col in ["attack_run", "experiment_run"]:
        if col in df.columns and df[col].notna().any():
            run_col = col
            break
    if args.split_mode == "event_level" and run_col:
        test_runs = df.loc[test_idx, run_col].unique().tolist()
        test_runs = [r for r in test_runs if pd.notna(r) and str(r).strip()]
        metadata["test_experiment_runs"] = test_runs
        train_runs = df.loc[train_idx, run_col].unique().tolist()
        train_runs = [r for r in train_runs if pd.notna(r) and str(r).strip()]
        metadata["train_experiment_runs"] = train_runs

    metadata.update({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_STATE,
        "split_mode": args.split_mode,
        "test_size": 0.2,
        "stratified": args.split_mode == "stratified",
        "feature_count": len(FEATURE_COLS),
        "features": list(FEATURE_COLS),
        "label_mapping": label_mapping,
        "total_flows": int(n_total),
        "training_flows": int(len(train_idx)),
        "testing_flows": int(len(test_idx)),
        "class_distribution_total": {k: int(v) for k, v in class_dist.items()},
        "class_distribution_train": {k: int(v) for k, v in pd.Series(y_train).value_counts().items()},
        "class_distribution_test": {k: int(v) for k, v in pd.Series(y_test).value_counts().items()},
        "lstm_sequence_length": SEQ_LEN,
        "rf_params": {"n_estimators": 200, "max_depth": 20,
                      "min_samples_split": 5, "class_weight": "balanced"},
        "lstm_params": {"units": 64, "dense": 32, "epochs": 20, "batch_size": 64},
        "ae_params": {"layers": [16, 8, 16], "epochs": 30, "batch_size": 16},
    })

    # ---- Random Forest (train partition only) ----
    rf = train_random_forest(X_train_scaled, y_train)
    joblib.dump(rf, os.path.join(args.outdir, "random_forest.joblib"))
    f1_rf = f1_score(y_test, rf.predict(X_test_scaled), average="weighted")
    print(f"[+] RF weighted F1 (holdout): {f1_rf:.4f}", file=sys.stderr)
    metadata["rf_holdout_weighted_f1"] = float(f1_rf)

    # ---- LSTM: sequences built AFTER the split, per partition ----
    train_part = df.loc[train_idx]
    test_part = df.loc[test_idx]
    X_tr_seq, y_tr_lab = build_sequences(train_part, scaler=scaler)
    X_te_seq, y_te_lab = build_sequences(test_part, scaler=scaler)
    y_tr_ids = le.transform(y_tr_lab) if len(y_tr_lab) else np.array([])
    y_te_ids = le.transform(y_te_lab) if len(y_te_lab) else np.array([])
    print(f"[+] LSTM sequences -- train: {len(X_tr_seq)}, test: {len(X_te_seq)}",
          file=sys.stderr)
    metadata["lstm_training_sequences"] = int(len(X_tr_seq))
    metadata["lstm_testing_sequences"] = int(len(X_te_seq))
    metadata["lstm_sequence_class_distribution_train"] = {
        str(k): int(v) for k, v in pd.Series(y_tr_lab).value_counts().items()} if len(y_tr_lab) else {}
    metadata["lstm_sequence_class_distribution_test"] = {
        str(k): int(v) for k, v in pd.Series(y_te_lab).value_counts().items()} if len(y_te_lab) else {}

    if len(X_tr_seq) >= 20 and len(np.unique(y_tr_ids)) > 1:
        # Subsample if too many sequences for available memory
        MAX_SEQ = 50000
        if len(X_tr_seq) > MAX_SEQ:
            rng = np.random.RandomState(RANDOM_STATE)
            keep = rng.choice(len(X_tr_seq), MAX_SEQ, replace=False)
            X_tr_seq = X_tr_seq[keep]
            y_tr_ids = y_tr_ids[keep]
            print(f"[+] Subsampled LSTM training to {MAX_SEQ} sequences for memory",
                  file=sys.stderr)
        lstm_model = train_lstm(X_tr_seq, y_tr_ids, num_classes=len(le.classes_))
        if lstm_model is not None:
            lstm_model.save(os.path.join(args.outdir, "lstm_model.keras"))
            pred = np.argmax(lstm_model.predict(X_te_seq, verbose=0), axis=1)
            f1_lstm = f1_score(y_te_ids, pred, average="weighted")
            print(f"[+] LSTM weighted F1 (holdout): {f1_lstm:.4f}", file=sys.stderr)
            metadata["lstm_holdout_weighted_f1"] = float(f1_lstm)
    else:
        print("[!] Not enough LSTM training sequences/classes -- skipping LSTM",
              file=sys.stderr)

    # ---- Autoencoder: TRAINING normal flows only, threshold from them only ----
    normal_mask = pd.Series(y_train) == "NORMAL"
    X_train_norm = X_train_scaled[normal_mask.values]
    print(f"[+] Autoencoder training on {X_train_norm.shape[0]} NORMAL training flows",
          file=sys.stderr)
    ae_model = train_autoencoder(X_train_norm)
    if ae_model is not None:
        recon = ae_model.predict(X_train_norm, verbose=0)
        errors = np.mean(np.square(X_train_norm - recon), axis=1)
        threshold = float(np.mean(errors) + 3 * np.std(errors))
        with open(os.path.join(args.outdir, "autoencoder_threshold.json"), "w") as f:
            json.dump({
                "threshold": threshold,
                "rule": "mean + 3 * std of per-flow reconstruction error",
                "computed_on": "TRAINING partition NORMAL flows only",
                "n_training_normal": int(X_train_norm.shape[0]),
                "mean_error": float(np.mean(errors)),
                "std_error": float(np.std(errors)),
            }, f, indent=2)
        ae_model.save(os.path.join(args.outdir, "autoencoder_model.keras"))
        print(f"[+] Autoencoder threshold: {threshold:.6g} (saved)", file=sys.stderr)
        metadata["autoencoder_threshold"] = threshold
        metadata["autoencoder_training_normal_samples"] = int(X_train_norm.shape[0])

    with open(os.path.join(args.outdir, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print("[+] Saved: models/training_metadata.json", file=sys.stderr)
    print("[+] Training complete", file=sys.stderr)


if __name__ == "__main__":
    main()
