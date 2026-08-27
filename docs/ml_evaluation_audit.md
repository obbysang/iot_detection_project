# ML Evaluation Pipeline Audit

Date: 2026-08-25. All numbers below were measured directly from `data/labeled_flows.csv`,
`data/flows.csv`, `data/attack_log.csv`, `models/` artifacts, and the code in `ml/`.
No values are estimated.

## 1. Data flow (actual)

```
tcpdump (30 s segments → data/segments/capture.pcapN, 266 segments present)
   → scripts/live_update.sh appends per-segment flows to data/flows.csv (162,174 rows)
   → ml/extract_features.py  (scapy; unidirectional keyed on src 5-tuple)
   → ml/label_flows.py       (overlaps flow [start,end] against data/attack_log.csv intervals)
   → data/labeled_flows.csv  (153,188 rows × 23 columns)   ← dataset used for training/evaluation
```

Note: `flows.csv` (162,174 rows) is ahead of `labeled_flows.csv` (153,188 rows); the
labelled file is the authoritative dataset for this evaluation.

## 2. Segments / flows / labels (measured)

- PCAP segments in `data/segments/`: **266**
- Labelled flows: **153,188**
- Capture period covered: 2026-07-31 14:58:59 UTC – 2026-08-01 14:54:56 UTC
- Attack log intervals parsed: 9 valid START/END pairs
- Flow overlap per attack type:
  - RECON: **0 flows** (2 intervals, both outside capture windows)
  - BRUTEFORCE: **0 flows** (2 intervals, both outside capture windows)
  - C2_BEACON: **8,068 flows** (2 intervals, ~13 s apart → effectively one episode)
  - EXFIL_RANSOMWARE: **100 flows** (single ~1-second interval)

## 3. Classes and distribution (measured)

| label             | flows  | share    |
|-------------------|-------:|---------:|
| NORMAL            | 145,020 | 94.66 % |
| C2_BEACON         |   8,068 |  5.27 % |
| EXFIL_RANSOMWARE  |     100 |  0.065 % |

Only 3 classes exist in the labelled data (RECON/BRUTEFORCE produced no captured flows).

## 4. The 15 features (identical order used throughout)

`duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes,
mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec,
uncommon_port, dst_ip_entropy`

Training and evaluation already used the same list/order (hard-coded identically in both
scripts), but it was duplicated in two places. **Correction:** now defined once in
`ml/pipeline_common.py::FEATURE_COLS` and imported by both scripts.

## 5. Existing behaviour vs. recommended correction

### 5.1 Train/test split
- **Existing:** stratified 80/20, `random_state=42`, split by `df.index` — correct in
  principle. Test partition persisted as `models/holdout_test_set.csv` (30,638 rows).
- **Correction:** kept unchanged; moved into shared `make_split()` so training and
  evaluation reproduce byte-identical partitions (verified: only float CSV round-trip
  differences of ≤1 ULP in 57 cells).

### 5.2 Scaler
- **Existing behaviour:** `StandardScaler` fitted on training data only and saved —
  mostly correct. However, `ml/evaluate.py` lines 214–216 **silently fitted a new
  scaler on the test set** if `scaler.joblib` was missing.
- **Correction:** evaluate.py now *requires* the saved scaler; no fitting path exists.
  Scaler is additionally applied to LSTM sequence features (previously LSTM trained on
  unscaled features while RF/AE used scaled ones).

### 5.3 Label encoding
- **Existing behaviour:** three independent mappings:
  - RF: string labels passed directly (fine);
  - LSTM: `{label: id}` built from `sorted(set(labels))` over the **full dataset**
    (`train_models.py:53–54`) and rebuilt independently in `evaluate.py:243–244`;
  - Autoencoder F1 inside `train_models.py:131–134`: `LabelEncoder().fit_transform`
    on multiclass y_test compared against a binary prediction — **invalid comparison**
    (alphabetical mapping makes C2_BEACON=0, EXFIL=1, NORMAL=2 vs. binary 0/1).
  - Additionally `pd.factorize(y_train)`/`pd.factorize(y_test)` were computed
    separately (train_models.py:202–203), which can assign different IDs per partition.
