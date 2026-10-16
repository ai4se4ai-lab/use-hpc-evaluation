#!/usr/bin/env python3
"""Glue added by the reproducer for moyi-dong/execre: derive the run config from the authors' config for the same
method, pointing the OpenAI-compatible "online" backend at the job's local vLLM server (ONLINE_BASE_URL) under the
served model name. Smoke mode shrinks n, rounds and the problem count.
    glue_execre.py <method> <model> <out.json> [--smoke]"""
import json, sys
from pathlib import Path
method, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
src = {"qwen32b": f"configs/e1_{method}_online_qwen25coder32b.json", "llama8b": f"configs/e1_{method}_openrouter_llama31ins8b.json"}[model]
cfg = json.loads(Path(src).read_text())
cfg["model"]["model"] = {"qwen32b": "online-qwen2.5-coder-32b-instruct", "llama8b": "online-llama-3.1-8b-instruct"}[model]
if "--smoke" in sys.argv:
    cfg["experiment"]["n"] = 1
    cfg["experiment"]["test_count"] = 3
    cfg["max_rounds"] = 2
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(cfg, indent=2))
print(f"{src} -> {out}: model {cfg['model']['model']}, n={cfg['experiment']['n']}, rounds={cfg.get('max_rounds')}")
