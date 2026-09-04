# Thesis-Ready Results (auto-generated)

## Dataset
- Total labelled flows: 383886
- Training flows: 307108
- Test flows: 44300
- Classes (5): {"NORMAL": 349712, "C2_BEACON": 22328, "RECON": 8138, "BRUTEFORCE": 3412, "EXFIL_RANSOMWARE": 296}
- Class distribution (train): {"NORMAL": 305600, "RECON": 1018, "C2_BEACON": 342, "BRUTEFORCE": 120, "EXFIL_RANSOMWARE": 28}
- Class distribution (test): {"NORMAL": 44112, "BRUTEFORCE": 98, "C2_BEACON": 74, "EXFIL_RANSOMWARE": 12, "RECON": 4}
- Features (15): duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes, mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec, uncommon_port, dst_ip_entropy

## Random Forest
- Accuracy: 0.9562
- Precision (macro): 0.5084
- Recall (macro): 0.5355
- Macro F1: 0.5061
- Weighted F1: 0.9766
- Per-class:
  - BRUTEFORCE: precision=0.8652, recall=0.7857, f1=0.8235, support=98
  - C2_BEACON: precision=0.4773, recall=0.8514, f1=0.6117, support=74
  - EXFIL_RANSOMWARE: precision=0.2000, recall=0.0833, f1=0.1176, support=12
  - NORMAL: precision=0.9996, recall=0.9571, f1=0.9779, support=44112
  - RECON: precision=0.0000, recall=0.0000, f1=0.0000, support=4

## LSTM
- Accuracy: 0.9969
- Precision (macro): 0.3885
- Recall (macro): 0.3061
- Macro F1: 0.3356
- Weighted F1: 0.9957
- Per-class:
  - BRUTEFORCE: precision=0.9455, recall=0.5306, f1=0.6797, support=98
  - C2_BEACON: precision=0.0000, recall=0.0000, f1=0.0000, support=74
  - EXFIL_RANSOMWARE: precision=0.0000, recall=0.0000, f1=0.0000, support=12
  - NORMAL: precision=0.9969, recall=0.9999, f1=0.9984, support=44046
  - RECON: precision=0.0000, recall=0.0000, f1=0.0000, support=4

- Sequence length: 5
- Training sequences: 307029
- Test sequences: 44234

## Autoencoder
- Threshold: 0.0348996 (mean + 3*std of training-normal reconstruction error)
- Accuracy: 0.9951
- Precision (anomaly): 0.3483
- Recall (anomaly): 0.1649
- F1 (anomaly): 0.2238
- Confusion matrix: TN=44054 FP=58 FN=157 TP=31
