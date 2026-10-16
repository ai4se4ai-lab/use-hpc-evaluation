#!/usr/bin/env python3
"""Step 11 — aggregate the reproduction study (RQ5) into CSVs and LaTeX for docs/emse/emse-use-hpc.tex.

    use-hpc-eval results          -> data/results/*.csv, data/tex/tab_outcomes.tex,
                                                                tab_comparison.tex, tab_cost.tex, fig_reproduction.tex
Per repository it takes the newest non-smoke run that has compare/comparison.csv (else the newest smoke run, marked).
Outcome classes (first matching rule, in this order):
  NR  not runnable as released: a probe in which a documented entry point exits non-zero
  NC  not comparable: every reported row is not_comparable (artefact lacks evaluation code, data or weights)
  R   reproduced: every comparable rerun row is within tolerance
  P   partially reproduced: some comparable rerun rows are within tolerance
  D   deviates: comparable rows exist, none is within tolerance
  ... pending: no comparison yet
Cost per repository comes from one sacct call over all study jobs: jobs, GPU-hours, median queue wait.
Reproducer effort = lines of the repository's configuration (experiments.json, glue_*.py, compare.py, hooks).
"""
from __future__ import annotations

import csv
import json
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from use_hpc_eval import config as C

REPOS = C.WORK / "repos"
OUT = C.DATA / "results"
TEX = C.DATA / "tex"


def esc(s) -> str:
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"), ("$", r"\$")):
        s = s.replace(a, b)
    return s


