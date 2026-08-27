# Thesis Sections Requiring Small Edits

Only the sections below need updating. Do not rewrite anything else.
All "new result" numbers come from `results/thesis_results.md` / `results/evaluation_summary.json`
(corrected pipeline, seed 42, run 2026-08-25).

---

## Section describing LSTM sequence creation (Chapter 4/5, wherever sequences are described)

Current statement (typical wording): sequences were created from flows and then split
into training/test sets.

Recommended replacement: "The dataset was first divided into stratified 80/20
training and test partitions. LSTM sequences of length 5 were then constructed
independently within each partition by ordering each device's flows chronologically
(sorted by start time); each sequence was labelled with the class of its most recent
flow. No sequence contains flows from both partitions."

Reason: original code built sequences over the whole dataset before splitting,
allowing sequences to span the train/test boundary (data leakage). Corrected in
`ml/train_models.py`.

---

## Section describing Autoencoder training/threshold

Current statement (typical wording): autoencoder trained on normal traffic; threshold =
mean + 3×std of reconstruction error.

Recommended replacement: add "trained exclusively on the 116,016 NORMAL flows of the
training partition; the threshold (mean + 3×std of reconstruction error on those same
training flows) is 0.0456215 and is stored and reused unchanged at evaluation time."

Reason: originally all normal flows of the full dataset (including test normals) were
used for both training and threshold calculation.

---

## Section describing scaling

Add one sentence: "The StandardScaler was fitted only on the training partition and
applied unchanged to the test partition and to LSTM inputs."

Reason: evaluation previously could refit a scaler on test data as a fallback.

---

## Section describing label encoding

Add: "A single label encoder was fitted on the training labels and persisted
(C2_BEACON=0, EXFIL_RANSOMWARE=1, NORMAL=2) and loaded unchanged during evaluation."

Reason: mappings were previously regenerated independently in two scripts.

---

## Results section — replace previous metric tables with:

Random Forest: accuracy 0.8698, weighted precision 0.9524, recall 0.8698,
macro F1 0.6485, weighted F1 0.8994.
Per-class F1: C2_BEACON 0.4102, EXFIL_RANSOMWARE 0.6087, NORMAL 0.9268.

LSTM (122,474 train / 30,572 test sequences, length 5): accuracy 0.9473,
weighted precision 0.9380, recall 0.9473, macro F1 0.3670, weighted F1 0.9231.
Per-class F1: C2_BEACON 0.0410, EXFIL_RANSOMWARE 0.0870, NORMAL 0.9729.
Note for discussion: the LSTM's high accuracy reflects majority-class (NORMAL)
prediction; attack-class recalls are ~2 % and ~5 %.

Autoencoder: threshold 0.0456215; accuracy 0.9447; anomaly precision 0.0933,
recall 0.0043, F1 0.0082; confusion matrix TN=28,936, FP=68, FN=1,627, TP=7.
Note: the autoencoder fails to generalise as an anomaly detector on this dataset;
report this honestly.

Previous values that must be replaced wherever quoted:
- RF weighted F1 0.8947 → 0.8994
- LSTM weighted F1 0.9123 → 0.9231 (but now leakage-free; per-class values changed drastically)
- AE weighted F1 0.0012 → replaced by binary-anomaly metrics above

---

## Dataset description section

Update if it currently claims RECON/BRUTEFORCE flows exist: they do not — zero flows
overlap those intervals. Only three classes are present:
NORMAL 145,020 / C2_BEACON 8,068 / EXFIL_RANSOMWARE 100 (total 153,188).

---

## Limitations section — add/confirm these statements

1. The split is flow-level; periodic simulated traffic produces many identical flow
   feature vectors (~43 % duplicated rows), some appearing in both partitions
   (20,981 distinct shared vectors). This inflates supervised results somewhat.
2. An attack/session-level split could not be performed because EXFIL_RANSOMWARE exists
   as a single episode.
3. The corrected results were produced after fixing the LSTM/AE/scaler/label-encoding
   leakage present in the original implementation (documented in
   docs/ml_evaluation_audit.md).
