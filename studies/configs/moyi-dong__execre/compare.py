#!/usr/bin/env python3
"""ExeCRE: overall Pass@1 (mean over the n runs) as printed by the authors' analyzer (src.experiments.solution_chain
--skip_generate --skip_evaluate); the score files are parsed for the first 'overall'/'all' Pass@1 percentage."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_lib import compare
res, reported = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for f in sorted((res / "scores").glob("*.txt")):
    model, method = f.stem.split("_", 1)
    t = f.read_text(errors="replace")
    m = re.search(r"(?i)(overall|all)[^\n]*?(\d{1,3}\.\d+)", t) or re.search(r"(?i)pass@1[^\n]*?(\d{1,3}\.\d+)", t)
    val = float(m.groups()[-1]) if m else ""
    if val != "" and val <= 1.0:
        val = round(100 * val, 2)
    rows.append({"key": f"{model}|{method}", "metric": "pass@1 overall", "measured": val, "n": "", "note": "parsed from solution_chain output"})
compare(res, reported, rows)
