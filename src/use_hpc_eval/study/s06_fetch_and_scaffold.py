#!/usr/bin/env python3
"""Step 6 — fetch the selected repositories at their screened commit and scaffold use-hpc into each.

    use-hpc-eval fetch        data/selected.csv -> $REPRO_WORK/repos/<id>/

Full clone (all files, so data shipped in the repository is present) checked out at the commit recorded by
s04, then `scaffold.sh` of the use-hpc skill creates <repo>/hpc/. The pipeline configuration of each repository
(hpc/config/experiments.json, cluster.env, requirements.txt) is then written by an agent session with the
use-hpc skill and copied back to studies/configs/<id>/ for the replication package.
"""
from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path

from use_hpc_eval import config as C

SKILL = Path(os.environ.get("USE_HPC_SKILL", str(Path.home() / ".claude/skills/use-hpc")))


def main() -> int:
    rows = list(csv.DictReader((C.DATA / "selected.csv").open()))
    base = C.WORK / "repos"
    base.mkdir(parents=True, exist_ok=True)
    for r in rows:
        rid = r["repo"].replace("/", "__")
        dest = base / rid
        if not dest.exists():
            subprocess.run(["git", "clone", "-q", f"https://github.com/{r['repo']}", str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "-q", r["commit"]], check=True)
        if not (dest / "hpc").exists():
            subprocess.run(["bash", str(SKILL / "scripts" / "scaffold.sh"), str(dest)], check=True,
                           stdout=subprocess.DEVNULL)
        size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / 2**20
        print(f"{r['repo']:<50} {r['commit'][:10]}  {size:8.1f} MiB  -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
