#!/usr/bin/env python3
import argparse
import os
import sys
import json

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    roc_auc_score,
    roc_curve,
    auc,
)


def load_models(outdir):
    models = {}
    rf_path = os.path.join(outdir, "random_forest.joblib")
    if os.path.exists(rf_path):
        from sklearn.ensemble import RandomForestClassifier
        models["random_forest"] = joblib.load(rf_path)

    lstm_path = os.path.join(outdir, "lstm_model.keras")
    if os.path.exists(lstm_path):
        try:
            from tensorflow import keras
            models["lstm"] = keras.models.load_model(lstm_path)
        except Exception as e:
            print(f"[!] Could not load LSTM model: {e}", file=sys.stderr)

    ae_path = os.path.join(outdir, "autoencoder_model.keras")
    if os.path.exists(ae_path):
        try:
            from tensorflow import keras
            models["autoencoder"] = keras.models.load_model(ae_path)
        except Exception as e:
            print(f"[!] Could not load Autoencoder model: {e}", file=sys.stderr)

    return models


def load_threshold(outdir):
    thresh_path = os.path.join(outdir, "autoencoder_threshold.json")
    if os.path.exists(thresh_path):
        with open(thresh_path) as f:
            return json.load(f)["threshold"]
    return None


def evaluate_rf(model, X_test, y_test, outdir):
    le = LabelEncoder()
    y_test_enc = le.fit_transform(y_test)
    num_classes = len(le.classes_)

    y_pred = model.predict(X_test)
    y_pred_enc = le.transform(y_pred) if hasattr(le, "transform") else y_pred
    # handle case where y_pred contains unseen labels
    try:
        y_pred_enc = le.transform(y_pred)
    except:
        y_pred_enc = np.array([le.transform([p])[0] if p in le.classes_ else -1 for p in y_pred])

    y_prob = model.predict_proba(X_test)

    cm = confusion_matrix(y_test_enc, y_pred_enc, labels=range(num_classes))
    f1 = f1_score(y_test_enc, y_pred_enc, average="weighted")

    if num_classes == 2:
        roc_auc = roc_auc_score(y_test_enc, y_prob[:, 1])
    else:
        try:
            roc_auc = roc_auc_score(y_test_enc, y_prob, multi_class="ovr")
        except:
            roc_auc = float("nan")

    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")

    save_confusion_matrix(cm, le.classes_, "Random Forest", outdir, "rf_confusion_matrix.png")

    return {
        "model": "random_forest",
        "f1_score": f1,
        "roc_auc": roc_auc,
        "false_positive_rate": fpr,
        "confusion_matrix": cm.tolist(),
    }


def evaluate_lstm(model, X_test, y_test, outdir):
    le = LabelEncoder()
    y_test_enc = le.fit_transform(y_test)
    num_classes = len(le.classes_)

    y_prob = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_prob, axis=1)

    cm = confusion_matrix(y_test_enc, y_pred, labels=range(num_classes))
    f1 = f1_score(y_test_enc, y_pred, average="weighted")

    if num_classes == 2:
        roc_auc = roc_auc_score(y_test_enc, y_prob[:, 1])
    else:
        try:
            roc_auc = roc_auc_score(y_test_enc, y_prob, multi_class="ovr")
        except:
            roc_auc = float("nan")

    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")

    save_confusion_matrix(cm, le.classes_, "LSTM", outdir, "lstm_confusion_matrix.png")

    return {
        "model": "lstm",
        "f1_score": f1,
        "roc_auc": roc_auc,
        "false_positive_rate": fpr,
        "confusion_matrix": cm.tolist(),
    }


def evaluate_autoencoder(model, X_test, y_test, threshold, scaler, outdir):
    le = LabelEncoder()
    y_test_bin = le.fit_transform(y_test)

    reconstructions = model.predict(X_test, verbose=0)
    errors = np.mean(np.square(X_test - reconstructions), axis=1)
    y_pred = (errors > threshold).astype(int)

    cm = confusion_matrix(y_test_bin, y_pred)
    f1 = f1_score(y_test_bin, y_pred, average="binary")

    roc_auc = float("nan")
    try:
        roc_auc = roc_auc_score(y_test_bin, errors)
    except:
        pass

    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")

    save_confusion_matrix(cm, ["NORMAL", "ANOMALY"], "Autoencoder", outdir, "ae_confusion_matrix.png")

    return {
        "model": "autoencoder",
        "f1_score": f1,
        "roc_auc": roc_auc,
        "false_positive_rate": fpr,
        "confusion_matrix": cm.tolist(),
    }