- **Correction:** one `LabelEncoder` fitted on **training labels**, saved to
  `models/label_encoder.joblib`, loaded by evaluate.py. Final recorded mapping:
  `C2_BEACON=0, EXFIL_RANSOMWARE=1, NORMAL=2`.

### 5.4 Random Forest
- **Existing/kept:** 200 trees, max_depth 20, min_samples_split 5, class_weight
  "balanced", random_state 42 — trained on scaled training partition only. No bug found;
  hyperparameters preserved. No tuning against the test set was performed or added.

### 5.5 LSTM — data leakage (confirmed)
- **Existing behaviour:** sequences were built over the **full dataset** grouped by
  `src_ip`, sorted by `start_time`, seq_len 5 (`train_models.py:39–55, 209`), then the
  finished sequences were randomly split 80/20 (`train_models.py:215`). Consecutive
  flows of the same host appear in overlapping windows, so **~4 out of every 5 test
  sequences shared 4 of their 5 flows with the training set** — direct train/test
  contamination. `evaluate.py:232–249` repeated the same construction.
- **Corrected final evaluation:** the 80/20 split is applied first; sequences are then
  built independently from the training rows and from the test rows. A sequence can
  never cross the boundary. Sequence rule preserved: per `src_ip`, sorted by
  `start_time`, length 5, label = label of last flow.
- Resulting counts: **122,474 training sequences / 30,572 test sequences**.

### 5.6 Autoencoder — threshold/training leakage (confirmed)
- **Existing behaviour:** AE was trained on ALL normal flows of the full dataset
  (`train_models.py:221–225`, includes test normals), and the threshold
  `mean + 3×std` of reconstruction error was computed on those same all-dataset normal
  flows — i.e., test information influenced both weights and threshold.
- **Corrected final evaluation:** AE trained on the **116,016 NORMAL flows of the
  training partition only**; threshold computed from reconstruction errors of exactly
  those flows: **threshold = 0.045621540864318307** (mean + 3×std), saved to
  `models/autoencoder_threshold.json`. Evaluation loads the saved threshold and never
  recomputes it.

### 5.7 Evaluation procedure inconsistencies (existing)
- `evaluate.py` re-derived the LSTM test subset by re-running the same random split on
  regenerated sequences — fragile coupling, removed.
- Metrics reported previously: weighted F1, ROC-AUC, FPR only; confusion matrix PNGs.
  No accuracy/macro metrics/per-class reports/classification CSVs.
- **Correction:** `results/` now contains accuracy, macro & weighted precision/recall/F1,
  full per-class precision/recall/F1/support, confusion matrices (CSV + PNG),
  `evaluation_summary.json`, `classification_report.csv`, `evaluation_results.csv`,
  `thesis_results.md`, each run timestamped under `results/run_YYYYMMDD_HHMMSS/`.

## 6. Duplicates / contamination (measured, see docs/data_integrity_report.md)

- Exact duplicate full rows in dataset: **66,187** (~43 %) — periodic simulated traffic.
- Distinct feature vectors appearing in BOTH partitions after split: **20,981**.
- Identical flow identities (5-tuple + start_time) in BOTH partitions: **21,037**
  (reprocessed segments appended duplicate flows).
- Every attack episode appears in BOTH partitions under the flow-level split.

## 7. Experiment B (attack/session-aware split)

Not implemented, deliberately. The repository contains only two C2_BEACON episodes
13 s apart and a single 1-second EXFIL episode; any event-level split must place all
EXFIL_RANSOMWARE flows on one side, making a stratified session-aware experiment
statistically impossible without inventing additional capture sessions. This is
documented rather than fabricated.

## 8. Reproducibility

Two complete training runs with seed 42 produced identical results: scaler parameters,
RF feature importances, label mapping, sequence counts, AE threshold, and all three
models' evaluation metrics matched exactly. TensorFlow determinism was enabled via
`tf.keras.utils.set_random_seed(42)` and `tf.config.experimental.enable_op_determinism()`.
