#!/usr/bin/env python3
"""
Orchestrated experiment runner.

Runs on the HOST. Coordinates:
  - capture container (tcpdump)
  - attacker container (attack scripts)
  - iot-sensor container (normal traffic)
  - feature extraction, labelling, validation, ML pipeline

Every attack run gets a unique experiment_run ID.  The resulting
labelled_flows.csv includes columns: experiment_id, attack_run.

Usage:
    python scripts/run_experiment.py --repetitions 3
    python scripts/run_experiment.py --repetitions 5 --baseline 60 --cooldown 30
    python scripts/run_experiment.py --dry-run          # prints plan, does nothing
    python scripts/run_experiment.py --skip-capture      # assume capture already running
    python scripts/run_experiment.py --skip-attacks      # only process existing segments
"""
import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
SEG_DIR = ROOT / "data" / "segments"
DATA_DIR = ROOT / "data"
ML_DIR = ROOT / "ml"
MODELS_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"

CONTAINER_ATTACKER = "attacker"
CONTAINER_SENSOR = "iot-sensor"
CONTAINER_CAPTURE = "iot-capture"

ATTACKS = [
    {"name": "RECON",          "script": "/scripts/attack_recon.sh",      "duration_hint": 30},
    {"name": "BRUTEFORCE",     "script": "/scripts/attack_bruteforce.sh", "duration_hint": 60},
    {"name": "C2_BEACON",      "script": "/scripts/attack_beacon.sh 180", "duration_hint": 180},
    {"name": "EXFIL_RANSOMWARE","script": "/scripts/attack_exfil.sh",     "duration_hint": 15},
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def run(cmd, check=True, capture=True, timeout=600, shell=False):
    """Run a subprocess and return (returncode, stdout, stderr)."""
    r = subprocess.run(
        cmd, shell=shell, capture_output=capture, text=True, timeout=timeout
    )
    if check and r.returncode != 0:
        log(f"Command failed: {cmd}", "ERROR")
        if r.stderr:
            log(f"  stderr: {r.stderr.strip()[:500]}", "ERROR")
    return r.returncode, r.stdout.strip() if capture else "", r.stderr.strip() if capture else ""


def docker_exec(container, script, timeout=600):
    """Execute a script inside a container and return (exit_code, stdout)."""
    cmd = ["docker", "exec", container, "bash", "-c", script]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def list_segments():
    """Return sorted list of current pcap segment filenames."""
    if not SEG_DIR.exists():
        return []
    return sorted(f.name for f in SEG_DIR.iterdir()
                  if f.name.startswith("capture.pcap") and f.name != "capture.pcap")


def gen_experiment_id():
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    return f"EXP_{ts}_{short}"


# ── Phase functions ───────────────────────────────────────────────────────────
def phase_verify_containers():
    log("Phase: Verify containers")
    for name in [CONTAINER_ATTACKER, CONTAINER_SENSOR, CONTAINER_CAPTURE]:
        rc, out, _ = run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                         check=False)
        if rc != 0 or out.strip() != "true":
            log(f"  Container {name} is NOT running. Start with: docker compose up -d", "ERROR")
            return False
        log(f"  {name}: running")
    return True


def phase_start_listener():
    log("Phase: Ensure HTTP listener running in attacker")
    rc, out, _ = run(["docker", "exec", CONTAINER_ATTACKER,
                       "pgrep", "-f", "listener.py"], check=False)
    if rc == 0 and out:
        log("  Listener already running")
        return True
    rc, _, err = docker_exec(CONTAINER_ATTACKER,
                             "nohup python3 /scripts/listener.py > /tmp/listener.log 2>&1 &")
    time.sleep(2)
    rc2, out2, _ = run(["docker", "exec", CONTAINER_ATTACKER,
                         "pgrep", "-f", "listener.py"], check=False)
    if rc2 == 0 and out2:
        log("  Listener started")
        return True
    log("  WARNING: Could not confirm listener is running", "WARN")
    return True  # proceed anyway


