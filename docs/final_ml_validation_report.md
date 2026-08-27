# Final ML Validation Report

Answers refer to the corrected pipeline executed 2026-08-25 (results in
`results/run_20260825_152339/` and `results/run_20260825_153340/` — identical).

## 1. What data was used?
`data/labeled_flows.csv` — flows extracted from 266 pcap segments of the Docker IoT
simulation and labelled against `data/attack_log.csv` intervals.

## 2. How many flows?
153,188 labelled flows (145,020 NORMAL / 8,068 C2_BEACON / 100 EXFIL_RANSOMWARE).
122,550 train / 30,638 test.

## 3. The 15 features
duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes,
mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec,
uncommon_port, dst_ip_entropy (single authoritative list: `ml/pipeline_common.py::FEATURE_COLS`).

## 4. How was the dataset split?
Stratified 80/20 flow-level split, `train_test_split(random_state=42, stratify=label)`.
Test partition persisted as `models/holdout_test_set.csv`. An attack/session-aware
split was **not** performed: EXFIL_RANSOMWARE exists as a single ~1 s episode, so it
cannot be spread across an event-level split; documented rather than faked.

## 5. How was scaling performed?
One `StandardScaler` fitted on training flows only → `models/scaler.joblib`; test data
and LSTM sequences transformed with that saved scaler. Evaluation never fits a scaler.

## 6. How were labels encoded?
One `LabelEncoder` fitted on training labels → `models/label_encoder.joblib`.
Mapping: `C2_BEACON=0, EXFIL_RANSOMWARE=1, NORMAL=2`. Evaluation loads this file.

## 7. How was Random Forest trained?
RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_split=5,
class_weight="balanced", random_state=42) on scaled training rows only. No test-set tuning.

## 8. How were LSTM sequences generated?
After the split, independently per partition: flows grouped by `src_ip`, sorted by
`start_time`, windows of length 5, label = last flow's label. 122,474 train sequences /
30,572 test sequences. No sequence crosses the train/test boundary.

## 9. How was the Autoencoder trained?
16→8→16→linear Dense AE, MSE loss, adam, 30 epochs, batch 16, on the 116,016
NORMAL flows of the **training partition only**.

## 10. How was the threshold calculated?
mean + 3 × std of per-flow reconstruction error on those same training-normal flows:
**0.045621540864318307**. Saved to `models/autoencoder_threshold.json`; evaluation only
loads it.

## 11. What leakage was found (original implementation)?
1. LSTM sequences were built over the full dataset before splitting, then randomly
   split — most test sequences shared 4 of their 5 flows with training data.
2. Autoencoder trained on all normal flows including test normals, and its threshold
   computed on them.
3. `evaluate.py` silently refit a scaler on the test set if `scaler.joblib` was absent.
4. Label mappings regenerated independently by sorting/factorize in both scripts; AE
   training F1 compared multiclass labels against binary predictions (invalid).
5. 21,037 identical flow identities appeared on both sides of the split (duplicate
   segment reprocessing + periodic traffic).

## 12. What was corrected?
Items 1–4 fully corrected as described above. Item 5 quantified (see
`docs/data_integrity_report.md`) but not "fixed" by deleting data — the documented
flow-level methodology is preserved and the duplication is reported as a limitation.

## 13. Remaining limitations
- Flow-level (not event-level) split: near-identical periodic normal flows occur in both
  partitions (~43 % duplicated rows overall), so RF results likely benefit from
  memorisation of repeated normal patterns.
- Only 3 classes present; RECON and BRUTEFORCE intervals contain zero captured flows.
- Extreme class imbalance (EXFIL = 100 flows, 20 in test); per-class metrics for it are
  high-variance.
- LSTM is heavily majority-biased despite balanced sequence labels not being applied;
  its high accuracy reflects the NORMAL class.
- Autoencoder anomaly F1 is very low (0.0082): attacks reconstructed well below the
  normal-derived threshold.
- No automated unit tests exist in the repository (unchanged).

## 14. Final model results (test partition)

| Model         | Accuracy | Precision | Recall | Macro F1 | Weighted F1 |
|---------------|---------:|----------:|-------:|---------:|------------:|
| Random Forest |   0.8698 |    0.9524*| 0.8698*|   0.6485 |      0.8994 |
| LSTM          |   0.9473 |    0.9380*| 0.9473*|   0.3670 |      0.9231 |
| Autoencoder   |   0.9447 |    0.0933 | 0.0043 | n/a (binary anomaly detection) | F1(anomaly)=0.0082 |

\* weighted averages. Macro precision/recall: RF 0.5996/0.8088; LSTM 0.6846/0.3569.
Autoencoder confusion matrix: TN=28,936 FP=68 FN=1,627 TP=7.

## 15. Are the results reproducible?
Yes. Two full runs with seed 42 produced byte-identical scaler parameters, RF feature
importances, label mapping, sequence counts, AE threshold, and identical metrics for all
three models (TensorFlow determinism enabled).

## 16. Figures to quote in the thesis
See `results/thesis_results.md` (auto-generated from the actual run).
