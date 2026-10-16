#!/usr/bin/env python3
"""Glue added by the reproducer (the artefact has no code between these steps):
  prepare <work> <dataset>   copy-on-scratch fixes: datasets' paths for Old/New, embed.sh 0-based loop, Ollama URL,
                             CPU counts, CUDA_VISIBLE_DEVICES=1 removed from run-RetriGen.sh
  jsonl <work> <dataset>     hybrid dataset CSVs (source,target) -> datas/{train,test,valid}.jsonl for codet5_main.py
  txt <work> <dataset>       predictions jsonl -> result/<dataset>/RetriGen_{Label,Result}.txt (inputs of acc.py)
Every change is listed in the step log."""
import json, os, re, sys
from pathlib import Path
import pandas as pd

cmd, work, ds = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
sfx = "old" if ds == "OldDataSet" else "new"
cpus = os.environ.get("SLURM_CPUS_PER_TASK", "8")
if cmd == "prepare":
    for sh in work.rglob("*.sh"):
        t0 = t = sh.read_text()
        if sfx == "old":
            t = t.replace("NewDataSet", "OldDataSet").replace("_new", "_old")
        t = re.sub(r"cpu_count=\d+", f"cpu_count={cpus}", t)
        t = t.replace("for i in $(seq 1 `expr ${#source_paths[@]}`); do", "for i in $(seq 0 `expr ${#source_paths[@]} - 1`); do")
        t = t.replace("CUDA_VISIBLE_DEVICES=1 ", "")
        if t != t0:
            sh.write_text(t); print(f"patched {sh.relative_to(work)}")
    emb = work / "codellama" / "codellama_embedding.py"
    t = emb.read_text().replace("http://localhost:11434", os.environ["LLM_URL"])
    emb.write_text(t); print(f"patched {emb.relative_to(work)}: Ollama URL -> {os.environ['LLM_URL']}")
elif cmd == "jsonl":   # hybrid/*.sh already apply RQ2/dataset.py's transformation and write source,target CSVs
    (work / "datas").mkdir(exist_ok=True)
    for split, name in (("train", "train"), ("test", "test"), ("val", "valid")):
        df = pd.read_csv(work / "hybrid" / "result" / ds / split / f"assert_{split}_{sfx}_alpha_0.5.csv")
        with (work / "datas" / f"{name}.jsonl").open("w") as f:
            for _, d in df.iterrows():
                f.write(json.dumps({"source": str(d["source"]), "target": str(d["target"])}) + "\n")
        print(f"{name}: {len(df)} rows")
elif cmd == "txt":
    out = work / "result" / ds
    out.mkdir(parents=True, exist_ok=True)
    lines = [json.loads(l) for l in (work / "results" / "generated_predictions.jsonl").read_text().splitlines() if l.strip()]
    (out / "RetriGen_Label.txt").write_text("\n".join(l["target"].strip() for l in lines) + "\n")
    (out / "RetriGen_Result.txt").write_text("\n".join(str(l.get("prediction", "")).strip() for l in lines) + "\n")
    print(f"{len(lines)} predictions")
