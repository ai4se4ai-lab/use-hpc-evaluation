#!/usr/bin/env python3
"""Print lines of a screened paper's cached full text that match a pattern (manual round 6 helper).

    use-hpc-eval paper-text <owner/repo> <regex> [max_lines]

Reads the full texts cached by s03 under $REPRO_WORK/text/.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys

from use_hpc_eval import config as C


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    repo, pat = sys.argv[1].lower(), re.compile(sys.argv[2], re.I)
    mx = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    for l in (C.DATA / "r3_links.jsonl").read_text().splitlines():
        r = json.loads(l)
        if r.get("artifact_repo") != repo:
            continue
        urls = [f"https://arxiv.org/pdf/{r['arxiv']}"] if r.get("arxiv") else []
        for u in urls + list(r.get("pdf_urls", [])):
            f = C.WORK / "text" / (hashlib.sha1(u.encode()).hexdigest() + ".txt.gz")
            if f.exists():
                t = gzip.decompress(f.read_bytes()).decode(errors="replace")
                print(f"== {r['title'][:90]} ({u})")
                n = 0
                for line in t.splitlines():
                    if pat.search(line) and n < mx:
                        print("   " + re.sub(r"\s+", " ", line.strip())[:170])
                        n += 1
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
