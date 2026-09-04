#!/usr/bin/env python3
"""Authoritative final evaluation entry point.

Loads saved models, scaler, label encoder and Autoencoder threshold.
NEVER retrains, NEVER fits the scaler, NEVER regenerates the label
mapping, NEVER recomputes the Autoencoder threshold.

Outputs all results into results/run_YYYYMMDD_HHMMSS/ and copies the
canonical result files to results/.
"""
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, precision_recall_fscore_support,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_common import (
    FEATURE_COLS, LABEL_COL, RANDOM_STATE, SEQ_LEN, TEST_SIZE,
    load_labeled_data, make_split, make_event_level_split, build_sequences,
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def load_artifacts(outdir):
    scaler = joblib.load(os.path.join(outdir, "scaler.joblib"))
    le = joblib.load(os.path.join(outdir, "label_encoder.joblib"))
    with open(os.path.join(outdir, "autoencoder_threshold.json")) as f:
        threshold = json.load(f)["threshold"]
    models = {}
    rf_path = os.path.join(outdir, "random_forest.joblib")
    if os.path.exists(rf_path):
        models["random_forest"] = joblib.load(rf_path)
    try:
        from tensorflow import keras
        lstm_path = os.path.join(outdir, "lstm_model.keras")
        if os.path.exists(lstm_path):
            models["lstm"] = keras.models.load_model(lstm_path)
        ae_path = os.path.join(outdir, "autoencoder_model.keras")
        if os.path.exists(ae_path):
            models["autoencoder"] = keras.models.load_model(ae_path)
    except ImportError:
        print("[!] TensorFlow not available -- LSTM/AE evaluation skipped", file=sys.stderr)
    return scaler, le, threshold, models


def get_test_set(args, outdir):
    """Return (X_test_df_rows, y_test) using the saved holdout partition.

    Reads the split_mode from training_metadata.json to reproduce the
    exact same split used during training.
    """
    # Determine split mode from training metadata
    meta_path = os.path.join(outdir, "training_metadata.json")
    split_mode = "stratified"
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        split_mode = meta.get("split_mode", "stratified")

    if getattr(args, "data", None):
        df = load_labeled_data(args.data)
        if split_mode == "event_level":
            print("[*] Reproducing EVENT-LEVEL split", file=sys.stderr)
            train_idx, test_idx = make_event_level_split(df)
        else:
            train_idx, test_idx = make_split(df)
        test_part = df.loc[test_idx]
        holdout_path = os.path.join(outdir, "holdout_test_set.csv")
        if os.path.exists(holdout_path):
            holdout = pd.read_csv(holdout_path)
            same = len(holdout) == len(test_part) and np.allclose(
                holdout[FEATURE_COLS].values, test_part[FEATURE_COLS].values,
                rtol=1e-12, atol=0)
            if same:
                print("[*] Holdout file verified against reproduced split",
                      file=sys.stderr)
            else:
                print("[!] Holdout file differs from reproduced split -- "
                      "using reproduced split", file=sys.stderr)
        return test_part, test_part[LABEL_COL].values
    holdout_path = os.path.join(outdir, "holdout_test_set.csv")
    if not os.path.exists(holdout_path):
        raise SystemExit("ERROR: no --data given and no holdout_test_set.csv found")
    holdout = pd.read_csv(holdout_path)
    return holdout, holdout[LABEL_COL].values


def classification_dict(y_true, y_pred, le):
    acc = accuracy_score(y_true, y_pred)
    p_mac = precision_score(y_true, y_pred, average="macro", zero_division=0)
    r_mac = recall_score(y_true, y_pred, average="macro", zero_division=0)
    f_mac = f1_score(y_true, y_pred, average="macro", zero_division=0)
    p_wtd = precision_score(y_true, y_pred, average="weighted", zero_division=0)
    r_wtd = recall_score(y_true, y_pred, average="weighted", zero_division=0)
    f_wtd = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    class_labels = list(le.classes_)
    prec, rec, f1s, sup = precision_recall_fscore_support(
        y_true, y_pred, labels=class_labels, zero_division=0)
    per_class = {}
    for i, cls in enumerate(class_labels):
        per_class[str(cls)] = {"precision": float(prec[i]), "recall": float(rec[i]),
                               "f1": float(f1s[i]), "support": int(sup[i])}
    return {
        "accuracy": float(acc),
        "precision_macro": float(p_mac), "recall_macro": float(r_mac),
        "f1_macro": float(f_mac),
        "precision_weighted": float(p_wtd), "recall_weighted": float(r_wtd),
        "f1_weighted": float(f_wtd),
        "per_class": per_class,
    }


def save_cm(cm, labels, title, run_dir, name):
    pd.DataFrame(cm, index=[f"true_{l}" for l in labels],
                 columns=[f"pred_{l}" for l in labels]).to_csv(
        os.path.join(run_dir, f"confusion_matrix_{name}.csv"))
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=labels, yticklabels=labels, ax=ax)
    ax.set_title(f"{title} - Confusion Matrix")
    ax.set_ylabel("True")
    ax.set_xlabel("Predicted")
    plt.tight_layout()
    fig.savefig(os.path.join(run_dir, f"confusion_matrix_{name}.png"), dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True, help="Models directory")
    parser.add_argument("--data", default=None, help="Labeled flows CSV (full dataset)")
    args = parser.parse_args()

    run_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.abspath(os.path.join(RESULTS_DIR, f"run_{run_ts}"))
    os.makedirs(run_dir, exist_ok=True)

    print("[*] Loading saved artifacts...", file=sys.stderr)
    scaler, le, threshold, models = load_artifacts(args.outdir)
    label_mapping = {str(c): int(i) for i, c in enumerate(le.classes_)}

    test_part, y_test = get_test_set(args, args.outdir)
    X_test_scaled = scaler.transform(test_part[FEATURE_COLS].values.astype(np.float64))
    print(f"[*] Test flows: {len(test_part)}", file=sys.stderr)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": RANDOM_STATE,
        "split": {"training_percentage": int((1 - TEST_SIZE) * 100),
                  "testing_percentage": int(TEST_SIZE * 100), "stratified": True},
        "feature_count": len(FEATURE_COLS),
        "feature_names": list(FEATURE_COLS),
        "training_samples": None,
        "testing_samples": int(len(test_part)),
        "label_mapping": label_mapping,
        "lstm_sequence_length": SEQ_LEN,
        "autoencoder_threshold": float(threshold),
        "models": {},
    }

    report_rows = []

    # ---------------- Random Forest ----------------
    if "random_forest" in models:
        print("[*] Evaluating Random Forest...", file=sys.stderr)
        rf = models["random_forest"]
        y_pred = rf.predict(X_test_scaled)
        m = classification_dict(y_test, y_pred, le)
        cm = confusion_matrix(y_test, y_pred, labels=le.classes_)
        save_cm(cm, le.classes_, "Random Forest", run_dir, "random_forest")
        summary["models"]["random_forest"] = m
        for cls, vals in m["per_class"].items():
            report_rows.append({"model": "random_forest", "class": cls,
                                **{k: v for k, v in vals.items()}})
        report_rows.append({"model": "random_forest", "class": "MACRO",
                            "precision": m["precision_macro"], "recall": m["recall_macro"],
                            "f1": m["f1_macro"], "support": len(y_test)})
        report_rows.append({"model": "random_forest", "class": "WEIGHTED",
                            "precision": m["precision_weighted"], "recall": m["recall_weighted"],
                            "f1": m["f1_weighted"], "support": len(y_test)})

    # ---------------- LSTM ----------------
    lstm_info = None
    if "lstm" in models:
        print("[*] Building LSTM TEST sequences from test partition only...", file=sys.stderr)
        X_seq, y_lab = build_sequences(test_part, scaler=scaler)
        lstm_info = {"sequence_length": SEQ_LEN,
                     "test_sequences": int(len(X_seq)),
                     "sequence_class_distribution": {
                         str(k): int(v) for k, v in pd.Series(y_lab).value_counts().items()}
                     if len(y_lab) else {}}
        summary["lstm_testing_sequences"] = int(len(X_seq))
        if len(X_seq) > 0:
            y_ids = le.transform(y_lab)
            prob = models["lstm"].predict(X_seq, verbose=0)
            y_pred_ids = np.argmax(prob, axis=1)
            y_true_labels = le.classes_[y_ids]
            y_pred_labels = le.classes_[y_pred_ids]
            m = classification_dict(y_true_labels, y_pred_labels, le)
            cm = confusion_matrix(y_true_labels, y_pred_labels, labels=le.classes_)
            save_cm(cm, le.classes_, "LSTM", run_dir, "lstm")
            summary["models"]["lstm"] = m
            for cls, vals in m["per_class"].items():
                report_rows.append({"model": "lstm", "class": cls,
                                    **{k: v for k, v in vals.items()}})
            report_rows.append({"model": "lstm", "class": "MACRO",
                                "precision": m["precision_macro"], "recall": m["recall_macro"],
                                "f1": m["f1_macro"], "support": len(y_true_labels)})
            report_rows.append({"model": "lstm", "class": "WEIGHTED",
                                "precision": m["precision_weighted"], "recall": m["recall_weighted"],
                                "f1": m["f1_weighted"], "support": len(y_true_labels)})

    # ---------------- Autoencoder ----------------
    if "autoencoder" in models:
        print("[*] Evaluating Autoencoder with SAVED threshold...", file=sys.stderr)
        ae = models["autoencoder"]
        recon = ae.predict(X_test_scaled, verbose=0)
        errors = np.mean(np.square(X_test_scaled - recon), axis=1)
        y_bin_true = np.array([0 if l == "NORMAL" else 1 for l in y_test])
        y_bin_pred = (errors > threshold).astype(int)
        acc = accuracy_score(y_bin_true, y_bin_pred)
        prec = precision_score(y_bin_true, y_bin_pred, zero_division=0)
        rec = recall_score(y_bin_true, y_bin_pred, zero_division=0)
        f1b = f1_score(y_bin_true, y_bin_pred, zero_division=0)
        cm = confusion_matrix(y_bin_true, y_bin_pred, labels=[0, 1])
        save_cm(cm, ["NORMAL", "ANOMALY"], "Autoencoder", run_dir, "autoencoder")
        m = {"accuracy": float(acc), "precision_binary_anomaly": float(prec),
             "recall_binary_anomaly": float(rec), "f1_binary_anomaly": float(f1b),
             "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]),
                                  "fn": int(cm[1, 0]), "tp": int(cm[1, 1])}}
        summary["models"]["autoencoder"] = m
        report_rows.append({"model": "autoencoder", "class": "ANOMALY(binary)",
                            "precision": float(prec), "recall": float(rec),
                            "f1": float(f1b), "support": int((y_bin_true == 1).sum())})
        report_rows.append({"model": "autoencoder", "class": "NORMAL(binary)",
                            "precision": precision_score(1 - y_bin_true, 1 - y_bin_pred, zero_division=0),
                            "recall": recall_score(1 - y_bin_true, 1 - y_bin_pred, zero_division=0),
                            "f1": f1_score(1 - y_bin_true, 1 - y_bin_pred, zero_division=0),
                            "support": int((y_bin_true == 0).sum())})

    # ---------------- Persist results ----------------
    flat = []
    for name, m in summary["models"].items():
        row = {"model": name}
        for k, v in m.items():
            if isinstance(v, dict):
                continue
            row[k] = v
        flat.append(row)
    pd.DataFrame(flat).to_csv(os.path.join(run_dir, "evaluation_results.csv"), index=False)
    pd.DataFrame(report_rows).to_csv(os.path.join(run_dir, "classification_report.csv"),
                                     index=False)

    train_meta_path = os.path.join(args.outdir, "training_metadata.json")
    if os.path.exists(train_meta_path):
        with open(train_meta_path) as f:
            meta = json.load(f)
        summary["training_samples"] = meta.get("training_flows",
                                               summary["training_samples"])
        summary["lstm_training_sequences"] = meta.get("lstm_training_sequences")
        summary["dataset_statistics"] = {
            "total_flows": meta.get("total_flows"),
            "class_distribution_total": meta.get("class_distribution_total"),
            "class_distribution_train": meta.get("class_distribution_train"),
            "class_distribution_test": meta.get("class_distribution_test"),
        }
    with open(os.path.join(run_dir, "evaluation_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Copy canonical files to results/ root
    for fname in ["evaluation_results.csv", "classification_report.csv",
                  "evaluation_summary.json",
                  "confusion_matrix_random_forest.csv",
                  "confusion_matrix_lstm.csv", "confusion_matrix_autoencoder.csv",
                  "confusion_matrix_random_forest.png",
                  "confusion_matrix_lstm.png", "confusion_matrix_autoencoder.png"]:
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(RESULTS_DIR, fname))

    write_thesis_results(summary, run_dir)
    shutil.copy2(os.path.join(run_dir, "thesis_results.md"),
                 os.path.join(RESULTS_DIR, "thesis_results.md"))

    print(f"[+] Results saved: {run_dir}", file=sys.stderr)
    print(json.dumps({k: v for k, v in summary["models"].items()}, indent=2),
          file=sys.stderr)
    print("[+] Evaluation complete", file=sys.stderr)


def write_thesis_results(summary, run_dir):
    def pct(x):
        return f"{x:.4f}"

    lines = ["# Thesis-Ready Results (auto-generated)", ""]
    ds = summary.get("dataset_statistics", {})
    lines += [
        "## Dataset",
        f"- Total labelled flows: {ds.get('total_flows', 'n/a')}",
        f"- Training flows: {summary['training_samples']}",
        f"- Test flows: {summary['testing_samples']}",
        f"- Classes ({len(summary['label_mapping'])}): "
        f"{json.dumps(ds.get('class_distribution_total', {}))}",
        f"- Class distribution (train): {json.dumps(ds.get('class_distribution_train', {}))}",
        f"- Class distribution (test): {json.dumps(ds.get('class_distribution_test', {}))}",
        f"- Features ({summary['feature_count']}): {', '.join(summary['feature_names'])}",
        "",
    ]
    for model in ["random_forest", "lstm"]:
        if model not in summary["models"]:
            continue
        m = summary["models"][model]
        title = "Random Forest" if model == "random_forest" else "LSTM"
        lines += [f"## {title}", f"- Accuracy: {pct(m['accuracy'])}",
                  f"- Precision (macro): {pct(m['precision_macro'])}",
                  f"- Recall (macro): {pct(m['recall_macro'])}",
                  f"- Macro F1: {pct(m['f1_macro'])}",
                  f"- Weighted F1: {pct(m['f1_weighted'])}",
                  "- Per-class:"]
        for cls, v in m["per_class"].items():
            lines.append(f"  - {cls}: precision={v['precision']:.4f}, "
                         f"recall={v['recall']:.4f}, f1={v['f1']:.4f}, "
                         f"support={v['support']}")
        lines.append("")
    if "lstm" in summary["models"]:
        lines += ["- Sequence length: " + str(summary["lstm_sequence_length"]),
                  "- Training sequences: " + str(summary.get("lstm_training_sequences")),
                  "- Test sequences: " + str(summary.get("lstm_testing_sequences")), ""]
    if "autoencoder" in summary["models"]:
        a = summary["models"]["autoencoder"]
        c = a["confusion_matrix"]
        lines += ["## Autoencoder",
                  f"- Threshold: {summary['autoencoder_threshold']:.6g} "
                  "(mean + 3*std of training-normal reconstruction error)",
                  f"- Accuracy: {pct(a['accuracy'])}",
                  f"- Precision (anomaly): {pct(a['precision_binary_anomaly'])}",
                  f"- Recall (anomaly): {pct(a['recall_binary_anomaly'])}",
                  f"- F1 (anomaly): {pct(a['f1_binary_anomaly'])}",
                  f"- Confusion matrix: TN={c['tn']} FP={c['fp']} FN={c['fn']} TP={c['tp']}",
                  ""]
    with open(os.path.join(run_dir, "thesis_results.md"), "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
