import asyncio
import json
import os
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

app = FastAPI(title="IoT NIDS Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = {
    "flows_df": None,
    "evaluation": None,
    "attack_log": [],
    "last_loaded": 0.0,
    "pipeline_phase": "INIT",
    "models_available": [],
    "phase_history": [],
}

PROTO_MAP = {6: "TCP", 17: "UDP", 1: "ICMP"}

PIPELINE_ORDER = [
    "BUILD", "RUNNING", "CAPTURING", "ATTACKING",
    "POST_CAPTURE", "FEATURE_EXTRACTION", "LABELING",
    "TRAINING", "EVALUATION",
]


def get_pipeline_phase() -> str:
    eval_csv = MODELS_DIR / "evaluation_results.csv"
    model_files = list(MODELS_DIR.glob("*.joblib")) + list(MODELS_DIR.glob("*.keras"))
    labeled_csv = DATA_DIR / "labeled_flows.csv"
    attack_log = DATA_DIR / "attack_log.csv"
    pcap_files = list(DATA_DIR.glob("*.pcap")) + list(DATA_DIR.glob("*.pcapng"))
    flows_csv = DATA_DIR / "flows.csv"

    if eval_csv.exists():
        return "EVALUATION"
    if model_files:
        return "TRAINING"
    if labeled_csv.exists():
        return "LABELING"
    if attack_log.exists():
        return "ATTACKING"
    if pcap_files:
        return "POST_CAPTURE"
    if flows_csv.exists():
        return "RUNNING"
    return "BUILD"


def load_data():
    now = time.time()
    phase = get_pipeline_phase()
    if phase != cache["pipeline_phase"]:
        cache["phase_history"].append({
            "phase": phase,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "t": datetime.utcnow().isoformat() + "Z",
            "level": "info",
            "msg": f"Pipeline · → {phase}",
        })
    cache["pipeline_phase"] = phase

    model_files = []
    for ext in ["*.joblib", "*.keras"]:
        model_files.extend(MODELS_DIR.glob(ext))
    cache["models_available"] = sorted(p.name for p in model_files)

    eval_csv = MODELS_DIR / "evaluation_results.csv"
    if eval_csv.exists() and eval_csv.stat().st_mtime > cache["last_loaded"]:
        try:
            df = pd.read_csv(eval_csv)
            records = {}
            for _, row in df.iterrows():
                model_name = row.get("model", "unknown")
                records[model_name] = {
                    "f1_score": float(row.get("f1_score", 0)),
                    "roc_auc": float(row.get("roc_auc", 0)),
                    "false_positive_rate": float(row.get("false_positive_rate", 0)),
                }
            cache["evaluation"] = records
        except Exception as e:
            print(f"[dashboard-api] Error loading evaluation: {e}")

    sources = [
        ("holdout_test_set", MODELS_DIR / "holdout_test_set.csv"),
        ("labeled_flows", DATA_DIR / "labeled_flows.csv"),
        ("flows", DATA_DIR / "flows.csv"),
    ]
    for name, src in sources:
        if src.exists() and src.stat().st_mtime > cache["last_loaded"]:
            try:
                df = pd.read_csv(src)
                if "proto" in df.columns and df["proto"].dtype in (int, float):
                    df["proto"] = df["proto"].map(PROTO_MAP).fillna("OTHER")
                if "start_time" in df.columns:
                    df["start_time_dt"] = pd.to_datetime(df["start_time"], unit="s")
                cache["flows_df"] = df
                cache["last_loaded"] = now
                break
            except Exception as e:
                print(f"[dashboard-api] Error loading {name}: {e}")

    attack_log_path = DATA_DIR / "attack_log.csv"
    if attack_log_path.exists() and attack_log_path.stat().st_mtime > cache["last_loaded"]:
        try:
            cache["attack_log"] = attack_log_path.read_text().splitlines()
            cache["last_loaded"] = now
        except Exception as e:
            print(f"[dashboard-api] Error loading attack log: {e}")


load_data()


def _notify_event(level: str, msg: str):
    cache.setdefault("events_queue", []).append({
        "t": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "msg": msg,
    })


async def refresh_loop():
    while True:
        old_phase = cache["pipeline_phase"]
        load_data()
        new_phase = cache["pipeline_phase"]
        if new_phase != old_phase:
            _notify_event("info", f"Pipeline · → {new_phase}")
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup():
    asyncio.create_task(refresh_loop())


