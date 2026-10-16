#!/usr/bin/env python3
"""robustextended: RP5@1 per model x language for nominal, partial and format (worst case over the 5 seeds of each
format perturbation, averaged over the 6 format perturbations, as the paper's summary). The worst-case function is
the authors' get_worst_passatk_dict, loaded from run_code/calculate_metrics.py without its module-level driver."""
import ast, json, os, sys
from os.path import join
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare

res, reported = Path(sys.argv[1]), Path(sys.argv[2])
src = (Path(os.environ.get("REPO_DIR", ".")) / "run_code" / "calculate_metrics.py").read_text()
tree = ast.parse(src)
ns = {"join": join, "json": json}
code = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("load_prompts", "get_worst_passatk_dict", "calculate_passatk")], type_ignores=[])
exec(compile(code, "calculate_metrics.py", "exec"), ns)
rows = []
for cell in sorted((res / "work").glob("*_*")):
    model, lang = cell.name.rsplit("_", 1)
    base = cell / "datasets" / model / "generated_pass5_1" / lang
    for kind in ("nominal", "partial"):
        f = base / kind / "f_s0.jsonl"
        if f.exists():
            P = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
            if P and "passed" in P[0]:
                rows.append({"key": f"{model}|{lang}|{kind}", "metric": "RP5@1", "measured": round(sum(p["passed"] for p in P) / len(P), 3), "n": len(P), "note": ""})
    vals = []
    for d in sorted((base / "format").glob("*")):
        try:
            vals.append(ns["calculate_passatk"](ns["get_worst_passatk_dict"](str(d), 5)))
        except Exception as e:  # noqa: BLE001
            print("format", d.name, e)
    if vals:
        rows.append({"key": f"{model}|{lang}|format", "metric": "RP5@1", "measured": round(sum(vals) / len(vals), 3), "n": len(vals), "note": "mean over format perturbations"})
rows += [dict(r, metric="RP5@1 (Table 9)") for r in list(rows)]   # same measurement, compared with both tables
compare(res, reported, rows)
