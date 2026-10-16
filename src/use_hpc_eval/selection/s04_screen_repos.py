#!/usr/bin/env python3
"""Step 4 — rounds 3–5 on the candidate artefact repositories (no GitHub API needed).

    use-hpc-eval screen [--workers 4]   data/r3_links.jsonl -> data/r4_repos.jsonl

Round 3 (artefact)    : the paper links a GitHub repository (s03 score >= 4) that is reachable (`git ls-remote`).
Round 4 (open weights): the repository uses open-weight models: config.OPEN_WEIGHT occurs in code, configs or README
                        (Ollama recorded separately); repositories that only call proprietary APIs are dropped.
Round 5 (runnable)    : Python is the main language, a dependency file exists, the README gives commands to run,
                        and the last commit is after config.PUSHED_AFTER.
Each repository is shallow-cloned without blobs > 200 KB (code only, no data or weights) into
$REPRO_WORK/clones/; clones that fail a round are deleted immediately (scratch quota and file counts).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from use_hpc_eval import config as C

CLONES = C.WORK / "clones"
TEXT_EXT = {".py", ".md", ".txt", ".sh", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ipynb", ".rst", ".ini", ".env"}
CODE_EXT = {".py": "python", ".ipynb": "python", ".java": "java", ".js": "js", ".ts": "js", ".cpp": "c", ".c": "c",
            ".go": "go", ".rs": "rust", ".kt": "java", ".scala": "java", ".r": "r", ".cs": "csharp", ".sol": "solidity"}
RUN_CMD = re.compile(r"(^|\n)\s*(\$ )?(python3?|bash|sh|torchrun|accelerate launch|ollama (run|pull)|make)\s+\S+", re.I)


def sh(cmd: list[str], timeout: int = 300, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          env={"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:" + __import__("os").environ["PATH"]})


def screen(repo: str) -> dict:
    try:
        return _screen(repo)
    except Exception as e:  # noqa: BLE001  (e.g. file names too long for the filesystem)
        shutil.rmtree(CLONES / repo.replace("/", "__"), ignore_errors=True)
        return {"repo": repo, "round": 3, "kept": False, "reason": f"clone failed ({type(e).__name__})"}


def _screen(repo: str) -> dict:
    rec = {"repo": repo, "round": 3, "kept": False, "reason": ""}
    url = f"https://github.com/{repo}"
    try:
        r = sh(["git", "ls-remote", "--symref", url, "HEAD"], timeout=60)
    except subprocess.TimeoutExpired:
        r = None
    if not r or r.returncode != 0:
        rec["reason"] = "repository not reachable (deleted, private or renamed)"
        return rec
    dest = CLONES / repo.replace("/", "__")
    if not dest.exists():
        try:
            r = sh(["git", "clone", "-q", "--depth", "1", "--filter=blob:limit=200k", "--no-tags", url, str(dest)], timeout=600)
        except subprocess.TimeoutExpired:
            r = None
        if not r or r.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            rec["reason"] = "clone failed"
            return rec
    rec["commit"] = sh(["git", "rev-parse", "HEAD"], cwd=dest).stdout.strip()
    rec["last_commit"] = sh(["git", "log", "-1", "--format=%cI"], cwd=dest).stdout.strip()
    files = [p for p in dest.rglob("*") if p.is_file() and ".git" not in p.parts]
    rec["n_files"] = len(files)
    rec["mb"] = round(sum(p.stat().st_size for p in files) / 2**20, 1)
    langs = Counter(CODE_EXT[p.suffix.lower()] for p in files if p.suffix.lower() in CODE_EXT)
    rec["languages"] = dict(langs.most_common(4))
    rec["main_language"] = langs.most_common(1)[0][0] if langs else ""
    rec["dep_files"] = sorted({p.name for p in files if p.name in C.DEP_FILES or p.name.startswith("requirements")})
    readme = next((p for p in files if p.parent == dest and p.name.lower().startswith("readme")), None)
    rtext = readme.read_text(errors="replace") if readme else ""
    rec["readme_chars"] = len(rtext)
    rec["readme_run_cmds"] = len(RUN_CMD.findall(rtext))
    ow, ol, pr = Counter(), 0, Counter()
    for p in files:
        if p.suffix.lower() in TEXT_EXT and p.stat().st_size < 400_000:
            t = p.read_text(errors="replace")
            ow.update(m.group(0).lower() for m in C.OPEN_WEIGHT.finditer(t))
            ol += len(C.OLLAMA.findall(t))
            pr.update(m.group(0).lower() for m in C.PROPRIETARY.finditer(t))
    rec["open_weight_hits"] = sum(ow.values())
    rec["open_weight_terms"] = dict(ow.most_common(8))
    rec["ollama_hits"] = ol
    rec["proprietary_hits"] = sum(pr.values())
    rec["proprietary_terms"] = dict(pr.most_common(5))
    rec["license"] = next((p.name for p in files if p.parent == dest and p.name.upper().startswith(("LICENSE", "LICENCE", "COPYING"))), "")
    # round 4
    rec["round"] = 4
    if rec["open_weight_hits"] < 2:
        rec["reason"] = ("only proprietary LLM APIs" if rec["proprietary_hits"] else "no open-weight model usage found")
        shutil.rmtree(dest, ignore_errors=True)
        return rec
    # round 5
    rec["round"] = 5
    problems = []
    if rec["main_language"] != "python":
        problems.append(f"main language {rec['main_language'] or 'unknown'}")
    if not rec["dep_files"]:
        problems.append("no dependency file")
    if rec["readme_run_cmds"] == 0:
        problems.append("README gives no run commands")
    if rec["last_commit"][:10] < C.PUSHED_AFTER:
        problems.append(f"last commit {rec['last_commit'][:10]}")
    if problems:
        rec["reason"] = "; ".join(problems)
        shutil.rmtree(dest, ignore_errors=True)
        return rec
    rec["round"] = 6
    rec["kept"] = True
    rec["clone"] = str(dest)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    CLONES.mkdir(parents=True, exist_ok=True)
    links = [json.loads(l) for l in (C.DATA / "r3_links.jsonl").read_text().splitlines() if l.strip()]
    papers_of: dict[str, list[dict]] = {}
    for l in links:
        if l.get("artifact_repo"):
            papers_of.setdefault(l["artifact_repo"], []).append(l)
    out = C.DATA / "r4_repos.jsonl"
    done = {json.loads(l)["repo"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    todo = [r for r in papers_of if r not in done]
    print(f"{len(links)} papers, {len(papers_of)} distinct artefact repositories, {len(todo)} to screen", flush=True)
    with out.open("a") as fh, ThreadPoolExecutor(a.workers) as ex:
        for k, rec in enumerate(ex.map(screen, todo), 1):
            rec["papers"] = [{"id": p["id"], "title": p["title"], "venue": p["venue"], "year": p["year"], "doi": p["doi"],
                              "arxiv": p.get("arxiv", "")} for p in papers_of[rec["repo"]]]
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 25 == 0:
                print(f"{k}/{len(todo)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