def get_flows_df():
    df = cache.get("flows_df")
    if df is None or df.empty:
        return pd.DataFrame()
    return df


def get_evaluation():
    return cache.get("evaluation") or {}


def compute_kpis(df: pd.DataFrame, evaluation: dict) -> dict:
    n = len(df)
    if n == 0:
        return {
            "avg_throughput_pkts": 0,
            "total_bytes": 0,
            "active_flows": 0,
            "flagged_flows": 0,
            "avg_anomaly_score": 0,
            "detection_rate": 0,
            "f1_scores": {},
            "pipeline_phase": cache["pipeline_phase"],
        }

    total_bytes = int(df["total_bytes"].sum()) if "total_bytes" in df.columns else 0
    avg_pkts = float(df["pkts_per_sec"].mean()) if "pkts_per_sec" in df.columns else 0
    attack_count = int((df["label"] != "NORMAL").sum()) if "label" in df.columns else 0
    detection_rate = round((attack_count / n) * 100, 1) if n > 0 else 0

    avg_anomaly = 0.0
    if "dst_ip_entropy" in df.columns:
        anomaly_mask = df["label"] != "NORMAL" if "label" in df.columns else pd.Series([False] * n)
        anomaly_scores = df["dst_ip_entropy"].copy()
        anomaly_scores[anomaly_mask] *= 0.12
        anomaly_scores[~anomaly_mask] *= 0.02
        avg_anomaly = round(float(anomaly_scores.mean()), 3)

    f1_scores = {}
    for model_name, metrics in evaluation.items():
        f1_scores[model_name] = round(metrics.get("f1_score", 0), 4)

    return {
        "avg_throughput_pkts": round(avg_pkts, 1),
        "total_bytes": total_bytes,
        "active_flows": n,
        "flagged_flows": attack_count,
        "avg_anomaly_score": avg_anomaly,
        "detection_rate": detection_rate,
        "f1_scores": f1_scores,
        "pipeline_phase": cache["pipeline_phase"],
    }


def compute_timeline(df: pd.DataFrame) -> dict:
    labels = []
    pkts = []
    anomaly = []

    if df.empty or "start_time_dt" not in df.columns:
        now = datetime.utcnow()
        for i in range(30):
            t = now.timestamp() - (30 - i)
            labels.append(datetime.utcfromtimestamp(t).strftime("%H:%M:%S"))
            pkts.append(0)
            anomaly.append(0)
        return {"labels": labels, "pkts": pkts, "anomaly": anomaly}

    df_sorted = df.sort_values("start_time_dt")
    min_t = df_sorted["start_time_dt"].min()
    max_t = df_sorted["start_time_dt"].max()
    span = (max_t - min_t).total_seconds()

    if span < 60:
        bins = max(10, int(span) + 1)
    else:
        bins = min(60, int(span))

    if bins < 2:
        bins = 2

    try:
        df_sorted["bucket"] = pd.cut(
            df_sorted["start_time_dt"],
            bins=bins,
            labels=False,
        )
    except Exception:
        for i in range(30):
            t = datetime.utcnow().timestamp() - (30 - i)
            labels.append(datetime.utcfromtimestamp(t).strftime("%H:%M:%S"))
            pkts.append(0)
            anomaly.append(0)
        return {"labels": labels, "pkts": pkts, "anomaly": anomaly}

    for bucket_id in range(bins):
        bucket_df = df_sorted[df_sorted["bucket"] == bucket_id]
        if bucket_df.empty:
            if labels:
                prev_t = datetime.strptime(labels[-1], "%H:%M:%S")
            else:
                prev_t = min_t
            next_t = prev_t + pd.Timedelta(seconds=max(1, span / bins))
            labels.append(next_t.strftime("%H:%M:%S"))
            pkts.append(0)
            anomaly.append(0)
            continue

        mid_time = bucket_df["start_time_dt"].mean()
        labels.append(mid_time.strftime("%H:%M:%S"))

        avg_pkts = float(bucket_df["pkts_per_sec"].mean()) if "pkts_per_sec" in bucket_df.columns else 0
        pkts.append(round(avg_pkts, 1))

        if "dst_ip_entropy" in bucket_df.columns:
            mask = bucket_df["label"] != "NORMAL" if "label" in bucket_df.columns else pd.Series([False] * len(bucket_df))
            scores = bucket_df["dst_ip_entropy"].copy()
            scores[mask] *= 0.12
            scores[~mask] *= 0.02
            avg_anom = float(scores.mean())
        else:
            avg_anom = 0.0
        anomaly.append(round(avg_anom, 3))

    return {"labels": labels, "pkts": pkts, "anomaly": anomaly}


