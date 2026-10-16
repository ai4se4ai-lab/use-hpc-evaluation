#!/usr/bin/env python3
"""Step 3 — round 3 input: find the artefact repository of every LLM paper in its full text.

    use-hpc-eval find-repos [--limit N]     data/r2_llm_papers.jsonl -> data/r3_links.jsonl

For each paper (resumable; one JSON line per paper):
  1. GitHub URLs in the abstract (OpenAlex);
  2. if the paper has no arXiv id and no open-access PDF, an arXiv title search (exact normalised title match);
  3. the full text: arXiv PDF, else the first open-access PDF, converted with pdftotext (the PDF is deleted);
  4. every github.com/<owner>/<repo> link scored as the candidate artefact (see score_links); the highest positive
     score is the candidate, verified later (s04 clones it, the manual round checks it against the paper).
     Zenodo/Figshare/OSF links are recorded as alternative artefacts.
arXiv's guidance of one request per 3 s is respected.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from use_hpc_eval import config as C

UA = {"User-Agent": f"use-hpc-eval research crawler ({C.MAILTO})"}
CTX = re.compile(r"replicat|artifact|artefact|package|available|our code|source code|reproduc|open[- ]source|"
                 r"released|implementation|github repository|we (make|provide|publish)", re.I)
OTHER = re.compile(r"(zenodo\.org/(?:record|records|doi)/[\w./-]+|doi\.org/10\.5281/zenodo\.\d+|figshare\.com/[\w./-]+|osf\.io/[\w]+)", re.I)
_last = [0.0]


def polite(host: str) -> None:
    gap = 3.1 if "arxiv" in host else 0.5
    wait = _last[0] + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def fetch(url: str, binary: bool = False, timeout: int = 90):
    polite(urllib.parse.urlparse(url).netloc)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data if binary else data.decode(errors="replace")


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def arxiv_by_title(title: str) -> str:
    q = urllib.parse.quote(f'ti:"{re.sub(r"[^A-Za-z0-9 ]+", " ", title)[:200]}"')
    try:
        xml = fetch(f"https://export.arxiv.org/api/query?search_query={q}&max_results=5")
    except Exception:  # noqa: BLE001
        return ""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(xml).findall("a:entry", ns):
        if norm_title(e.findtext("a:title", "", ns)) == norm_title(title):
            m = re.search(r"abs/(\d{4}\.\d{4,5})", e.findtext("a:id", "", ns))
            if m:
                return m.group(1)
    return ""


TEXT_CACHE = C.WORK / "text"


def pdf_text(url: str) -> str:
    """Text of a PDF via pdftotext, cached as gzip on scratch (key = URL) so re-scoring never re-downloads."""
    import gzip
    import hashlib
    TEXT_CACHE.mkdir(parents=True, exist_ok=True)
    cf = TEXT_CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".txt.gz")
    if cf.exists():
        return gzip.decompress(cf.read_bytes()).decode(errors="replace")
    data = fetch(url, binary=True)
    if not data[:5] == b"%PDF-":
        return ""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        out = subprocess.run(["pdftotext", "-q", "-layout", f.name, "-"], capture_output=True, timeout=120)
    text = out.stdout.decode(errors="replace")
    cf.write_bytes(gzip.compress(text.encode()))
    return text


DATA_AVAIL = re.compile(r"(data availability|availability of data|replication package|artifact availability|"
                        r"open science|data and code availability|code availability)", re.I)


def score_links(text: str, abstract_links: list[str], title: str = "", abstract: str = "") -> list[dict]:
    """Score every GitHub link of the paper as the candidate artefact repository.

    + 4  the 150 characters before the link mention replication/artifact/available/our code/...
    + 3  a token of the repository name (>= 4 chars) occurs in the paper's title or abstract (its tool name)
    + 2  the link occurs in the first 12% of the text (title page footnotes, abstract, introduction)
    + 2  the link occurs after a data-availability / replication-package heading
    + 2  the link is in the abstract;  + min(occurrences, 3)
    - 6  the owner is a platform or third-party tool (config.NOT_ARTEFACT_OWNERS)
    """
    flat = re.sub(r"-[ \t]*\n\s*", "-", text)      # a line break after "-" inside a URL keeps the hyphen
    flat = re.sub(r"(github\.com/[\w.-]*/?)\s*\n\s*([\w.-]+)", r"\1\2", flat)   # URL wrapped without hyphen
    flat = re.sub(r"\s+", " ", flat)
    n = max(len(flat), 1)
    da = [m.start() for m in DATA_AVAIL.finditer(flat)]
    words = set(re.findall(r"[a-z0-9]{4,}", (title + " " + abstract).lower()))
    found: dict[str, dict] = {}
    for m in C.GITHUB_URL.finditer(flat):
        repo = C.norm_repo(m.group(1), m.group(2))
        d = found.setdefault(repo, {"repo": repo, "count": 0, "ctx": 0, "early": 0, "da": 0})
        d["count"] += 1
        if CTX.search(flat[max(0, m.start() - 150): m.start()]):
            d["ctx"] = 4
        if m.start() < 0.12 * n:
            d["early"] = 2
        if any(0 <= m.start() - p < 1500 for p in da):
            d["da"] = 2
    for repo in abstract_links:
        found.setdefault(repo, {"repo": repo, "count": 0, "ctx": 0, "early": 2, "da": 0})["abstract"] = True
    out = []
    for d in found.values():
        owner, name = d["repo"].split("/", 1)
        toks = {t for t in re.split(r"[-_.]", name.lower()) if len(t) >= 4} | ({name.lower().replace("-", "").replace("_", "")} if len(name) >= 4 else set())
        overlap = 3 if toks & words else 0
        s = (d["ctx"] + overlap + d["early"] + d["da"] + (2 if d.get("abstract") else 0) + min(d["count"], 3)
             - (6 if owner in C.NOT_ARTEFACT_OWNERS else 0))
        out.append({"repo": d["repo"], "count": d["count"], "score": s, "title_overlap": bool(overlap),
                    "ctx": bool(d["ctx"]), "early": bool(d["early"]), "data_availability": bool(d["da"])})
    return sorted(out, key=lambda x: -x["score"])


MIN_ARTIFACT_SCORE = 4


def s2_arxiv_ids(dois: list[str]) -> dict[str, str]:
    """DOI -> arXiv id via the Semantic Scholar batch API (catches preprints whose title differs)."""
    out: dict[str, str] = {}
    cache = C.DATA / "s2_arxiv.json"
    if cache.exists():
        out = json.loads(cache.read_text())
    todo = [d for d in dois if d and d not in out]
    for i in range(0, len(todo), 400):
        chunk = todo[i:i + 400]
        body = json.dumps({"ids": ["DOI:" + d.replace("https://doi.org/", "") for d in chunk]}).encode()
        for k in range(5):
            try:
                req = urllib.request.Request("https://api.semanticscholar.org/graph/v1/paper/batch?fields=externalIds",
                                             data=body, headers={**UA, "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    res = json.loads(r.read())
                break
            except Exception as e:  # noqa: BLE001
                print(f"  S2 retry {k + 1}: {e}", flush=True)
                time.sleep(10 * (k + 1))
        else:
            continue
        for d, item in zip(chunk, res):
            out[d] = ((item or {}).get("externalIds") or {}).get("ArXiv") or ""
        cache.write_text(json.dumps(out))
        time.sleep(3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    papers = [json.loads(l) for l in (C.DATA / "r2_llm_papers.jsonl").read_text().splitlines() if l.strip()]
    out = C.DATA / "r3_links.jsonl"
    done = {json.loads(l)["id"] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    todo = [p for p in papers if p["id"] not in done][: a.limit or None]
    print(f"{len(done)} done, {len(todo)} to do", flush=True)
    s2 = s2_arxiv_ids([p["doi"] for p in todo if not p.get("arxiv")])
    print(f"Semantic Scholar: {sum(1 for v in s2.values() if v)} arXiv ids for {len(s2)} DOIs", flush=True)
    for p in todo:
        if not p.get("arxiv") and s2.get(p["doi"]):
            p["arxiv"], p["arxiv_via_s2"] = s2[p["doi"]], True
    with out.open("a") as fh:
        for k, p in enumerate(todo, 1):
            rec = {"id": p["id"], "title": p["title"], "venue": p["venue"], "year": p["year"], "doi": p["doi"],
                   "arxiv": p.get("arxiv", ""), "arxiv_via_s2": p.get("arxiv_via_s2", False), "source": "",
                   "text_chars": 0, "error": ""}
            try:
                if not rec["arxiv"] and not p.get("pdf_urls"):
                    rec["arxiv"] = arxiv_by_title(p["title"])
                    rec["arxiv_by_title"] = bool(rec["arxiv"])
                text = ""
                if rec["arxiv"]:
                    text, rec["source"] = pdf_text(f"https://arxiv.org/pdf/{rec['arxiv']}"), "arxiv"
                if not text:
                    for u in [x for x in p.get("pdf_urls", []) if "arxiv.org" not in x][:2]:
                        try:
                            text, rec["source"] = pdf_text(u), urllib.parse.urlparse(u).netloc
                        except Exception as e:  # noqa: BLE001
                            rec["error"] = f"{type(e).__name__}: {str(e)[:80]}"
                        if text:
                            break
                if not text and not rec["arxiv"]:          # publisher PDF blocked: look for the preprint
                    rec["arxiv"] = arxiv_by_title(p["title"])
                    rec["arxiv_by_title"] = bool(rec["arxiv"])
                    if rec["arxiv"]:
                        text, rec["source"] = pdf_text(f"https://arxiv.org/pdf/{rec['arxiv']}"), "arxiv"
                rec["text_chars"] = len(text)
                rec["links"] = score_links(text + " " + (p.get("abstract") or ""), p.get("abstract_github", []),
                                           p["title"], p.get("abstract") or "")
                rec["other_artifacts"] = sorted(set(OTHER.findall(text)))[:5]
                if not text:
                    rec["source"] = rec["source"] or "none"
            except Exception as e:  # noqa: BLE001
                rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
                rec["links"] = score_links(p.get("abstract") or "", p.get("abstract_github", []), p["title"], p.get("abstract") or "")
            best = rec["links"][0] if rec.get("links") and rec["links"][0]["score"] >= MIN_ARTIFACT_SCORE else None
            rec["artifact_repo"] = best["repo"] if best else ""
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            if k % 25 == 0:
                print(f"{k}/{len(todo)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
