# Data Integrity Report (measured values)

- Total labelled flows: 153188
- Training flows (stratified 80/20, seed 42): 122550
- Testing flows: 30638
- Exact duplicate full rows within whole dataset: 66187
- Duplicate feature-vector rows within training partition: 42879
- Duplicate feature-vector rows within test partition: 2763
- Distinct feature vectors present in BOTH partitions: 20981 (of 79651 train / 27873 test distinct vectors)
- Identical flow identities (5-tuple + start_time) in BOTH partitions: 21037
- Test flows temporally overlapping at least one training flow (interleaved capture windows): 24231

## Attack episodes per partition

| label | episodes | in train | in test | in BOTH |
|---|---|---|---|---|
| C2_BEACON | 1 | 1 | 1 | 1 |
| EXFIL_RANSOMWARE | 1 | 1 | 1 | 1 |
| NORMAL | 2 | 2 | 2 | 2 |

## Notes

- Duplicated feature vectors arise from the periodic simulated normal traffic (MQTT/HTTP/ICMP loops), which produces byte-identical flows.
- Because the dataset is split at flow level (per the documented 80/20 methodology), near-identical periodic normal flows inevitably appear on both sides of the split. This was quantified above and NOT removed.
- RECON and BRUTEFORCE attack intervals contain 0 captured flows (attacks ran outside capture windows), so only NORMAL, C2_BEACON and EXFIL_RANSOMWARE are represented in the dataset.
- EXFIL_RANSOMWARE consists of a single ~1-second episode (100 flows); an event-level split would have to place all of it on one side, so an attack/session-aware Experiment B is not statistically performable on this dataset without inventing additional data.