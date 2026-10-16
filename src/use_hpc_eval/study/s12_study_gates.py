#!/usr/bin/env python3
"""Step 12 — aggregate what the RQ5 study runs actually did (gates, causes, cancellations, cost) for docs/emse/emse-use-hpc.tex.

    use-hpc-eval gates [--refresh]

--refresh rebuilds data/results/study_jobs.csv from the run logs on scratch (jobs.tsv, steps.tsv, slurm/*.err) and
data/study_sacct.psv (one sacct call over all study jobs, made beforehand). Without it, the tables are regenerated
from the CSV alone, so the paper can be rebuilt without access to scratch.
Outputs: data/results/study_jobs.csv, study_runs.csv, data/tex/tab_study_runs.tex, tab_study_summary.tex.
H100-equivalent hours count a MIG slice by its compute share (1g = 1/7, 3g = 3/7 of an H100).
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from use_hpc_eval import config as C

REPOS = C.WORK / "repos"
OUT = C.DATA / "results"
TEX = C.DATA / "tex"
PLAN = {r["repo"].replace("/", "__"): r for r in csv.DictReader((C.DATA / "reproduction_plan.csv").open())}
SHORT = {"semguard": "SemGuard", "provenanceguard": "ProvenanceGuard", "retrigen": "RetriGen", "execre": "ExeCRE",
         "effiskel": "EffiSkel", "llm-for-binary-spd": "BinarySPD", "ircoco": "IRCoCo", "robustextended": "RobustExt",
         "llm4perf": "LLM4Perf", "logreasoner": "LogReasoner"}


def gpu_share(tres: str) -> float:
    m = re.search(r"gres/gpu:[^=,]*?(\d)g\.\d+gb=(\d+)", tres)
    if m:
        return int(m.group(1)) / 7 * int(m.group(2))
    m = re.search(r"gres/gpu=(\d+)", tres)
    return float(m.group(1)) if m else 0.0


def cause(logdir: Path, job: str, stage: str) -> str:
    """First failure cause of a job: pip resolution (from the job's .err) or the first failed step (steps.tsv)."""
    for err in (logdir / "slurm").glob(f"*_{job}.err"):
        t = err.read_text(errors="replace")
        if "pip install failed" in t:
            pkg = re.search(r"No matching distribution found for (\S+)", t) or re.search(r"Failed to build '([^']+)'", t)
            hidden = " (wheelhouse hidden: PIP_FIND_LINKS)" if "PIP_FIND_LINKS" in t else ""
            return f"wheel: {pkg.group(1) if pkg else '?'}{hidden}"
    led = logdir / "steps.tsv"
    if led.exists():
        for r in csv.DictReader(led.open(), delimiter="\t"):
            if r["job"] == job and r["rc"] not in ("0", ""):
                return f"step {r['step']} rc={r['rc']}"
    return ""


def refresh() -> None:
    acct = {}
    for line in (C.DATA / "study_sacct.psv").read_text().splitlines():
        f = line.split("|")
        acct[f[0]] = {"state": f[2], "submit": f[3], "start": f[4], "end": f[5], "elapsed_s": int(f[6] or 0), "tres": f[7],
                      "exit": f[8], "node": f[9]}
    rows = []
    for rid in PLAN:
        logs = REPOS / rid / "hpc" / "logs"
        for run in sorted(logs.iterdir()) if logs.exists() else []:
            jt = run / "jobs.tsv"
            if not jt.exists():
                continue
            for line in jt.read_text().splitlines():
                job, stage, _, dep, _ = (line.split("\t") + [""] * 5)[:5]
                a = acct.get(job, {})
                st = a.get("state", "UNKNOWN")
                rows.append({"id": PLAN[rid]["id"], "repo": PLAN[rid]["repo"], "mode": PLAN[rid]["mode"], "run": run.name,
                             "job": job, "stage": stage, "dependency": dep, "state": st.split(" by")[0],
                             "cancelled_by": "operator" if " by " in st else ("dependency" if st == "CANCELLED" else ""),
                             "submit": a.get("submit", ""), "start": a.get("start", ""), "end": a.get("end", ""),
                             "elapsed_s": a.get("elapsed_s", 0),
                             "h100_eq_hours": round(a.get("elapsed_s", 0) * gpu_share(a.get("tres", "")) / 3600, 4),
                             "cause": cause(run, job, stage) if st.startswith("FAILED") else ""})
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "study_jobs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def ts(s: str) -> datetime | None:
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None


def config_rows() -> list[dict]:
    """Reproducer effort per artefact: graph size and lines of the versioned configuration (configs/<repo>/)."""
    rows = []
    for rid, p in sorted(PLAN.items(), key=lambda kv: int(kv[1]["id"][1:])):
        cfg = C.CONFIGS / rid
        g = json.loads((cfg / "experiments.json").read_text())
        files = list(cfg.glob("*.py")) + list(cfg.glob("*.json")) + list(cfg.glob("hooks/*.sh"))
        loc = sum(sum(1 for _ in f.open()) for f in files)
        glue = sum(sum(1 for _ in f.open()) for f in cfg.glob("glue_*.py"))
        rows.append({"id": p["id"], "name": SHORT[p["repo"].split("/")[1]], "mode": p["mode"], "stages": len(g["stages"]),
                     "steps": sum(len(st.get("steps", [])) for st in g["stages"]), "config_loc": loc, "glue_loc": glue,
                     "hooks": len(list(cfg.glob("hooks/*.sh")))})
    return rows


def esc(s: str) -> str:
    return s.replace("_", r"\_").replace("&", r"\&").replace("%", r"\%")


def main() -> int:
    if "--refresh" in sys.argv or not (OUT / "study_jobs.csv").exists():
        refresh()
    jobs = list(csv.DictReader((OUT / "study_jobs.csv").open()))
    runs = defaultdict(list)
    for j in jobs:
        runs[(j["id"], j["repo"], j["mode"], j["run"])].append(j)
    out, seen = [], Counter()
    for (rid, repo, mode, run), js in sorted(runs.items(), key=lambda k: (int(k[0][0][1:]), k[0][3])):
        gate = next(j for j in js if j["stage"] == "setup")
        dependents = [j for j in js if j["stage"] not in ("setup", "collect")]
        coll = next((j for j in js if j["stage"] == "collect"), None)
        if gate["cancelled_by"] == "operator":
            outcome = "withdrawn before start"
        elif gate["state"] == "FAILED":
            outcome = "gate failed"
        elif gate["state"] == "COMPLETED":
            outcome = "gate passed"
        else:
            outcome = gate["state"].lower()
        seen[rid] += 1
        out.append({"id": rid, "label": f"{rid}-{'abc'[seen[rid] - 1]}", "name": SHORT[repo.split("/")[1]], "mode": mode, "run": run, "jobs": len(js),
                    "gate": outcome, "gate_s": int(gate["elapsed_s"]), "cause": gate["cause"],
                    "dependents": len(dependents),
                    "cancelled_by_dependency": sum(j["cancelled_by"] == "dependency" for j in dependents),
                    "cancelled_by_operator": sum(j["cancelled_by"] == "operator" for j in js),
                    "collector": (coll["state"].lower() + (f" ({coll['cause']})" if coll["cause"] else "")) if coll else "",
                    "h100_eq_hours": round(sum(float(j["h100_eq_hours"]) for j in js), 3)})
    with (OUT / "study_runs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    # per-run table: only runs in which at least one job started
    started = [r for r in out if r["gate"] != "withdrawn before start"]
    def num(x: int) -> str:
        return f"{x:,}".replace(",", "{,}")

    body = "\n".join(f"{r['label']} & {r['name']} & {r['gate'].replace('gate ', '')} & {num(r['gate_s'])}\\,s & "
                     f"{esc(r['cause']) or '--'} & {r['cancelled_by_dependency']}/{r['dependents']} & "
                     f"{esc(r['collector']) or '--'} & {r['h100_eq_hours']:.3f} \\\\".replace("& 0.000 ", "& $<$0.001 ")
                     for r in started)
    TEX.mkdir(exist_ok=True)
    (TEX / "tab_study_runs.tex").write_text(
        "\\begin{tabularx}{\\textwidth}{@{}l l l r >{\\raggedright\\arraybackslash}X c >{\\raggedright\\arraybackslash}p{3.4cm} r@{}}\n\\toprule\n"
        "Run & Artefact & Gate & Time & First failure & Dep.\\ canc. & Collector ($\\mathit{any}$) & H100-h \\\\\n"
        "\\midrule\n" + body + "\n\\bottomrule\n\\end{tabularx}\n")
    # summary over the whole study
    st = Counter(j["state"] for j in jobs)
    started_jobs = [j for j in jobs if int(j["elapsed_s"]) > 0]
    gates = [r for r in out if r["gate"] in ("gate failed", "gate passed")]
    waits = [(ts(j["start"]) - ts(j["submit"])).total_seconds() for j in jobs
             if j["stage"] == "setup" and ts(j["start"]) and ts(j["submit"])]
    # fix turnaround: end of a failed gate -> submission of the next run of the same artefact
    turn = []
    by_art = defaultdict(list)
    for (rid, _, _, run), js in runs.items():
        g = next(j for j in js if j["stage"] == "setup")
        by_art[rid].append((min(ts(j["submit"]) for j in js if ts(j["submit"])), g))
    for rid, lst in by_art.items():
        lst.sort(key=lambda x: x[0])
        for (sub, g), (nsub, _) in zip(lst, lst[1:]):
            if g["state"] == "FAILED" and ts(g["end"]):
                turn.append((nsub - ts(g["end"])).total_seconds())
    summ = [("Study runs submitted / with a started job", f"{len(out)} / {len(started)}"),
            ("Jobs submitted / started", f"{len(jobs)} / {len(started_jobs)}"),
            ("Setup gates executed: passed / failed", f"{sum(r['gate'] == 'gate passed' for r in gates)} / {sum(r['gate'] == 'gate failed' for r in gates)}"),
            ("Artefacts whose gate passed", f"{len({r['id'] for r in gates if r['gate'] == 'gate passed'})} of {len({r['id'] for r in gates})}"),
            ("Dependents cancelled by a failed gate", f"{sum(r['cancelled_by_dependency'] for r in out)} (0 GPU-seconds)"),
            ("Jobs withdrawn by the operator before start", f"{sum(j['cancelled_by'] == 'operator' for j in jobs)}"),
            ("H100-equivalent hours, whole study", f"{sum(float(j['h100_eq_hours']) for j in jobs):.2f}"),
            ("Median / max gate time", f"{statistics.median(r['gate_s'] for r in gates):,.0f}\\,s / {max(r['gate_s'] for r in gates):,}\\,s".replace(",", "{,}").replace("\\{,}", "\\,"))]
    summ += [("Median queue wait of a gate", f"{statistics.median(waits) / 60:.1f}\\,min"),
             ("Failed gate $\\to$ fixed resubmission, median (range)",
              f"{statistics.median(turn) / 60:.1f}\\,min ({min(turn) / 60:.0f}--{max(turn) / 60:.0f}\\,min, n={len(turn)})")]
    (TEX / "tab_study_summary.tex").write_text(
        "\\begin{tabular}{@{}l r@{}}\n\\toprule\n" + "\n".join(f"{a} & {b} \\\\" for a, b in summ) + "\n\\bottomrule\n\\end{tabular}\n")
    cr = config_rows()
    with (OUT / "study_config.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cr[0]))
        w.writeheader()
        w.writerows(cr)
    (TEX / "tab_study_config.tex").write_text(
        "\\begin{tabular}{@{}l l l r r r r r@{}}\n\\toprule\nId & Artefact & Mode & Stages & Steps & Config LoC & Glue LoC & Hooks \\\\\n\\midrule\n"
        + "\n".join(f"{r['id']} & {r['name']} & {r['mode']} & {r['stages']} & {r['steps']} & {r['config_loc']} & {r['glue_loc'] or '--'} & {r['hooks'] or '--'} \\\\" for r in cr)
        + f"\n\\midrule\nTotal & & & {sum(r['stages'] for r in cr)} & {sum(r['steps'] for r in cr)} & "
          f"{sum(r['config_loc'] for r in cr):,} & {sum(r['glue_loc'] for r in cr)} & {sum(r['hooks'] for r in cr)} \\\\".replace(",", "{,}")
        + "\n\\bottomrule\n\\end{tabular}\n")
    print(dict(st), {k: v for k, v in summ})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
