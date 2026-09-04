# Thesis-Ready Results (auto-generated)

## Dataset
- Total labelled flows: 368256
- Training flows: 294604
- Test flows: 50936
- Classes (5): {"NORMAL": 343486, "C2_BEACON": 21452, "BRUTEFORCE": 2970, "EXFIL_RANSOMWARE": 256, "RECON": 92}
- Class distribution (train): {"NORMAL": 293238, "C2_BEACON": 574, "BRUTEFORCE": 444, "EXFIL_RANSOMWARE": 256, "RECON": 92}
- Class distribution (test): {"NORMAL": 50248, "BRUTEFORCE": 406, "C2_BEACON": 282}
- Features (15): duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes, mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec, uncommon_port, dst_ip_entropy

## Random Forest
- Accuracy: 0.9942
- Precision (macro): 0.5352
- Recall (macro): 0.4917
- Macro F1: 0.5051
- Weighted F1: 0.9944
- Per-class:
  - BRUTEFORCE: precision=0.8984, recall=0.5665, f1=0.6949, support=406
  - C2_BEACON: precision=0.7802, recall=0.8936, f1=0.8331, support=282
  - EXFIL_RANSOMWARE: precision=0.0000, recall=0.0000, f1=0.0000, support=0
  - NORMAL: precision=0.9972, recall=0.9982, f1=0.9977, support=50248
  - RECON: precision=0.0000, recall=0.0000, f1=0.0000, support=0

## LSTM
- Accuracy: 0.9898
- Precision (macro): 0.9489
- Recall (macro): 0.4762
- Macro F1: 0.5385
- Weighted F1: 0.9862
- Per-class:
  - BRUTEFORCE: precision=0.9820, recall=0.4039, f1=0.5724, support=406
  - C2_BEACON: precision=0.8750, recall=0.0248, f1=0.0483, support=282
  - EXFIL_RANSOMWARE: precision=0.0000, recall=0.0000, f1=0.0000, support=0
  - NORMAL: precision=0.9898, recall=0.9999, f1=0.9948, support=50181
  - RECON: precision=0.0000, recall=0.0000, f1=0.0000, support=0

- Sequence length: 5
- Training sequences: 294525
- Test sequences: 50869

## Autoencoder
- Threshold: 0.442225 (mean + 3*std of training-normal reconstruction error)
- Accuracy: 0.9866
- Precision (anomaly): 0.5410
- Recall (anomaly): 0.0480
- F1 (anomaly): 0.0881
- Confusion matrix: TN=50220 FP=28 FN=655 TP=33
