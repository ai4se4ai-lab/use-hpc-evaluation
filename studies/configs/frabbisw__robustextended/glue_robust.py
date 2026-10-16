#!/usr/bin/env python3
"""Glue added by the reproducer for frabbisw/robustextended:
  prepare <work> <model> <lang>  builds a per-cell working copy (run_code + nominal + this language's format prompts),
                                 maps the hard-coded /home/f_rabbi/models paths to Hugging Face ids, and restricts
                                 calculate_pass_status.py to the reproduced scopes (nominal, partial, format)
  generate <work> <model> <lang> runs the authors' generator for every prompt file, skipping finished outputs
"""
import os, re, shutil, subprocess, sys
from pathlib import Path

HF = {"codegen2bmulti": "Salesforce/codegen-2B-multi", "qwencoder": "Qwen/Qwen2.5-Coder-7B-Instruct"}
cmd, work, model, lang = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
repo = Path(os.environ["REPO_DIR"])
if cmd == "prepare":
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(repo / "run_code", work / "run_code")
    shutil.copytree(repo / "datasets" / "nominal", work / "datasets" / "nominal")
    shutil.copytree(repo / "datasets" / "perturbed" / f"humaneval{lang}" / "full" / "format",
                    work / "datasets" / "perturbed" / f"humaneval{lang}" / "full" / "format")
    g = work / "run_code" / "generate_single_code_single_gpu.py"
    t = g.read_text()
    t = re.sub(r"^models_dict = \{.*\}$", "models_dict = " + repr(HF), t, flags=re.M)
    g.write_text(t); print("patched models_dict ->", HF)
    p = work / "run_code" / "calculate_pass_status.py"
    t = p.read_text().replace('methods = ["nlaugmenter", "natgen", "format", "func_name"]', 'methods = ["format"]')
    p.write_text(t); print("patched calculate_pass_status.py: methods = ['format']")
elif cmd == "generate":
    rc = work / "run_code"
    gen = f"../datasets/{model}/generated_pass5_1/{lang}"
    jobs = [(f"../datasets/nominal/humaneval{lang}_nominal_f_s0.jsonl", f"{gen}/nominal/"),
            (f"../datasets/nominal/humaneval{lang}_partial_f_s0.jsonl", f"{gen}/partial/")]
    fmt = work / "datasets" / "perturbed" / f"humaneval{lang}" / "full" / "format"
    limit = int(os.environ.get("MAX_FORMAT_FILES", "1000"))
    for f in sorted(fmt.glob("*.jsonl"))[:limit]:           # same output naming as create_batch_scripts_all_in_one_file.py
        name = f.name[f.name.find("_") + 1:f.name.rfind("_")]
        jobs.append((f"../datasets/perturbed/humaneval{lang}/full/format/{f.name}", f"{gen}/format/{name}/"))
    for src, out in jobs:
        ext = Path(src).stem.split("_")[-1]
        target = (rc / out / f"f_{ext}.jsonl").resolve()
        if target.exists() and target.stat().st_size > 0:
            print("skip", target.name, out); continue
        (rc / out).mkdir(parents=True, exist_ok=True)
        print("generate", src, flush=True)
        subprocess.run([sys.executable, "generate_single_code_single_gpu.py", src, out, model], cwd=rc, check=True)