def latest_run(rid: str) -> tuple[Path | None, bool]:
    logs = REPOS / rid / "hpc" / "logs"
    if not logs.exists():
        return None, False
    runs = sorted(logs.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for smoke in (False, True):
        for r in runs:
            if ("smoke" in r.name) == smoke and (r / "results" / "compare" / "comparison.csv").exists():
                return r, smoke
    return None, False


def ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    TEX.mkdir(exist_ok=True)
    plan = {r["repo"].replace("/", "__"): r for r in csv.DictReader((C.DATA / "reproduction_plan.csv").open())}
    # cost: every job of every study run, one sacct call
    jobs = defaultdict(list)
    for rid in plan:
        for jt in (REPOS / rid / "hpc" / "logs").glob("*/jobs.tsv") if (REPOS / rid / "hpc" / "logs").exists() else []:
            for line in jt.read_text().splitlines():
                if line.strip():
                    jobs[rid].append(line.split("\t")[0])
    allids = [j for v in jobs.values() for j in v]
    acct = {}
    if allids:
        out = subprocess.run(["sacct", "-n", "-P", "-X", "-j", ",".join(allids), "--format=JobID,State,Submit,Start,End,ElapsedRaw,AllocTRES"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            f = line.split("|")
            if len(f) >= 7:
                g = sum(float(x.split("=")[1]) for x in f[6].split(",") if x.startswith("gres/gpu=")) if f[6] else 0
                base = f[0].split("_")[0]
                acct.setdefault(base, []).append({"state": f[1], "wait": (ts(f[3]) - ts(f[2])).total_seconds() if ts(f[3]) and ts(f[2]) else None,
                                                  "gpuh": int(f[5] or 0) * g / 3600})
    rows_out, comp_rows, cost_rows = [], [], []
    for rid, p in plan.items():
        run, smoke = latest_run(rid)
        comp = list(csv.DictReader((run / "results" / "compare" / "comparison.csv").open())) if run else []
        for r in comp:
            comp_rows.append({"id": p["id"], "repo": p["repo"], "run": run.name if run else "", **r})
        st = [r["status"] for r in comp]
        rerun = [r for r in comp if "rescored" not in r["key"]]
        rr = [r["status"] for r in rerun]
        if p["mode"] == "probe" and any(r["status"] == "deviates" for r in comp):
            outcome = "NR"
        elif comp and all(s == "not_comparable" for s in rr or st):
            outcome = "NC"
        elif rr and all(s == "reproduced" for s in rr if s != "not_comparable") and any(s == "reproduced" for s in rr):
            outcome = "R"
        elif any(s == "reproduced" for s in rr):
            outcome = "P"
        elif any(s == "deviates" for s in rr):
            outcome = "D"
        else:
            outcome = "pending"
        resc = [r for r in comp if "rescored" in r["key"] and r["status"] in ("reproduced", "deviates")]
        effort = 0
        cfg = C.CONFIGS / rid
        for f in list(cfg.glob("*.py")) + list(cfg.glob("*.json")) + list(cfg.glob("hooks/*.sh")):
            effort += sum(1 for _ in f.open())
        a = [x for j in jobs[rid] for x in acct.get(j, [])]
        waits = [x["wait"] for x in a if x["wait"] is not None]
        rows_out.append({"id": p["id"], "repo": p["repo"], "venue": p["venue"], "mode": p["mode"], "run": run.name if run else "",
                         "smoke_only": smoke, "outcome": outcome,
                         "rows_reproduced": sum(s == "reproduced" for s in rr), "rows_compared": sum(s in ("reproduced", "deviates") for s in rr),
                         "rows_not_comparable": sum(s == "not_comparable" for s in st),
                         "rescored_ok": f"{sum(r['status'] == 'reproduced' for r in resc)}/{len(resc)}" if resc else "",
                         "config_lines": effort})
        cost_rows.append({"id": p["id"], "jobs": len(a), "completed": sum(x["state"] == "COMPLETED" for x in a),
                          "gpu_hours": round(sum(x["gpuh"] for x in a), 1),
                          "median_wait_min": round(statistics.median(waits) / 60, 1) if waits else ""})
    for name, rows in (("outcomes.csv", rows_out), ("comparison_all.csv", comp_rows), ("cost.csv", cost_rows)):
        if rows:
            with (OUT / name).open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    cost = {c["id"]: c for c in cost_rows}
    body = "\n".join(f"{r['id']} & \\code{{{esc(r['repo'])}}} & {r['mode']} & {r['outcome']} & {r['rows_reproduced']}/{r['rows_compared']} & "
                     f"{r['rescored_ok'] or '--'} & {r['config_lines']} & {cost[r['id']]['jobs']} & {cost[r['id']]['gpu_hours']} \\\\" for r in rows_out)
    (TEX / "tab_outcomes.tex").write_text(
        "\\begin{tabular}{@{}l l l c c c r r r@{}}\n\\toprule\nId & Repository & Mode & Outcome & Rerun rows & Re-scored & Config LoC & Jobs & GPU-h \\\\\n"
        "\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")
    # comparison table: every comparable row (rerun and re-scored), reported vs measured
    lines = []
    for r in comp_rows:
        if r["status"] in ("reproduced", "deviates", "missing"):
            kind = "re-scored" if "rescored" in r["key"] else "rerun"
            key = r["key"].replace("|rescored-shipped", "").replace("|rerun", "")
            mark = {"reproduced": "\\cmark", "deviates": "\\xmark", "missing": "--"}[r["status"]]
            lines.append(f"{r['id']} & {esc(key)} & {esc(r['metric'])} & {kind} & {r['reported']} & {r['measured'] or '--'} & "
                         f"{r.get('abs_diff') or '--'} & {r.get('tolerance') or '--'} & {mark} \\\\")
    (TEX / "tab_comparison.tex").write_text(
        "\\begin{longtable}{@{}l l l l r r r r c@{}}\n\\toprule\nId & Setting & Metric & Kind & Reported & Measured & $\\Delta$ & Tol. & \\\\\n"
        "\\midrule\n\\endhead\n" + "\n".join(lines) + "\n\\bottomrule\n\\end{longtable}\n")
    print(json.dumps({r["id"]: r["outcome"] for r in rows_out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