# ── Control Endpoints (Capture / Pipeline / Attacks) ─────

CONTROL_PROCESSES: dict[str, subprocess.Popen] = {}

@app.post("/api/control/capture/start")
async def control_capture_start():
    if await _capture_is_running():
        return {"status": "already_running"}
    try:
        seg_dir = "/data/segments"
        result = subprocess.run(
            ["docker", "exec", "iot-capture", "sh", "-c",
             f"nohup tcpdump -i any -G 30 -W 500 -w {seg_dir}/capture.pcap -n > /dev/null 2>&1 &"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "docker exec failed"
            return {"status": "error", "message": err}
        await asyncio.sleep(1)
        if not await _capture_is_running():
            return {"status": "error", "message": "tcpdump failed to start"}
        _notify_event("info", "Capture started on iot-capture container")
        return {"status": "started"}
    except FileNotFoundError:
        return {"status": "error", "message": "Docker CLI not available"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def _capture_is_running() -> bool:
    try:
        r = subprocess.run(
            ["docker", "exec", "iot-capture", "pgrep", "tcpdump"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False

@app.post("/api/control/capture/stop")
async def control_capture_stop():
    if not await _capture_is_running():
        return {"status": "not_running"}
    try:
        subprocess.run(
            ["docker", "exec", "iot-capture", "pkill", "tcpdump"],
            capture_output=True, timeout=10,
        )
        _notify_event("info", "Capture stopped")
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/control/pipeline/start")
async def control_pipeline_start():
    if "pipeline" in CONTROL_PROCESSES:
        p = CONTROL_PROCESSES["pipeline"]
        if p.poll() is None:
            return {"status": "already_running"}
    try:
        proc = subprocess.Popen(
            ["bash", str(BASE_DIR / "scripts/live_update.sh")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid, cwd=str(BASE_DIR),
        )
        CONTROL_PROCESSES["pipeline"] = proc
        _notify_event("info", "ML pipeline started")
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/control/pipeline/stop")
async def control_pipeline_stop():
    proc = CONTROL_PROCESSES.pop("pipeline", None)
    if proc and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            _notify_event("info", "ML pipeline stopped")
        except Exception:
            pass
        return {"status": "stopped"}
    return {"status": "not_running"}

ATTACK_TYPES = {"recon", "bruteforce", "beacon", "exfil"}

@app.post("/api/control/attack/{attack_type}")
async def control_attack(attack_type: str, duration: int = 180):
    if attack_type not in ATTACK_TYPES:
        return {"status": "error", "message": f"invalid type. valid: {', '.join(sorted(ATTACK_TYPES))}"}

    script = f"/scripts/attack_{attack_type}.sh"
    cmd = ["docker", "exec", "attacker", "bash", script]
    if attack_type == "beacon":
        cmd.append(str(duration))

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=600, cwd=str(BASE_DIR),
        )
        attack_log = BASE_DIR / "data" / "attack_log.csv"
        with open(attack_log, "a") as f:
            f.write(result.stdout)
        _notify_event("attack", f"Attack · {attack_type} completed")
        return {"status": "completed", "output": result.stdout.strip()}
    except subprocess.TimeoutExpired:
        _notify_event("error", f"Attack · {attack_type} timed out")
        return {"status": "timeout"}
    except Exception as e:
        _notify_event("error", f"Attack · {attack_type} failed: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/control/status")
async def control_status():
    return {
        "capture_running": await _capture_is_running(),
        "pipeline_running": _pipeline_is_running(),
    }

def _pipeline_is_running() -> bool:
    proc = CONTROL_PROCESSES.get("pipeline")
    return proc is not None and proc.poll() is None

# ── API Endpoints ────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/status")
async def status():
    df = get_flows_df()
    evaluation = get_evaluation()
    return {
        "pipeline_phase": cache["pipeline_phase"],
        "models_available": cache["models_available"],
        "flows_count": len(df),
        "evaluation_loaded": bool(evaluation),
        "last_loaded": datetime.utcfromtimestamp(cache["last_loaded"]).isoformat() + "Z" if cache["last_loaded"] else None,
        "phase_history": cache.get("phase_history", []),
    }


@app.get("/api/kpis")
async def kpis():
    df = get_flows_df()
    evaluation = get_evaluation()
    data = compute_kpis(df, evaluation)
    return data


@app.get("/api/flows")
async def flows(
    proto: str = "",
    label: str = "",
    search: str = "",
    sort_col: str = "total_packets",
    sort_dir: str = "desc",
    limit: int = Query(default=200, le=500),
):
    df = get_flows_df()
    if df.empty:
        return {"flows": [], "total": 0, "filtered": 0}

    mask = pd.Series([True] * len(df))
    if proto:
        mask &= df["proto"] == proto
    if label:
        mask &= df["label"] == label
    if search:
        q = search.lower()
        mask &= (
            df["src_ip"].str.lower().str.contains(q, na=False)
            | df["dst_ip"].str.lower().str.contains(q, na=False)
            | df["src_port"].astype(str).str.contains(q, na=False)
            | df["dst_port"].astype(str).str.contains(q, na=False)
            | df["proto"].str.lower().str.contains(q, na=False)
        )

    filtered = df[mask].copy()
    total = len(df)
    filtered_count = len(filtered)

    sort_asc = sort_dir == "asc"
    if sort_col in filtered.columns:
        filtered = filtered.sort_values(by=sort_col, ascending=sort_asc)

    rows = filtered.head(limit).to_dict(orient="records")
    for r in rows:
        for k in list(r.keys()):
            if isinstance(r[k], pd.Timestamp):
                r[k] = r[k].isoformat()

    return {"flows": rows, "total": total, "filtered": filtered_count}


@app.get("/api/flows/timeline")
async def timeline():
    df = get_flows_df()
    return compute_timeline(df)


@app.get("/api/events")
async def events(limit: int = Query(default=100, le=500)):
    df = get_flows_df()
    event_list = list(cache.get("phase_history", []))

    if not df.empty and "label" in df.columns:
        attack_count = int((df["label"] != "NORMAL").sum())
        if attack_count > 0:
            now = datetime.utcnow().isoformat() + "Z"
            event_list.append({
                "t": now,
                "level": "attack",
                "msg": f"ML inference · {attack_count} anomalous flows detected",
            })

    event_list = event_list[-limit:]
    return {"events": event_list}


@app.get("/api/models")
async def models():
    evaluation = get_evaluation()
    return {
        "models": evaluation,
        "available": cache["models_available"],
    }


_initial_events_sent = False


@app.get("/api/events/stream")
async def event_stream():
    async def generate():
        global _initial_events_sent
        if not _initial_events_sent:
            phase = cache["pipeline_phase"]
            yield f"event: init\ndata: {json.dumps({'phase': phase})}\n\n"
            _initial_events_sent = True

        last_phase = cache["pipeline_phase"]
        last_eval_count = len(get_evaluation())

        while True:
            await asyncio.sleep(3)
            current_phase = cache["pipeline_phase"]
            current_eval_count = len(get_evaluation())
            df = get_flows_df()
            now = datetime.utcnow().isoformat() + "Z"

            if current_phase != last_phase:
                yield f"event: phase\ndata: {json.dumps({'phase': current_phase, 'timestamp': now})}\n\n"
                last_phase = current_phase

            if current_eval_count > last_eval_count:
                yield f"event: evaluation\ndata: {json.dumps({'timestamp': now})}\n\n"
                last_eval_count = current_eval_count

            yield f"event: heartbeat\ndata: {json.dumps({'timestamp': now, 'flows': len(df)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def serve_index():
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"error": "index.html not found — build the frontend first"}, status_code=404)


@app.get("/dist/{file_path:path}")
async def serve_dist(file_path: str):
    dist_dir = DASHBOARD_DIR / "dist"
    target = (dist_dir / file_path).resolve()
    if target.exists() and target.is_file() and str(target).startswith(str(dist_dir)):
        return FileResponse(str(target))
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.exception_handler(404)
async def not_found_handler(request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    index_path = DASHBOARD_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"error": "Not found"}, status_code=404)
