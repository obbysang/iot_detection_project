#!/usr/bin/env python3
import argparse
import sys
import json
import os
from collections import defaultdict

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
import joblib


def train_random_forest(X_train, y_train, X_test, y_test, outdir):
    print("[*] Training Random Forest...", file=sys.stderr)
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_split=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    f1 = f1_score(y_test, y_pred, average="weighted")
    print(f"[+] RF F1 (weighted): {f1:.4f}", file=sys.stderr)
    path = os.path.join(outdir, "random_forest.joblib")
    joblib.dump(rf, path)
    print(f"[+] Saved: {path}", file=sys.stderr)
    return rf


def build_lstm_sequences(df, feature_cols, seq_len=5):
    sequences = []
    labels = []
    label_map = {}
    for src_ip, group in df.groupby("src_ip"):
        group = group.sort_values("start_time")
        for i in range(len(group) - seq_len + 1):
            seq = group.iloc[i : i + seq_len]
            last_label = seq["label"].iloc[-1]
            X_vals = seq[feature_cols].values.astype(np.float64)
            sequences.append(X_vals)
            labels.append(last_label)
    if len(sequences) == 0:
        return np.array([]), np.array([]), {}
    all_labels = sorted(set(labels))
    label_map = {l: i for i, l in enumerate(all_labels)}
    return np.array(sequences), np.array(labels), label_map


