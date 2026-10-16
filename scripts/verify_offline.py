#!/usr/bin/env python3
"""Check that the committed selection and study tables regenerate byte for byte from the committed inputs.

    python3 scripts/verify_offline.py          # or: make check

Copies data/ to a temporary directory, reruns the offline steps there (s02 filter, s05 rank, s07 selection-tex,
s12 gates without --refresh), and compares every file they write with the committed one. No network, no Slurm,
a few seconds on a login node. Exit code 0 when everything matches.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ["filter", "rank", "selection-tex", "gates"]
OUTPUTS = ["r2_llm_papers.jsonl", "decisions.csv", "funnel.csv", "shortlist.csv", "selected.csv",
           "exclusion_reasons.csv", "tex/tab_funnel.tex", "tex/fig_funnel.tex", "tex/tab_exclusions.tex",
           "tex/tab_selected.tex", "tex/tab_venues.tex", "results/study_runs.csv", "results/study_config.csv",
           "tex/tab_study_runs.tex", "tex/tab_study_summary.tex", "tex/tab_study_config.tex"]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        data = Path(td) / "data"
        shutil.copytree(ROOT / "data", data)
        env = {**os.environ, "USE_HPC_EVAL_DATA": str(data),
               "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT / "src"), os.environ.get("PYTHONPATH")]))}
        for step in STEPS:
            r = subprocess.run([sys.executable, "-m", "use_hpc_eval", step], env=env, capture_output=True, text=True)
            if r.returncode:
                print(f"FAIL {step}: exit {r.returncode}\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
                return 1
            print(f"ran  {step}")
        bad = 0
        for rel in OUTPUTS:
            a, b = ROOT / "data" / rel, data / rel
            if not a.exists():
                continue
            same = b.exists() and filecmp.cmp(a, b, shallow=False)
            bad += not same
            print(f"{'ok  ' if same else 'DIFF'} data/{rel}")
        print("all regenerated files match" if not bad else f"{bad} file(s) differ")
        return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
