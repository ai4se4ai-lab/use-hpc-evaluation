#!/usr/bin/env python3
"""Step 1 — collect every paper of ICSE, FSE, ASE, TSE, EMSE and TOSEM published 2024–2026 from OpenAlex.

    use-hpc-eval collect            -> data/papers.jsonl

DBLP was the first choice but its automated access is behind bot protection (Anubis) at the time of the study,
so OpenAlex (open, CC0) is used; venue -> source IDs are in config.py. One line per work: id, doi, title, year,
venue, type, pages, abstract (rebuilt from OpenAlex's inverted index), arXiv id (if a location is on arXiv),
open-access PDF URLs, and GitHub URLs found in the abstract. Cursor paging, polite pool, resumable.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

from use_hpc_eval import config as C


def get(url: str, tries: int = 5) -> dict:
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": f"use-hpc-eval ({C.MAILTO})"}),
                                        timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"  retry {k + 1}: {e}")
            time.sleep(2 * (k + 1))
    raise RuntimeError(url)


def abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {}
    for w, idx in inv.items():
        for i in idx:
            pos[i] = w
    return " ".join(pos[i] for i in sorted(pos))


def arxiv_id(work: dict) -> str:
    for loc in work.get("locations") or []:
        for u in (loc.get("landing_page_url") or "", loc.get("pdf_url") or ""):
            m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", u)
            if m:
                return m.group(1)
    ids = work.get("ids") or {}
    return ""


def main() -> int:
    out = C.DATA / "papers.jsonl"
    seen = set()
    if out.exists():
        seen = {json.loads(l)["id"] for l in out.read_text().splitlines() if l.strip()}
    n_new = 0
    with out.open("a") as fh:
        for venue, v in C.VENUES.items():
            flt = f"primary_location.source.id:{v['source']},publication_year:{C.YEARS}"
            if v.get("issue"):
                flt += f",biblio.issue:{v['issue']}"
            cursor, got = "*", 0
            while cursor:
                url = ("https://api.openalex.org/works?" + urllib.parse.urlencode(
                    {"filter": flt, "per-page": 200, "cursor": cursor, "mailto": C.MAILTO,
                     "select": "id,doi,title,publication_year,type,biblio,abstract_inverted_index,locations,"
                               "open_access,best_oa_location,ids"}))
                d = get(url)
                for w in d.get("results", []):
                    got += 1
                    if w["id"] in seen:
                        continue
                    ab = abstract(w.get("abstract_inverted_index"))
                    b = w.get("biblio") or {}
                    pages = None
                    try:
                        pages = int(b["last_page"]) - int(b["first_page"]) + 1
                    except (TypeError, ValueError, KeyError):
                        pass
                    pdfs = sorted({loc["pdf_url"] for loc in (w.get("locations") or []) if loc.get("pdf_url")})
                    rec = {"id": w["id"], "doi": w.get("doi"), "title": w.get("title") or "", "year": w.get("publication_year"),
                           "venue": venue, "type": w.get("type"), "pages": pages, "abstract": ab,
                           "arxiv": arxiv_id(w), "pdf_urls": pdfs,
                           "abstract_github": sorted({C.norm_repo(*m) for m in C.GITHUB_URL.findall(ab)})}
                    fh.write(json.dumps(rec) + "\n")
                    seen.add(w["id"])
                    n_new += 1
                cursor = d.get("meta", {}).get("next_cursor")
                if not d.get("results"):
                    break
                time.sleep(0.2)
            print(f"{venue}: {got} works")
    print(f"new records: {n_new}; total: {len(seen)} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
