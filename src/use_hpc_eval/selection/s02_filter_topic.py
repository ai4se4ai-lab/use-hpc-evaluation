#!/usr/bin/env python3
"""Step 2 — rounds 1 and 2: research papers about / using LLMs.

    use-hpc-eval filter     data/papers.jsonl -> data/r2_llm_papers.jsonl, data/funnel.csv

Round 1 (research paper): drops front matter, keynotes, editorials, errata (title pattern) and papers with
fewer than MIN_PAGES pages when OpenAlex knows the page range.
Round 2 (LLM topic): the title or abstract matches config.LLM_TOPIC.
Every decision is written to data/decisions.csv (paper id, round, kept, reason).
"""
from __future__ import annotations

import csv
import json

from use_hpc_eval import config as C


def main() -> int:
    papers = [json.loads(l) for l in (C.DATA / "papers.jsonl").read_text().splitlines() if l.strip()]
    dec = []
    r1 = []
    for p in papers:
        t = p["title"].strip()
        if C.EXCLUDE_TITLE.search(t) or not t:
            dec.append((p["id"], 1, 0, "not a research paper (title)"))
        elif p.get("pages") is not None and 0 < p["pages"] < C.MIN_PAGES:
            dec.append((p["id"], 1, 0, f"short paper ({p['pages']} pages)"))
        else:
            r1.append(p)
            dec.append((p["id"], 1, 1, ""))
    r2 = []
    for p in r1:
        m = C.LLM_TOPIC.search(p["title"]) or C.LLM_TOPIC.search(p.get("abstract") or "")
        if m:
            r2.append(p)
            dec.append((p["id"], 2, 1, f"matched '{m.group(0)}'"))
        else:
            dec.append((p["id"], 2, 0, "no LLM topic in title/abstract"))
    with (C.DATA / "r2_llm_papers.jsonl").open("w") as fh:
        for p in r2:
            fh.write(json.dumps(p) + "\n")
    with (C.DATA / "decisions.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["paper_id", "round", "kept", "reason"])
        w.writerows(dec)
    with (C.DATA / "funnel.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["round", "description", "remaining"])
        w.writerow([0, f"ICSE/FSE/ASE/TSE/EMSE/TOSEM {C.YEARS} (OpenAlex)", len(papers)])
        w.writerow([1, "research papers", len(r1)])
        w.writerow([2, "LLM topic (title/abstract)", len(r2)])
    by = {}
    for p in r2:
        by[p["venue"]] = by.get(p["venue"], 0) + 1
    print(f"round 0: {len(papers)}  round 1: {len(r1)}  round 2: {len(r2)}  by venue: {by}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
