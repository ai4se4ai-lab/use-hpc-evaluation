#!/usr/bin/env python3
"""Step 5 — rank the repositories that passed rounds 3–5, apply the manual round 6, select the top 10.

    use-hpc-eval rank        -> data/shortlist.csv, data/selected.csv, data/funnel.csv

Ranking (automatic, deterministic): repositories are ordered by
    score = 10·[uses Ollama] + 2·log2(1 + open-weight mentions) + min(README run commands, 5)
            + 2·[last commit in 2025 or later] + 1·[licence file] − 2·[also calls proprietary APIs]
Round 6 (manual feasibility, data/manual_screening.csv) is applied in rank order. Each screened repository gets
one decision with the first failing criterion:
    M0 the repository is the paper's own artefact (not a third-party tool, benchmark or library it used)
    M1 the paper reports quantitative results of an open-weight-model experiment that the repository runs
    M2 that experiment has a documented entry point in the repository
    M3 its data/benchmarks are public and downloadable
    M4 its models are open-weight, available (Hugging Face or Ollama) and <= config.MAX_MODEL_PARAMS_B parameters
    M5 the reproduced subset fits config.MAX_FULL_GPU_HOURS on H100s
    M6 no human participants or paid services are needed for the reproduced subset
The first config.TOP_K repositories that pass M1–M6 are selected. Screening stops once TOP_K are selected.
"""
from __future__ import annotations

import csv
import json
import math

from use_hpc_eval import config as C

FIELDS = ["rank", "repo", "score", "ollama_hits", "open_weight_hits", "proprietary_hits", "readme_run_cmds",
          "last_commit", "license", "venue", "year", "title", "doi", "arxiv", "top_terms"]


def score(r: dict) -> float:
    return round(10 * (r["ollama_hits"] > 0) + 2 * math.log2(1 + r["open_weight_hits"]) + min(r["readme_run_cmds"], 5)
                 + 2 * (r["last_commit"][:4] >= "2025") + (1 if r["license"] else 0) - 2 * (r["proprietary_hits"] > 0), 2)


def main() -> int:
    repos = [json.loads(l) for l in (C.DATA / "r4_repos.jsonl").read_text().splitlines() if l.strip()]
    links = [json.loads(l) for l in (C.DATA / "r3_links.jsonl").read_text().splitlines() if l.strip()]
    kept = [r for r in repos if r["kept"]]
    for r in kept:
        r["score"] = score(r)
    kept.sort(key=lambda r: (-r["score"], r["repo"]))
    with (C.DATA / "shortlist.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for i, r in enumerate(kept, 1):
            p = r["papers"][0]
            w.writerow({"rank": i, "repo": r["repo"], "score": r["score"], "ollama_hits": r["ollama_hits"],
                        "open_weight_hits": r["open_weight_hits"], "proprietary_hits": r["proprietary_hits"],
                        "readme_run_cmds": r["readme_run_cmds"], "last_commit": r["last_commit"][:10],
                        "license": r["license"], "venue": p["venue"], "year": p["year"], "title": p["title"],
                        "doi": p["doi"], "arxiv": p["arxiv"],
                        "top_terms": " ".join(f"{k}:{v}" for k, v in list(r["open_weight_terms"].items())[:5])})
    manual = {}
    mf = C.DATA / "manual_screening.csv"
    if mf.exists():
        with mf.open() as fh:
            for row in csv.DictReader(fh):
                manual[row["repo"]] = row
    selected, screened = [], 0
    for r in kept:
        if len(selected) >= C.TOP_K:
            break
        m = manual.get(r["repo"])
        if not m:
            break                       # screening proceeds strictly in rank order
        screened += 1
        if m["decision"].strip().lower() == "include":
            selected.append({**m, "rank": kept.index(r) + 1, "score": r["score"], "commit": r["commit"],
                             "venue": r["papers"][0]["venue"], "year": r["papers"][0]["year"],
                             "title": r["papers"][0]["title"], "doi": r["papers"][0]["doi"]})
    if selected:
        with (C.DATA / "selected.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(selected[0]))
            w.writeheader()
            w.writerows(selected)
    r3 = sum(1 for l in links if l.get("artifact_repo"))
    distinct = len({l["artifact_repo"] for l in links if l.get("artifact_repo")})
    reach = sum(1 for r in repos if r["round"] >= 4)
    r4 = sum(1 for r in repos if r["round"] >= 5)
    funnel = list(csv.reader((C.DATA / "funnel.csv").open()))[:4]
    funnel += [[3, "paper links a GitHub artefact (full text)", r3],
               ["3b", "distinct repositories", distinct],
               ["3c", "reachable and cloneable", reach],
               [4, "uses open-weight models", r4],
               [5, "Python, dependencies, run commands, maintained", len(kept)],
               [6, f"manual feasibility M1-M6 (screened in rank order: {screened})", len(selected)]]
    with (C.DATA / "funnel.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows(funnel)
    reasons = {}
    for r in repos:
        if not r["kept"]:
            key = f"round {r['round']}: " + r["reason"].split(";")[0].split(" (")[0]
            reasons[key] = reasons.get(key, 0) + 1
    with (C.DATA / "exclusion_reasons.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["reason", "repositories"])
        w.writerows(sorted(reasons.items(), key=lambda x: -x[1]))
    for row in funnel:
        print("  ".join(str(x) for x in row))
    print(f"shortlist: {len(kept)} -> data/shortlist.csv; selected: {len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
