#!/usr/bin/env python3
"""Executability probe: one row per documented entry point (rc and first error line from the step log)."""
import csv, os, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare
res, reported = Path(sys.argv[1]), Path(sys.argv[2])
logs = Path(os.environ["LOG_ROOT"])
led = list(csv.DictReader((logs / "steps.tsv").open(), delimiter="\t")) if (logs / "steps.tsv").exists() else []
last = {}
for r in led:
    if r["stage"] == "probe":
        last[r["step"]] = r
rows = []
for step, r in last.items():
    log = logs / "steps" / "probe" / r["cell"] / f"{step}.log"
    err = ""
    if log.exists():
        lines = [l for l in log.read_text(errors="replace").splitlines() if re.search(r"Error|error:|Traceback|No such file|not found", l)]
        err = lines[-1][:200] if lines else ""
    rows.append({"key": step, "metric": "exit_code", "measured": r["rc"], "n": 1, "note": err})
compare(res, reported, rows)
