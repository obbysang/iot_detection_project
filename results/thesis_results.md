# Thesis-Ready Results (auto-generated)

## Dataset
- Total labelled flows: 153188
- Training flows: 122550
- Test flows: 30638
- Classes (3): {"NORMAL": 145020, "C2_BEACON": 8068, "EXFIL_RANSOMWARE": 100}
- Class distribution (train): {"NORMAL": 116016, "C2_BEACON": 6454, "EXFIL_RANSOMWARE": 80}
- Class distribution (test): {"NORMAL": 29004, "C2_BEACON": 1614, "EXFIL_RANSOMWARE": 20}
- Features (15): duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes, mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec, uncommon_port, dst_ip_entropy

## Random Forest
- Accuracy: 0.8698
- Precision (macro): 0.5996
- Recall (macro): 0.8088
- Macro F1: 0.6485
- Weighted F1: 0.8994
- Per-class:
  - C2_BEACON: precision=0.2697, recall=0.8556, f1=0.4102, support=1614
  - EXFIL_RANSOMWARE: precision=0.5385, recall=0.7000, f1=0.6087, support=20
  - NORMAL: precision=0.9906, recall=0.8707, f1=0.9268, support=29004

## LSTM
- Accuracy: 0.9473
- Precision (macro): 0.6846
- Recall (macro): 0.3569
- Macro F1: 0.3670
- Weighted F1: 0.9231
- Per-class:
  - C2_BEACON: precision=0.7727, recall=0.0211, f1=0.0410, support=1614
  - EXFIL_RANSOMWARE: precision=0.3333, recall=0.0500, f1=0.0870, support=20
  - NORMAL: precision=0.9476, recall=0.9996, f1=0.9729, support=28938

- Sequence length: 5
- Training sequences: 122474
- Test sequences: 30572

## Autoencoder
- Threshold: 0.0456215 (mean + 3*std of training-normal reconstruction error)
- Accuracy: 0.9447
- Precision (anomaly): 0.0933
- Recall (anomaly): 0.0043
- F1 (anomaly): 0.0082
- Confusion matrix: TN=28936 FP=68 FN=1627 TP=7
