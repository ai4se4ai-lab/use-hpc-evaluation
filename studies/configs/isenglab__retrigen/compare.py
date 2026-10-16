#!/usr/bin/env python3
"""RetriGen: accuracy (exact match, as RQ1/evaluator/acc.py) and CodeBLEU (codebleu package; the authors' script
needs tree_sitter 0.20, see deviations) for
  <ds>|rescored-shipped  the authors' shipped predictions (RetriGen/result/*/RetriGen_*_alpha_prediction.csv)
  <ds>|rerun             our full re-run (work/<ds>/results/generated_predictions.jsonl)
    compare.py <RESULTS> <reported.csv> [--rescore-only] <REPO>"""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare

res, reported = Path(sys.argv[1]), Path(sys.argv[2])
repo = Path(sys.argv[-1])
rescore_only = "--rescore-only" in sys.argv


def scores(refs, hyps):
    acc = 100 * sum(r.strip() == h.strip() for r, h in zip(refs, hyps)) / max(len(refs), 1)
    try:
        from codebleu import calc_codebleu
        cb = 100 * calc_codebleu(list(refs), list(hyps), lang="java")["codebleu"]
    except Exception as e:  # noqa: BLE001
        print("codebleu unavailable:", e); cb = None
    return round(acc, 2), (round(cb, 2) if cb is not None else "")


rows = []
for ds, sfx in (("OldDataSet", "old"), ("NewDataSet", "new")):
    f = repo / "RetriGen" / "result" / ds / f"RetriGen_{sfx}_alpha_prediction.csv"
    if f.exists():
        df = pd.read_csv(f)
        a, c = scores(df["target"].astype(str), df["raw_prediction"].astype(str))
        rows += [{"key": f"{sfx}|rescored-shipped", "metric": "accuracy", "measured": a, "n": len(df), "note": "authors' predictions"},
                 {"key": f"{sfx}|rescored-shipped", "metric": "codebleu", "measured": c, "n": len(df), "note": "codebleu package"}]
    p = res / "work" / ds / "results" / "generated_predictions.jsonl"
    if not rescore_only and p.exists():
        L = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        a, c = scores([l["target"] for l in L], [str(l["prediction"]) for l in L])
        rows += [{"key": f"{sfx}|rerun", "metric": "accuracy", "measured": a, "n": len(L), "note": "our re-run"},
                 {"key": f"{sfx}|rerun", "metric": "codebleu", "measured": c, "n": len(L), "note": "codebleu package"}]
compare(res, reported, rows)
