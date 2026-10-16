#!/usr/bin/env python3
"""Step 9 — executability probe for repositories whose documented pipeline cannot run unmodified.

    use-hpc-eval probe <repo_id> <probe.json>

probe.json: {"paper": ..., "modules": ..., "requirements": [...], "setup": ["cmd", ...],
             "entry_points": [{"name": ..., "cmd": ...}, ...], "not_comparable": [[key, metric, value, source, why], ...]}
Writes configs/<repo_id>/{experiments.json, requirements.txt, compare.py, reported.csv}. The generated graph has a
setup stage (data and models) and one probe stage that runs every documented entry point, in README order, with
minimal sizes, inside the real environment on a GPU node. A step's return code and log become the evidence.
Steps are not critical, so every entry point is tried even after a failure. compare.py turns the ledger into
probe rows (entry point, rc, first error line).
"""
from __future__ import annotations

import json
import sys

from use_hpc_eval import config as C

COMPARE = r'''#!/usr/bin/env python3
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
'''


def main() -> int:
    rid, spec_path = sys.argv[1], sys.argv[2]
    spec = json.loads(open(spec_path).read())
    d = C.CONFIGS / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "requirements.txt").write_text("\n".join(["# executability probe: the artefact's declared dependencies"] + spec["requirements"]) + "\n")
    steps = [{"name": p["name"], "cmd": p["cmd"]} for p in spec["entry_points"]]
    exp = {
        "_repro": {"paper": spec["paper"], "src_dirs": ".", "hash_dirs": ".", "modules": spec.get("modules", "StdEnv/2023 python/3.11 arrow/24.0.0")},
        "project": "r_probe_" + rid.split("__")[-1][:12],
        "require_gpu": True,
        "vars": {},
        "smoke": {"vars": {}, "time": "00:55:00"},
        "stages": [
            {"name": "setup", "description": "data and models for the probe", "internet": True,
             "resources": {"gpus": "h100_1g.10gb:1", "cpus": 4, "mem": "16G", "time": "02:00:00"},
             "steps": [{"name": "check_gpu", "builtin": "check_gpu", "always": True}] +
                      [{"name": f"setup_{i}", "cmd": c} for i, c in enumerate(spec.get("setup", []))]},
            {"name": "probe", "description": "every documented entry point, README order, minimal sizes",
             "depends": [{"stage": "setup", "type": "afterany"}],
             "resources": {"gpus": spec.get("probe_gpu", "h100_3g.40gb:1"), "cpus": 6, "mem": "48G", "time": spec.get("probe_time", "03:00:00")},
             "steps": steps},
            {"name": "collect", "depends": [{"stage": "probe", "type": "afterany"}],
             "resources": {"gpus": "h100_1g.10gb:1", "cpus": 2, "mem": "8G", "time": "01:00:00"},
             "steps": [{"name": "compare", "cmd": "python {HPC}/compare.py {RESULTS} {HPC}/reported.csv", "always": True},
                       {"name": "collect", "builtin": "collect", "always": True}]},
        ],
        "results": {"tables": [{"name": "comparison", "glob": "compare/comparison.csv"}], "copy": ["compare/*"]},
    }
    (d / "experiments.json").write_text(json.dumps(exp, indent=1))
    (d / "compare.py").write_text(COMPARE)
    import csv as _csv
    with (d / "reported.csv").open("w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["key", "metric", "reported", "tolerance", "source", "comparable"])
        for p in spec["entry_points"]:      # a working artefact exits 0 at every documented step; the run decides
            w.writerow([p["name"], "exit_code", 0, 0, "README step", "yes"])
        for k, m, v, src, why in spec.get("not_comparable", []):
            w.writerow([k, m, v, "", src, why])
    print(f"wrote probe config for {rid}: {len(steps)} entry points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