def save_confusion_matrix(cm, labels, title, outdir, filename):
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_title(f"{title} - Confusion Matrix")
    ax.set_ylabel("True")
    ax.set_xlabel("Predicted")
    plt.tight_layout()
    path = os.path.join(outdir, filename)
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"[+] Saved: {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True, help="Models directory")
    parser.add_argument("--data", required=True, help="Labeled flows CSV (full dataset)")
    args = parser.parse_args()

    print(f"[*] Loading data: {args.data}", file=sys.stderr)
    df = pd.read_csv(args.data)

    feature_cols = [
        "duration", "total_packets", "total_bytes",
        "fwd_packets", "bwd_packets", "fwd_bytes", "bwd_bytes",
        "mean_pkt_len", "std_pkt_len", "mean_iat", "std_iat",
        "pkts_per_sec", "bytes_per_sec", "uncommon_port", "dst_ip_entropy",
    ]
    available_features = [c for c in feature_cols if c in df.columns]

    scaler_path = os.path.join(args.outdir, "scaler.joblib")
    holdout_path = os.path.join(args.outdir, "holdout_test_set.csv")

    if os.path.exists(holdout_path):
        print(f"[*] Using holdout test set: {holdout_path}", file=sys.stderr)
        holdout = pd.read_csv(holdout_path)
        X_test = holdout[available_features].values
        y_test = holdout["label"].values
    else:
        print("[*] No holdout set found -- using full dataset split", file=sys.stderr)
        X = df[available_features].values
        y = df["label"].values
        _, X_test, _, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

    if os.path.exists(scaler_path):
        scaler = joblib.load(scaler_path)
        X_test_scaled = scaler.transform(X_test)
    else:
        scaler = StandardScaler()
        X_test_scaled = scaler.fit_transform(X_test)

    models = load_models(args.outdir)
    threshold = load_threshold(args.outdir)

    results = []

    if "random_forest" in models:
        print("[*] Evaluating Random Forest...", file=sys.stderr)
        res = evaluate_rf(models["random_forest"], X_test_scaled, y_test, args.outdir)
        results.append(res)

    if "lstm" in models:
        print("[*] Building LSTM sequences for evaluation...", file=sys.stderr)
        lstm_data = df[[c for c in df.columns if c in available_features] + ["src_ip", "start_time", "label"]].copy()
        lstm_data = lstm_data.dropna(subset=available_features)
        seqs = []
        seq_labels = []
        for src_ip, group in lstm_data.groupby("src_ip"):
            group = group.sort_values("start_time")
            for i in range(len(group) - 5 + 1):
                seq = group.iloc[i : i + 5]
                last_label = seq["label"].iloc[-1]
                X_vals = seq[available_features].values.astype(np.float64)
                seqs.append(X_vals)
                seq_labels.append(last_label)
        if len(seqs) >= 20:
            all_labels = sorted(set(seq_labels))
            label_map = {l: i for i, l in enumerate(all_labels)}
            label_ids = np.array([label_map[l] for l in seq_labels])
            _, X_lstm_test, _, y_lstm_test_ids = train_test_split(
                np.array(seqs), label_ids, test_size=0.2, random_state=42
            )
            y_lstm_test_labels = np.array([all_labels[i] for i in y_lstm_test_ids])
            res = evaluate_lstm(
                models["lstm"], X_lstm_test, y_lstm_test_labels, args.outdir
            )
            results.append(res)
        else:
            print("[!] Not enough LSTM sequences for evaluation", file=sys.stderr)

    if "autoencoder" in models and threshold is not None:
        print("[*] Evaluating Autoencoder...", file=sys.stderr)
        res = evaluate_autoencoder(
            models["autoencoder"], X_test_scaled, y_test, threshold, scaler, args.outdir
        )
        results.append(res)

    results_df = pd.DataFrame(results)
    results_csv = os.path.join(args.outdir, "evaluation_results.csv")
    results_df.to_csv(results_csv, index=False)
    print(f"[+] Saved: {results_csv}", file=sys.stderr)
    print(results_df.to_string(), file=sys.stderr)

    print("[+] Evaluation complete", file=sys.stderr)


if __name__ == "__main__":
    main()
