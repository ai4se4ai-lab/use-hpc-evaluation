#!/usr/bin/env python3
"""ProvenanceGuard: Error Rate (ER: unsafe traces allowed) and Intervention Rate (IR: safe traces blocked) per
method x benchmark, mean over runs; for the authors' shipped Qwen-3.5-9B runs (rescored) and our re-runs.
Definitions validated by re-scoring the shipped CSVs against Tables 2 and 3."""
import csv, glob, os, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare
res, reported = Path(sys.argv[1]), Path(sys.argv[2])
repo = Path(os.environ.get("REPO_DIR", "."))
M = {"provenanceguard": "pvgd", "single_step_provenanceguard": "pvpt", "baseline": "base"}


def rates(files):
    ers, irs = [], []
    for f in files:
        R = list(csv.DictReader(open(f)))
        uns = [r for r in R if str(r["safe?"]).strip() == "0"]
        saf = [r for r in R if str(r["safe?"]).strip() == "1"]
        if uns: ers.append(sum(str(r["predicted label"]).strip() == "1" for r in uns) / len(uns))
        if saf: irs.append(sum(str(r["predicted label"]).strip() == "0" for r in saf) / len(saf))
    return ers, irs


rows = []
for b in ("agent_safetybench", "workbench"):
    for m, short in M.items():
        for kind, files in (("rescored-shipped", sorted(glob.glob(str(repo / f"results/{b}/{m}/local_vllm/Qwen_Qwen3_5_9B_thinking-disabled_nonboundary_run[0-4].csv")))),
                            ("rerun", sorted(glob.glob(str(res / f"runs/{b}/{m}/run[0-9].csv"))))):
            ers, irs = rates(files)
            for metric, v in (("ER", ers), ("IR", irs)):
                if v:
                    rows.append({"key": f"{b}|{short}|{kind}", "metric": metric, "measured": round(st.mean(v), 3), "n": len(v),
                                 "note": f"sd {st.stdev(v):.3f}" if len(v) > 1 else ""})
compare(res, reported, rows)
