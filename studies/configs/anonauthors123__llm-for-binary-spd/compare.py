#!/usr/bin/env python3
"""Binary SPD (TOSEM 2026), Table 1 (prompting): accuracy, F1, FP rate and failure rate (neither yes nor no) per
model x dataset; positive = 'yes' in the answer (as evaluation/eval.py). Shipped API predictions (GPT-3.5,
DeepSeek-R1) are re-scored to validate the definitions; Qwen2.5-Coder-7B-Instruct zero-shot is re-run locally.
Fine-tuning results (Tables 2-3) are not comparable: training data and adapters are not released."""
import glob, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare
res, reported = Path(sys.argv[1]), Path(sys.argv[2])
repo = Path(os.environ.get("REPO_DIR", "."))


def metrics(rows):
    lab = [r["label"].strip().lower() == "yes" for r in rows]
    p = [str(r["predict"]).strip().lower() for r in rows]
    yes = ["yes" in x for x in p]
    tp = sum(a and b for a, b in zip(lab, yes)); fp = sum((not a) and b for a, b in zip(lab, yes))
    tn = sum((not a) and (not b) for a, b in zip(lab, yes)); fn = sum(a and not b for a, b in zip(lab, yes))
    prec, rec = tp / max(tp + fp, 1), tp / max(tp + fn, 1)
    return {"accuracy": (tp + tn) / len(rows), "f1": 2 * prec * rec / max(prec + rec, 1e-9), "fpr": fp / max(fp + tn, 1),
            "failure_rate": sum(("yes" not in x and "no" not in x) for x in p) / len(rows)}


out = []
for kind, pattern in (("rescored-shipped", str(repo / "LLM-online/saves/*/*/generated_predictions.jsonl")),
                      ("rerun", str(res / "saves/*/*/generated_predictions.jsonl"))):
    for f in sorted(glob.glob(pattern)):
        ds, model = Path(f).parts[-3], Path(f).parts[-2]
        R = [json.loads(l) for l in open(f) if l.strip()]
        for k, v in metrics(R).items():
            out.append({"key": f"{model}|{ds}|{kind}", "metric": k, "measured": round(v, 3), "n": len(R), "note": ""})
compare(res, reported, out)
