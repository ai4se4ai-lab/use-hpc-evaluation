#!/usr/bin/env python3
"""Helper for the manual round 6: print the facts a screener needs for M0–M6 for shortlisted repositories.

    use-hpc-eval triage <rank_from> <rank_to>

For each repository (rank order of data/shortlist.csv): paper title, venue; open-weight model names and sizes
mentioned anywhere (e.g. 7b/13b/34b/70b); Docker/Apptainer use; dataset hosts (huggingface, zenodo, drive);
README lines with run commands; result files shipped in the repository (csv/json/xlsx under result*/output*).
Read-only; the decision is written by the screener into data/manual_screening.csv.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

from use_hpc_eval import config as C

SIZE = re.compile(r"\b(\d{1,3}(?:\.\d)?)\s?[bB]\b")
MODEL = re.compile(r"(codellama|code-llama|llama-?[23](?:\.\d)?|llama3\.\d|deepseek-coder(?:-v2)?|deepseek-r1|qwen[\d.]*(?:-coder)?|"
                   r"starcoder2?|mistral|mixtral|gemma\d?|phi-?\d|codet5p?|codegen2?|wizardcoder|magicoder|granite|"
                   r"unixcoder|codebert|graphcodebert|gpt-?neo|incoder|santacoder|deepseek-v\d|glm-?\d)[\w.-]*", re.I)
HOSTS = re.compile(r"(huggingface\.co/datasets/[\w./-]+|zenodo\.org/[\w./-]+|drive\.google\.com/[\w./?=-]+|figshare\.com/[\w./-]+)")


def main() -> int:
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    rows = list(csv.DictReader((C.DATA / "shortlist.csv").open()))
    for r in rows[lo - 1: hi]:
        d = C.WORK / "clones" / r["repo"].replace("/", "__")
        print(f"\n######## #{r['rank']} {r['repo']}  [{r['venue']} {r['year']}]  ollama={r['ollama_hits']} prop={r['proprietary_hits']}")
        print(f"   paper: {r['title'][:150]}")
        if not d.exists():
            print("   (clone missing)")
            continue
        files = [p for p in d.rglob("*") if p.is_file() and ".git" not in p.parts]
        texts = {}
        for p in files:
            if p.suffix.lower() in {".py", ".md", ".sh", ".yaml", ".yml", ".json", ".txt", ".toml", ".cfg"} and p.stat().st_size < 300_000:
                texts[p] = p.read_text(errors="replace")
        allt = "\n".join(texts.values())
        models = Counter(m.group(0).lower() for m in MODEL.finditer(allt))
        sizes = Counter(m.group(1) + "B" for m in SIZE.finditer(allt))
        print(f"   models: {dict(models.most_common(10))}")
        print(f"   sizes : {dict(sizes.most_common(8))}")
        dock = sum(1 for p in files if p.name.lower().startswith(("dockerfile", "docker-compose"))) + len(re.findall(r"docker (run|build|pull)", allt))
        print(f"   docker: {dock}   data hosts: {sorted(set(HOSTS.findall(allt)))[:4]}")
        res = [str(p.relative_to(d)) for p in files if p.suffix.lower() in {".csv", ".json", ".xlsx", ".jsonl"}
               and re.search(r"result|output|eval", str(p.relative_to(d)), re.I)]
        print(f"   result files: {len(res)} e.g. {res[:4]}")
        readme = next((p for p in files if p.parent == d and p.name.lower().startswith("readme")), None)
        if readme:
            for line in readme.read_text(errors="replace").splitlines():
                if re.search(r"^\s*(\$ )?(python3?|bash|sh|torchrun|accelerate|ollama|vllm)\s", line):
                    print("   run> " + line.strip()[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
