#!/usr/bin/env python3
"""Step 7 — LaTeX tables and figure data for docs/emse/emse-use-hpc.tex, generated from the CSVs (no hand-copied numbers).

    use-hpc-eval selection-tex       -> data/tex/{tab_funnel,tab_exclusions,tab_selected,tab_venues,fig_funnel}.tex

The paper \\input{}s these files, so rerunning steps 1–7 updates the paper.
"""
from __future__ import annotations

import csv
import json
from collections import Counter

from use_hpc_eval import config as C

OUT = C.DATA / "tex"


def esc(s) -> str:
    s = str(s)
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"), ("$", r"\$"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\^{}")):
        s = s.replace(a, b)
    return s


def num(n) -> str:
    return f"{int(n):,}".replace(",", "{,}")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    funnel = list(csv.reader((C.DATA / "funnel.csv").open()))[1:]
    rows = "\n".join(f"{esc(r[0])} & {esc(r[1])} & {num(r[2])} \\\\" for r in funnel)
    (OUT / "tab_funnel.tex").write_text(
        "\\begin{tabular}{@{}l l r@{}}\n\\toprule\nRound & Criterion & Remaining \\\\\n\\midrule\n" + rows +
        "\n\\bottomrule\n\\end{tabular}\n")
    coords = " ".join(f"({num(r[2]).replace('{,}', '')},{esc(r[0])}) [{num(r[2])}]" for r in funnel)
    labels = ",".join(esc(r[0]) for r in funnel)
    (OUT / "fig_funnel.tex").write_text(
        "\\begin{tikzpicture}\n\\begin{axis}[xbar, xmode=log, log basis x=10, width=0.85\\textwidth, height=5.2cm,\n"
        f"  symbolic y coords={{{labels}}}, ytick=data, y dir=reverse, xlabel={{papers / repositories remaining (log)}},\n"
        "  ylabel={round}, point meta=explicit symbolic, nodes near coords, nodes near coords style={font=\\scriptsize}, xmin=1, bar width=7pt,\n"
        "  xmajorgrids, grid style={black!12}, enlarge y limits=0.08]\n"
        f"\\addplot[fill=modelbar!70, draw=modelbar] coordinates {{{coords}}};\n\\end{{axis}}\n\\end{{tikzpicture}}\n")
    ex = list(csv.reader((C.DATA / "exclusion_reasons.csv").open()))[1:]
    (OUT / "tab_exclusions.tex").write_text(
        "\\begin{tabular}{@{}l r@{}}\n\\toprule\nExclusion reason (first failing criterion) & Repositories \\\\\n\\midrule\n"
        + "\n".join(f"{esc(r[0])} & {num(r[1])} \\\\" for r in ex[:12]) + "\n\\bottomrule\n\\end{tabular}\n")
    papers = [json.loads(l) for l in (C.DATA / "r2_llm_papers.jsonl").read_text().splitlines() if l.strip()]
    allp = [json.loads(l) for l in (C.DATA / "papers.jsonl").read_text().splitlines() if l.strip()]
    links = [json.loads(l) for l in (C.DATA / "r3_links.jsonl").read_text().splitlines() if l.strip()]
    va, vl, vr = Counter(p["venue"] for p in allp), Counter(p["venue"] for p in papers), \
        Counter(l["venue"] for l in links if l.get("artifact_repo"))
    (OUT / "tab_venues.tex").write_text(
        "\\begin{tabular}{@{}l r r r r@{}}\n\\toprule\nVenue & Papers & LLM topic & GitHub artefact & Share \\\\\n\\midrule\n"
        + "\n".join(f"{v} & {num(va[v])} & {num(vl[v])} & {num(vr[v])} & {100 * vr[v] / max(vl[v], 1):.0f}\\% \\\\"
                    for v in C.VENUES)
        + f"\n\\midrule\nTotal & {num(sum(va.values()))} & {num(sum(vl.values()))} & {num(sum(vr.values()))} & "
          f"{100 * sum(vr.values()) / max(sum(vl.values()), 1):.0f}\\% \\\\\n\\bottomrule\n\\end{{tabular}}\n")
    plan = C.DATA / "reproduction_plan.csv"
    if plan.exists():
        rows = list(csv.DictReader(plan.open()))
        body = "\n".join(f"{esc(r['id'])} & {esc(r['venue'])} & \\code{{{esc(r['repo'])}}} & {esc(r['mode'])} & "
                         f"{esc(r['models'])} & {esc(r['executed_subset'])} \\\\" for r in rows)
        (OUT / "tab_selected.tex").write_text(
            "\\begin{tabularx}{\\textwidth}{@{}l l l l >{\\raggedright\\arraybackslash}p{3.1cm} X@{}}\n\\toprule\n"
            "Id & Venue & Repository & Mode & Open-weight models & Executed subset \\\\\n\\midrule\n" + body +
            "\n\\bottomrule\n\\end{tabularx}\n")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
