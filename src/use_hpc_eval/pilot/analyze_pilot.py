#!/usr/bin/env python3
"""RQ1-2 evidence from the 44,352-run pilot deployment on Nibi (real logs only).

    use-hpc-eval pilot --logs <pilot project>/hpc/logs     # reads the logs and data/pilot/sacct_raw.psv

Inputs (all produced by the pipeline itself, no manual numbers):
  <logs>/<RUN_ID>/{jobs.tsv, steps.tsv, jobs_finished.tsv, gpu/*.csv}   ledger, endings, GPU samples
  data/pilot/sacct_raw.psv   one `sacct -X -P` dump of every job of every run
                             (JobID|JobName|State|Submit|Start|End|ElapsedRaw|AllocTRES|NodeList)
Outputs (data/pilot/): runs.csv, stages_smoke.csv, gpu_util.csv, summary.json
The raw logs live in the pilot project, not in this repository; the derived CSVs are committed.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from use_hpc_eval import config as C

HERE = C.PILOT


def ts(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def tsv(p: Path) -> list[list[str]]:
    return [l.split("\t") for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def gpu_util(f: Path) -> list[float]:
    out = []
    for line in f.read_text(errors="replace").splitlines()[1:]:
        parts = [x.strip() for x in line.split(",")]
        try:
            out.append(float(parts[2].split()[0]))
        except (IndexError, ValueError):
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="use-hpc-eval pilot", description="Aggregate the pilot's ledgers and sacct dump.")
    ap.add_argument("--logs", type=Path, required=True, help="the pilot project's hpc/logs directory")
    ap.add_argument("--snapshot", help="time of the sacct dump, 'YYYY-mm-dd HH:MM:SS' (default: the dump's mtime, "
                                       "which a git clone does not preserve; the published one is in summary.json)")
    a = ap.parse_args()
    LOGS = a.logs
    if not LOGS.is_dir():
        ap.error(f"{LOGS} is not a directory")
    snap = (datetime.strptime(a.snapshot, "%Y-%m-%d %H:%M:%S") if a.snapshot else
            datetime.fromtimestamp((HERE / "sacct_raw.psv").stat().st_mtime).replace(microsecond=0))  # time of the sacct dump
    sacct = {}
    for line in (HERE / "sacct_raw.psv").read_text().splitlines():
        f = line.split("|")
        if len(f) >= 9:
            gpus = sum(int(x.split("=")[1]) for x in f[7].split(",") if x.startswith("gres/gpu=")) if f[7] else 0
            start, end = ts(f[4]), ts(f[5])
            if start and not end:   # still running at the snapshot
                end = snap
            sacct[f[0]] = {"name": f[1], "state": f[2], "submit": ts(f[3]), "start": start, "end": end,
                           "elapsed": int((end - start).total_seconds()) if start else 0, "gpus": gpus, "node": f[8]}
    runs, stage_rows, util_rows = [], [], []
    for d in sorted(p for p in LOGS.iterdir() if (p / "jobs.tsv").exists()):
        jobs = [r[0] for r in tsv(d / "jobs.tsv")]
        js = [sacct[j] for j in jobs if j in sacct]
        states = Counter(j["state"].split()[0] if not j["state"].startswith("CANCELLED by") else "CANCELLED_BY_USER" for j in js)
        led = tsv(d / "steps.tsv")[1:]
        step_rc = Counter("ok" if r[8] == "0" else "failed" for r in led if len(r) > 8)
        starts = [j["start"] for j in js if j["start"]]
        ends = [j["end"] for j in js if j["end"]]
        waits = [(j["start"] - j["submit"]).total_seconds() for j in js if j["start"] and j["submit"]]
        gpu_h = sum(j["elapsed"] * j["gpus"] for j in js) / 3600
        nodes = sorted({j["node"] for j in js if j["node"] and j["node"] != "None assigned"})
        kind = "smoke" if "smoke" in d.name else ("sizing" if "sizing" in d.name else "full")
        runs.append({"run": d.name, "kind": kind, "jobs": len(jobs), "started": len(starts), "completed": states.get("COMPLETED", 0),
                     "running": states.get("RUNNING", 0), "pending": states.get("PENDING", 0),
                     "failed": states.get("FAILED", 0), "cancelled_by_dependency": states.get("CANCELLED", 0),
                     "cancelled_by_user": states.get("CANCELLED_BY_USER", 0), "steps_ok": step_rc.get("ok", 0),
                     "steps_failed": step_rc.get("failed", 0), "distinct_nodes": len(nodes),
                     "makespan_s": int((max(ends) - min(starts)).total_seconds()) if starts and ends else "",
                     "sum_job_s": sum(j["elapsed"] for j in js),
                     "concurrency": round(sum(j["elapsed"] for j in js) / max((max(ends) - min(starts)).total_seconds(), 1), 2) if starts and ends else "",
                     "gpu_hours": round(gpu_h, 2),
                     "median_wait_s": int(statistics.median(waits)) if waits else "",
                     "max_wait_s": int(max(waits)) if waits else ""})
        if kind == "smoke":
            per = defaultdict(float)
            for r in led:
                if len(r) > 8:
                    per[r[3].split("_qwen")[0].split("_deepseek")[0]] += float(r[7] or 0)
            for st, s in per.items():
                stage_rows.append({"run": d.name, "stage": st, "step_seconds": int(s)})
        for f in sorted((d / "gpu").glob("*.csv")):
            u = gpu_util(f)
            if len(u) >= 3:
                util_rows.append({"run": d.name, "kind": kind, "job": f.stem, "samples": len(u),
                                  "mean_util": round(statistics.fmean(u), 1), "busy_share": round(sum(x > 10 for x in u) / len(u), 3)})
    for name, rows in (("runs.csv", runs), ("stages_smoke.csv", stage_rows), ("gpu_util.csv", util_rows)):
        with (HERE / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    smoke = [r for r in runs if r["kind"] == "smoke"]
    gated = [r for r in runs if r["kind"] == "full" and r["failed"] and r["cancelled_by_dependency"]]
    summary = {
        "snapshot": str(snap),
        "runs": len(runs), "jobs_total": sum(r["jobs"] for r in runs),
        "smoke": [{k: r[k] for k in ("run", "jobs", "completed", "steps_ok", "steps_failed", "makespan_s", "sum_job_s", "distinct_nodes", "median_wait_s")} for r in smoke],
        "gate_failures": [{k: r[k] for k in ("run", "jobs", "failed", "cancelled_by_dependency", "gpu_hours")} for r in gated],
        "sacct_states": dict(Counter(j["state"].split()[0] for j in sacct.values())),
    }
    (HERE / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
