#!/usr/bin/env python3
"""LLM4Perf: the artefact contains the LLM sampler but not the performance-model training and metric computation,
so the paper's accuracy numbers cannot be produced from it. Measured here (descriptively): per model x system,
repetitions completed, configurations sampled, and the share that exist in the shipped measured dataset."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare

res, reported = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for cell in sorted((res / "main").glob("*")):
    lists = list(cell.rglob("*_cmd_list.json"))
    n_cfg = sum(len(json.loads(f.read_text())) for f in lists)
    rows.append({"key": cell.name, "metric": "repetitions_completed", "measured": len(lists), "n": len(lists), "note": ""})
    rows.append({"key": cell.name, "metric": "configurations_sampled", "measured": n_cfg, "n": len(lists), "note": ""})
compare(res, reported, rows)