def phase_start_capture():
    log("Phase: Start capture")
    # Use the numbered-file loop approach (not -G rotation) so
    # segments are named capture.pcap0, capture.pcap1, ... which
    # the ML pipeline expects.
    SEG_DIR.mkdir(parents=True, exist_ok=True)
    # Find the next segment number
    existing = list_segments()
    if existing:
        nums = []
        for f in existing:
            try:
                nums.append(int(f.replace("capture.pcap", "")))
            except ValueError:
                pass
        next_num = max(nums) + 1 if nums else 0
    else:
        next_num = 0

    # Get the Docker network bridge interface
    rc, net_name, _ = run(["docker", "network", "ls", "--format", "{{.Name}}"],
                          check=False, shell=False)
    iot_net = [n for n in net_name.split("\n") if "iot_sim_net" in n]
    if not iot_net:
        log("  ERROR: iot_sim_net network not found", "ERROR")
        return None, next_num

    rc, net_id, _ = run(["docker", "network", "inspect", iot_net[0],
                          "-f", "{{.Id}}"], check=False)
    bridge = f"br-{net_id[:12]}"

    # Build the capture command for iot-capture container (host network, privileged)
    # We write segments to the shared volume via the host's tcpdump
    cap_script = (
        f'COUNTER={next_num}; '
        f'while true; do '
        f'  FILE="/data/segments/capture.pcap$COUNTER"; '
        f'  timeout 30 tcpdump -i {bridge} -n -w "$FILE" 2>/dev/null; '
        f'  COUNTER=$((COUNTER + 1)); '
        f'  [ "$COUNTER" -ge 1000 ] && COUNTER=0; '
        f'  sleep 0.5; '
        f'done'
    )

    # Start in background using nohup inside the capture container
    # The capture container already has host network + privileged + volume mount
    proc = subprocess.Popen(
        ["docker", "exec", "-d", CONTAINER_CAPTURE, "bash", "-c", cap_script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    proc.wait(timeout=10)
    log(f"  Capture started (next segment: capture.pcap{next_num})")
    return bridge, next_num


def phase_validate_capture(next_num, wait=8):
    """Wait and verify that capture is producing segments."""
    log(f"Phase: Validate capture (waiting {wait}s)")
    time.sleep(wait)
    segs = list_segments()
    new_segs = [s for s in segs if s >= f"capture.pcap{next_num}"]
    if not new_segs:
        log("  WARNING: No new segments appeared. Capture may not be working.", "WARN")
        log("  Check: docker logs iot-capture", "WARN")
        return False
    # Check at least one segment has content
    for seg in new_segs[:2]:
        sz = (SEG_DIR / seg).stat().st_size
        if sz > 100:
            log(f"  Capture validated: {seg} ({sz:,} bytes)")
            return True
    log("  WARNING: Segments exist but appear empty", "WARN")
    return True  # proceed anyway


def phase_baseline(duration=30):
    log(f"Phase: Baseline normal traffic ({duration}s)")
    time.sleep(duration)
    log("  Baseline complete")


def phase_run_attack(attack_cfg, run_num, total_runs):
    """Execute one attack run. Returns (experiment_id, metadata dict)."""
    exp_id = gen_experiment_id()
    run_label = f"{attack_cfg['name']}_run{run_num:02d}"
    log(f"Phase: Attack [{run_label}] ({run_num}/{total_runs})  id={exp_id}")

    segs_before = set(list_segments())
    start_utc = datetime.now(timezone.utc)

    rc, stdout, stderr = docker_exec(CONTAINER_ATTACKER, attack_cfg["script"],
                                     timeout=attack_cfg["duration_hint"] + 120)

    end_utc = datetime.now(timezone.utc)
    segs_after = set(list_segments())
    new_segs = sorted(segs_after - segs_before)

    # Parse timestamps from attack script stdout
    attack_start = None
    attack_end = None
    for line in stdout.split("\n"):
        line = line.strip()
        if "_START" in line and not attack_start:
            attack_start = line.split(",")[0] if "," in line else start_utc.isoformat()
        if "_END" in line:
            attack_end = line.split(",")[0] if "," in line else end_utc.isoformat()

    meta = {
        "experiment_id": exp_id,
        "attack_name": attack_cfg["name"],
        "run_number": run_num,
        "total_runs": total_runs,
        "attack_run": run_label,
        "attack_script": attack_cfg["script"],
        "attack_start_utc": attack_start or start_utc.isoformat(),
        "attack_end_utc": attack_end or end_utc.isoformat(),
        "orchestrator_start_utc": start_utc.isoformat(),
        "orchestrator_end_utc": end_utc.isoformat(),
        "segments_before": sorted(segs_before),
        "segments_after": sorted(segs_after),
        "new_segments": new_segs,
        "attack_exit_code": rc,
        "attack_stdout_snippet": stdout[:2000],
    }

    if rc != 0:
        log(f"  WARNING: attack exited with code {rc}", "WARN")
        if stderr:
            log(f"  stderr: {stderr[:300]}", "WARN")

    log(f"  Done: {len(new_segs)} new segments")
    return exp_id, meta


def phase_stop_capture():
    log("Phase: Stop capture")
    run(["docker", "exec", CONTAINER_CAPTURE, "pkill", "-f", "tcpdump"],
        check=False)
    time.sleep(2)
    log("  Capture stopped")


def phase_extract_features(segment_files, flows_csv):
    """Extract features from specific segment files."""
    log(f"Phase: Extract features from {len(segment_files)} segments")
    count = 0
    for seg in segment_files:
        pcap_path = str(SEG_DIR / seg)
        tmp_csv = f"/tmp/exp_seg_{seg.replace('.', '_')}.csv"
        # Run extract_features on host (it reads the pcap via the volume)
        rc, _, err = run(
            [sys.executable, str(ML_DIR / "extract_features.py"),
             "--pcap", pcap_path, "--out", tmp_csv],
            check=False, timeout=300
        )
        if rc != 0:
            log(f"  WARNING: extraction failed for {seg}: {err[:200]}", "WARN")
            continue

        # Append to flows.csv
        if os.path.exists(tmp_csv) and os.path.getsize(tmp_csv) > 10:
            if flows_csv.exists():
                with open(tmp_csv, "r") as src:
                    header = src.readline()  # skip header
                    with open(flows_csv, "a") as dst:
                        for line in src:
                            dst.write(line)
            else:
                os.replace(tmp_csv, str(flows_csv))
                count += 1
                continue
            count += 1
        # Clean up temp
        try:
            os.remove(tmp_csv)
        except OSError:
            pass
    log(f"  Extracted features from {count} segments")


def phase_label_flows(flows_csv, attack_log_csv, labeled_csv):
    """Run label_flows.py to label all flows against the attack log."""
    log("Phase: Label flows")
    rc, out, err = run(
        [sys.executable, str(ML_DIR / "label_flows.py"),
         "--flows", str(flows_csv), "--log", str(attack_log_csv),
         "--out", str(labeled_csv)],
        check=False, timeout=120
    )
    if rc != 0:
        log(f"  Labelling failed: {err[:300]}", "ERROR")
        return False
    # Print label distribution
    import pandas as pd
    df = pd.read_csv(str(labeled_csv))
    log(f"  Total flows: {len(df)}")
    for label, count in df["label"].value_counts().items():
        log(f"    {label}: {count}")
    return True


def phase_annotate_flows(labeled_csv, experiment_log):
    """Add experiment_id and attack_run columns to labeled flows based on
    timestamp overlap with experiment metadata."""
    import pandas as pd

    log("Phase: Annotate flows with experiment metadata")
    df = pd.read_csv(str(labeled_csv))

    # Default columns
    df["experiment_id"] = ""
    df["attack_run"] = ""

    # Load experiment log entries
    entries = []
    for entry in experiment_log:
        try:
            start = datetime.fromisoformat(
                entry["attack_start_utc"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(
                entry["attack_end_utc"].replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        entries.append({
            "experiment_id": entry["experiment_id"],
            "attack_run": entry["attack_run"],
            "attack_name": entry["attack_name"],
            "start_ts": start.timestamp(),
            "end_ts": end.timestamp(),
        })

    # Assign experiment metadata to flows that fall within attack windows
    for idx, row in df.iterrows():
        fs = row.get("start_time", 0)
        fe = row.get("end_time", 0)
        for e in entries:
            if fs <= e["end_ts"] and fe >= e["start_ts"]:
                df.at[idx, "experiment_id"] = e["experiment_id"]
                df.at[idx, "attack_run"] = e["attack_run"]
                break

    # Save
    df.to_csv(str(labeled_csv), index=False)
    annotated = (df["experiment_id"] != "").sum()
    log(f"  Annotated {annotated} flows with experiment metadata")
    return True


def phase_validate_dataset(labeled_csv):
    """Run dataset_validator.py before training."""
    log("Phase: Validate dataset")
    rc, out, err = run(
        [sys.executable, str(ML_DIR / "dataset_validator.py"),
         "--data", str(labeled_csv)],
        check=False
    )
    print(out)
    if err:
        print(err, file=sys.stderr)
    return rc == 0


def phase_train_and_evaluate(labeled_csv, split_mode="event_level"):
    """Run the ML pipeline."""
    log(f"Phase: Train models (split_mode={split_mode})")
    rc1, out1, err1 = run(
        [sys.executable, str(ML_DIR / "train_models.py"),
         "--data", str(labeled_csv),
         "--outdir", str(MODELS_DIR),
         "--split-mode", split_mode],
        check=False, timeout=3600
    )
    print(out1)
    if err1:
        print(err1, file=sys.stderr)
    if rc1 != 0:
        log("  Training failed", "ERROR")
        return False

    log("Phase: Evaluate models")
    rc2, out2, err2 = run(
        [sys.executable, str(ML_DIR / "evaluate.py"),
         "--outdir", str(MODELS_DIR),
         "--data", str(labeled_csv)],
        check=False, timeout=1200
    )
    print(out2)
    if err2:
        print(err2, file=sys.stderr)
    return rc2 == 0


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Orchestrated experiment runner for IoT detection project")
    parser.add_argument("--repetitions", "-n", type=int, default=3,
                        help="Number of repetitions per attack type (default: 3)")
    parser.add_argument("--baseline", type=int, default=30,
                        help="Seconds of baseline normal traffic (default: 30)")
    parser.add_argument("--cooldown", type=int, default=20,
                        help="Seconds between attack runs (default: 20)")
    parser.add_argument("--post-cooldown", type=int, default=30,
                        help="Seconds after last attack before stopping capture (default: 30)")
    parser.add_argument("--split-mode", choices=["stratified", "event_level"],
                        default="event_level",
                        help="ML train/test split mode (default: event_level)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print experiment plan without executing")
    parser.add_argument("--skip-capture", action="store_true",
                        help="Assume capture is already running")
    parser.add_argument("--skip-attacks", action="store_true",
                        help="Skip attacks; only process existing segments")
    parser.add_argument("--attack-log", default=None,
                        help="Path to existing attack log to append to")
    parser.add_argument("--label-out", default=None,
                        help="Path for labelled output CSV")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    experiment_dir = DATA_DIR / f"experiment_{timestamp}"
    experiment_dir.mkdir(parents=True, exist_ok=True)

    attack_log_path = Path(args.attack_log) if args.attack_log else DATA_DIR / "attack_log.csv"
    labeled_path = Path(args.label_out) if args.label_out else DATA_DIR / "labeled_flows.csv"
    flows_path = DATA_DIR / "flows.csv"

    # ── Experiment plan ──
    total_attacks = args.repetitions * len(ATTACKS)
    est_seconds = (args.baseline
                   + total_attacks * 180  # generous per-attack estimate
                   + (total_attacks - 1) * args.cooldown
                   + args.post_cooldown)
    log("=" * 60)
    log("EXPERIMENT PLAN")
    log(f"  Repetitions per attack: {args.repetitions}")
    log(f"  Attacks: {[a['name'] for a in ATTACKS]}")
    log(f"  Total attack runs: {total_attacks}")
    log(f"  Baseline: {args.baseline}s")
    log(f"  Cooldown between runs: {args.cooldown}s")
    log(f"  Post-cooldown: {args.post_cooldown}s")
    log(f"  Estimated duration: ~{est_seconds // 60}m {est_seconds % 60}s")
    log(f"  Split mode: {args.split_mode}")
    log(f"  Experiment dir: {experiment_dir}")
    log("=" * 60)

    experiment_log = []

    if args.dry_run:
        log("DRY RUN — printing plan only")
        for i, atk in enumerate(ATTACKS, 1):
            for r in range(1, args.repetitions + 1):
                log(f"  [{i * r:2d}/{total_attacks}] {atk['name']}_run{r:02d}"
                    f"  ({atk['duration_hint']}s)")
        log("Dry run complete.")
        return

    # ── Execute ──
    try:
        if not args.skip_attacks:
            if not phase_verify_containers():
                sys.exit(1)
            phase_start_listener()

            if not args.skip_capture:
                bridge, next_num = phase_start_capture()
                if bridge is None:
                    sys.exit(1)
                phase_validate_capture(next_num)
            else:
                log("Phase: Skipping capture start (--skip-capture)")

            phase_baseline(args.baseline)

            # Run all attacks
            attack_idx = 0
            for atk in ATTACKS:
                for r in range(1, args.repetitions + 1):
                    attack_idx += 1
                    log(f"  [{attack_idx}/{total_attacks}]")
                    exp_id, meta = phase_run_attack(atk, r, args.repetitions)
                    experiment_log.append(meta)

                    # Save individual run metadata
                    run_path = experiment_dir / f"{meta['attack_run']}.json"
                    with open(run_path, "w") as f:
                        json.dump(meta, f, indent=2)

                    # Write to attack log for label_flows.py
                    _append_attack_log(attack_log_path, meta)

                    if attack_idx < total_attacks:
                        log(f"  Cooldown {args.cooldown}s...")
                        time.sleep(args.cooldown)

            phase_stop_capture()
            log(f"Post-attack cooldown {args.post_cooldown}s...")
            time.sleep(args.post_cooldown)
        else:
            log("Phase: Skipping attacks (--skip-attacks)")

        # ── Post-experiment processing ──
        # Identify segments from this experiment
        if not args.skip_attacks and experiment_log:
            all_new = []
            for meta in experiment_log:
                all_new.extend(meta.get("new_segments", []))
            new_segments = sorted(set(all_new))
        else:
            new_segments = list_segments()  # process everything

        log(f"Segments to process: {len(new_segments)}")
        phase_extract_features(new_segments, flows_path)
        phase_label_flows(flows_path, attack_log_path, labeled_path)

        if experiment_log:
            phase_annotate_flows(labeled_path, experiment_log)

        # Save full experiment manifest
        manifest_path = experiment_dir / "experiment_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump({
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "total_runs": len(experiment_log),
                "attacks": [m["attack_name"] for m in experiment_log],
                "repetitions_per_attack": args.repetitions,
                "split_mode": args.split_mode,
                "runs": experiment_log,
            }, f, indent=2)
        log(f"Experiment manifest: {manifest_path}")

        if not phase_validate_dataset(labeled_path):
            log("Dataset validation FAILED — aborting training", "ERROR")
            sys.exit(1)

        phase_train_and_evaluate(labeled_path, split_mode=args.split_mode)

        log("=" * 60)
        log("EXPERIMENT COMPLETE")
        log(f"  Experiment dir: {experiment_dir}")
        log(f"  Labelled flows: {labeled_path}")
        log(f"  Models: {MODELS_DIR}")
        log(f"  Results: {RESULTS_DIR}")
        log("=" * 60)

    except KeyboardInterrupt:
        log("Interrupted — stopping capture", "WARN")
        phase_stop_capture()
        sys.exit(130)


def _append_attack_log(log_path, meta):
    """Append START/END lines to attack_log.csv for label_flows.py.

    Format: timestamp,event_name,src_ip,dst_ip
    """
    # Attack scripts output: timestamp,EVENT_NAME,src_ip,dst_ip
    # We extract these from the attack stdout (lines containing _START/_END).
    src_ip = "192.168.50.99"
    dst_ip = "192.168.50.20"
    for line in meta.get("attack_stdout_snippet", "").split("\n"):
        line = line.strip()
        if "_START" in line and "," in line:
            parts = line.split(",")
            if len(parts) >= 4:
                src_ip = parts[2]
                dst_ip = parts[3]
            break
    with open(log_path, "a") as f:
        f.write(f"{meta['attack_start_utc']},{meta['attack_name']}_START,"
                f"{src_ip},{dst_ip}\n")
        f.write(f"{meta['attack_end_utc']},{meta['attack_name']}_END,"
                f"{src_ip},{dst_ip}\n")


if __name__ == "__main__":
    main()
