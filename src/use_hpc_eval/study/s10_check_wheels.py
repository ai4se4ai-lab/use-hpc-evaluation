#!/usr/bin/env python3
"""Step 10 — pre-check that a repository's requirements resolve from the wheelhouse (+ the study wheel directory)
BEFORE submitting, with `pip install --dry-run` in a throw-away venv (login node, seconds, nothing installed).

    use-hpc-eval check-wheels [repo_id ...]

Uses the modules of the repository's cluster.env, so module-provided packages (e.g. opencv for vLLM) count.
Prints OK or pip's first error per repository.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile

from use_hpc_eval import config as C

CONFIGS = C.CONFIGS


def check(rid: str) -> bool:
    env = C.WORK / "repos" / rid / "hpc" / "config" / "cluster.env"
    req = C.WORK / "repos" / rid / "hpc" / "config" / "requirements.txt"
    with tempfile.TemporaryDirectory() as td:
        script = f"""set -a; source {env}; set +a
module purge >/dev/null 2>&1; module load $MODULES >/dev/null 2>&1 || {{ echo "module load failed: $MODULES"; exit 3; }}
virtualenv --no-download -q {td}/v && source {td}/v/bin/activate
pip install --no-index -q --dry-run --find-links "$EXTRA_WHEELS" -r {req} 2>&1 | grep -E "ERROR|error:" | head -3
exit ${{PIPESTATUS[0]}}"""
        r = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, timeout=600)
    out = (r.stdout + r.stderr).strip()
    ok = r.returncode == 0 and "ERROR" not in out
    print(f"{rid:<40} {'OK' if ok else 'FAIL'}  {'' if ok else out[:300]}")
    return ok


def main() -> int:
    ids = sys.argv[1:] or sorted(p.name for p in CONFIGS.iterdir() if (p / "experiments.json").exists())
    return 0 if all([check(i) for i in ids]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
