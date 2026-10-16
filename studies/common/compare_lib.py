"""Shared comparison logic of the reproduction study (copied next to each repository's compare.py).

reported.csv (one row per number the paper reports for the reproduced subset):
    key, metric, reported, tolerance, source, comparable
      key        setting the number belongs to (e.g. "qwen2.5-coder-32b|livecodebench|execre")
      reported   the paper's value (in the paper's unit; percentages as numbers, e.g. 41.5)
      tolerance  absolute tolerance for "reproduced" (from the paper's own variance where stated, else the
                 study default: 2 points for percentages, 5% relative otherwise)
      source     table/figure/page of the paper
      comparable "yes", or the reason the artefact cannot produce this number (e.g. "evaluation code missing")
measured.csv (written by the repository's compare.py): key, metric, measured, n (units averaged), note
comparison.csv: the join, with abs_diff, rel_diff and status in
    reproduced        |measured - reported| <= tolerance
    deviates          measured exists but outside tolerance
    missing           comparable, but the run produced no value for it
    not_comparable    the artefact cannot produce the number (reason kept)
"""
from __future__ import annotations

import csv
from pathlib import Path


def read(p: Path) -> list[dict]:
    return list(csv.DictReader(p.open())) if p.exists() else []


def write(rows: list[dict], p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols or ["key"])
        w.writeheader()
        w.writerows(rows)


def compare(results: Path, reported_csv: Path, measured: list[dict]) -> list[dict]:
    out_dir = results / "compare"
    write(measured, out_dir / "measured.csv")
    mm = {(m["key"], m["metric"]): m for m in measured}
    rows = []
    for r in read(reported_csv):
        m = mm.get((r["key"], r["metric"]))
        row = {"key": r["key"], "metric": r["metric"], "reported": r["reported"], "source": r.get("source", ""),
               "measured": m["measured"] if m else "", "n": m.get("n", "") if m else ""}
        if r.get("comparable", "yes").strip().lower() != "yes":
            row["status"], row["note"] = "not_comparable", r["comparable"]
        elif not m or m["measured"] in ("", None):
            row["status"], row["note"] = "missing", "no measured value"
        else:
            rep, mea = float(r["reported"]), float(m["measured"])
            tol = float(r["tolerance"]) if r.get("tolerance") else (2.0 if abs(rep) > 1.5 else 0.02) if abs(rep) <= 100 else 0.05 * abs(rep)
            row.update({"abs_diff": round(mea - rep, 4), "rel_diff": round((mea - rep) / rep, 4) if rep else "",
                        "tolerance": tol, "status": "reproduced" if abs(mea - rep) <= tol else "deviates",
                        "note": m.get("note", "")})
        rows.append(row)
    write(rows, out_dir / "comparison.csv")
    st = {}
    for r in rows:
        st[r["status"]] = st.get(r["status"], 0) + 1
    print("comparison:", st)
    return rows
