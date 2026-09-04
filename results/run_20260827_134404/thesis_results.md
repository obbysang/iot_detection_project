# Thesis-Ready Results (auto-generated)

## Dataset
- Total labelled flows: 376054
- Training flows: 300843
- Test flows: 50697
- Classes (5): {"NORMAL": 343576, "C2_BEACON": 21912, "RECON": 7116, "BRUTEFORCE": 3194, "EXFIL_RANSOMWARE": 256}
- Class distribution (train): {"NORMAL": 295065, "RECON": 5022, "C2_BEACON": 358, "EXFIL_RANSOMWARE": 256, "BRUTEFORCE": 142}
- Class distribution (test): {"NORMAL": 48511, "RECON": 2002, "C2_BEACON": 102, "BRUTEFORCE": 82}
- Features (15): duration, total_packets, total_bytes, fwd_packets, bwd_packets, fwd_bytes, bwd_bytes, mean_pkt_len, std_pkt_len, mean_iat, std_iat, pkts_per_sec, bytes_per_sec, uncommon_port, dst_ip_entropy

## Random Forest
- Accuracy: 0.9634
- Precision (macro): 0.5899
- Recall (macro): 0.6737
- Macro F1: 0.6084
- Weighted F1: 0.9686
- Per-class:
  - BRUTEFORCE: precision=0.7358, recall=0.4756, f1=0.5778, support=82
  - C2_BEACON: precision=0.6738, recall=0.9314, f1=0.7819, support=102
  - EXFIL_RANSOMWARE: precision=0.0000, recall=0.0000, f1=0.0000, support=0
  - NORMAL: precision=0.9992, recall=0.9629, f1=0.9807, support=48511
  - RECON: precision=0.5407, recall=0.9985, f1=0.7015, support=2002

## LSTM
- Accuracy: 0.9576
- Precision (macro): 0.7706
- Recall (macro): 0.3849
- Macro F1: 0.4525
- Weighted F1: 0.9400
- Per-class:
  - BRUTEFORCE: precision=0.9000, recall=0.3293, f1=0.4821, support=82
  - C2_BEACON: precision=0.7200, recall=0.1765, f1=0.2835, support=102
  - EXFIL_RANSOMWARE: precision=0.0000, recall=0.0000, f1=0.0000, support=0
  - NORMAL: precision=0.9590, recall=0.9984, f1=0.9783, support=48444
  - RECON: precision=0.5035, recall=0.0355, f1=0.0663, support=2002

- Sequence length: 5
- Training sequences: 300764
- Test sequences: 50630

## Autoencoder
- Threshold: 0.096018 (mean + 3*std of training-normal reconstruction error)
- Accuracy: 0.9566
- Precision (anomaly): 0.3519
- Recall (anomaly): 0.0087
- F1 (anomaly): 0.0170
- Confusion matrix: TN=48476 FP=35 FN=2167 TP=19