def train_lstm(X_train_seq, y_train_seq, X_test_seq, y_test_seq, outdir, num_classes):
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("[!] TensorFlow not installed -- skipping LSTM", file=sys.stderr)
        print("    Install: pip install tensorflow", file=sys.stderr)
        return None

    flatten_dim = X_train_seq.shape[2]
    model = keras.Sequential([
        layers.Input(shape=(X_train_seq.shape[1], flatten_dim)),
        layers.LSTM(64, return_sequences=False),
        layers.Dense(32, activation="relu"),
        layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.fit(
        X_train_seq, y_train_seq,
        epochs=20,
        batch_size=16,
        validation_split=0.1,
        verbose=0,
    )
    y_pred = np.argmax(model.predict(X_test_seq, verbose=0), axis=1)
    f1 = f1_score(y_test_seq, y_pred, average="weighted")
    print(f"[+] LSTM F1 (weighted): {f1:.4f}", file=sys.stderr)
    path = os.path.join(outdir, "lstm_model.keras")
    model.save(path)
    print(f"[+] Saved: {path}", file=sys.stderr)
    return model


def train_autoencoder(X_train_norm, X_test, y_test, outdir):
    try:
        import tensorflow as tf
        from tensorflow import keras
        from tensorflow.keras import layers
    except ImportError:
        print("[!] TensorFlow not installed -- skipping Autoencoder", file=sys.stderr)
        print("    Install: pip install tensorflow", file=sys.stderr)
        return None

    input_dim = X_train_norm.shape[1]
    model = keras.Sequential([
        layers.Input(shape=(input_dim,)),
        layers.Dense(16, activation="relu"),
        layers.Dense(8, activation="relu"),
        layers.Dense(16, activation="relu"),
        layers.Dense(input_dim, activation="linear"),
    ])
    model.compile(optimizer="adam", loss="mse")
    model.fit(
        X_train_norm, X_train_norm,
        epochs=30,
        batch_size=16,
        validation_split=0.1,
        verbose=0,
    )

    reconstructions = model.predict(X_train_norm, verbose=0)
    errors = np.mean(np.square(X_train_norm - reconstructions), axis=1)
    threshold = float(np.mean(errors) + 3 * np.std(errors))

    test_reconstructions = model.predict(X_test, verbose=0)
    test_errors = np.mean(np.square(X_test - test_reconstructions), axis=1)
    y_pred_ae = (test_errors > threshold).astype(int)

    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    y_test_bin = le.fit_transform(y_test)
    f1 = f1_score(y_test_bin, y_pred_ae, average="weighted")
    print(f"[+] Autoencoder F1 (weighted): {f1:.4f}", file=sys.stderr)

    model_path = os.path.join(outdir, "autoencoder_model.keras")
    model.save(model_path)
    print(f"[+] Saved: {model_path}", file=sys.stderr)

    threshold_path = os.path.join(outdir, "autoencoder_threshold.json")
    with open(threshold_path, "w") as f:
        json.dump({"threshold": threshold}, f)
    print(f"[+] Saved: {threshold_path}", file=sys.stderr)

    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to labeled flows CSV")
    parser.add_argument("--outdir", required=True, help="Output directory for models")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print(f"[*] Loading data: {args.data}", file=sys.stderr)
    df = pd.read_csv(args.data)

    label_col = "label"
    feature_cols = [
        "duration", "total_packets", "total_bytes",
        "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
        "mean_pkt_len", "std_pkt_len", "mean_iat", "std_iat",
        "pkts_per_sec", "bytes_per_sec", "uncommon_port", "dst_ip_entropy",
    ]

    drop_cols = [c for c in feature_cols if c not in df.columns]
    if drop_cols:
        print(f"[!] Missing columns: {drop_cols}", file=sys.stderr)

    available_features = [c for c in feature_cols if c in df.columns]
    print(f"[+] Using {len(available_features)} features: {available_features}", file=sys.stderr)

    X = df[available_features].values
    y = df[label_col].values

    train_idx, test_idx = train_test_split(
        df.index, test_size=0.2, random_state=42, stratify=y
    )

    X_train = df.loc[train_idx, available_features].values
    X_test = df.loc[test_idx, available_features].values
    y_train = df.loc[train_idx, label_col].values
    y_test = df.loc[test_idx, label_col].values

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    holdout = df.loc[test_idx].copy()
    holdout_path = os.path.join(args.outdir, "holdout_test_set.csv")
    holdout.to_csv(holdout_path, index=False)
    print(f"[+] Saved holdout test set: {holdout_path}", file=sys.stderr)

    scaler_path = os.path.join(args.outdir, "scaler.joblib")
    joblib.dump(scaler, scaler_path)
    print(f"[+] Saved scaler: {scaler_path}", file=sys.stderr)

    rf_model = train_random_forest(X_train_scaled, y_train, X_test_scaled, y_test, args.outdir)

    y_test_numeric = pd.factorize(y_test)[0]
    y_train_numeric = pd.factorize(y_train)[0]
    num_classes = len(np.unique(y_test_numeric))

    lstm_data = df[[c for c in df.columns if c in available_features] + ["src_ip", "start_time", "label"]].copy()
    lstm_data = lstm_data.dropna(subset=available_features)

    seqs, seq_labels, label_map = build_lstm_sequences(lstm_data, available_features, seq_len=5)
    if len(seqs) < 20:
        print(f"[!] Only {len(seqs)} LSTM sequences (< 20) -- skipping LSTM", file=sys.stderr)
        print("    Capture more traffic per device or repeat attacks more times.", file=sys.stderr)
    else:
        label_ids = np.array([label_map[l] for l in seq_labels])
        train_seqs, test_seqs, train_slabels, test_slabels = train_test_split(
            seqs, label_ids, test_size=0.2, random_state=42
        )
        lstm_num_classes = len(label_map)
        lstm_model = train_lstm(train_seqs, train_slabels, test_seqs, test_slabels, args.outdir, lstm_num_classes)

    normal_mask = df[label_col] == "NORMAL"
    if normal_mask.sum() > 0:
        X_norm = df[normal_mask][available_features].values
        X_norm_scaled = scaler.transform(X_norm)
        ae_model = train_autoencoder(X_norm_scaled, X_test_scaled, y_test, args.outdir)
    else:
        print("[!] No NORMAL flows found -- skipping Autoencoder", file=sys.stderr)

    print("[+] Training complete", file=sys.stderr)


if __name__ == "__main__":
    main()
