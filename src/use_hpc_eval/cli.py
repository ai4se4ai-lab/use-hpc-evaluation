"""`use-hpc-eval`: one entry point for every step of the evaluation.

    use-hpc-eval list                  # all commands, their step number and what they need
    use-hpc-eval paths                 # where data, study configurations and work files are
    use-hpc-eval <command> [args...]   # run one step; `--help` where the step takes options

Each command is a module with a main() that reads sys.argv, so a step can also be run with
`python -m use_hpc_eval.<package>.<module>`.
"""
from __future__ import annotations

import importlib
import sys
from typing import NamedTuple


class Step(NamedTuple):
    step: str
    module: str
    phase: str
    needs: str
    summary: str


COMMANDS: dict[str, Step] = {
    # Phase A: study selection (RQ3 of the MSR paper, RQ5 of the EMSE paper)
    "collect": Step("s01", "selection.s01_collect_papers", "select", "internet",
                    "round 0: every ICSE/FSE/ASE/TSE/EMSE/TOSEM paper of 2024-2026 from OpenAlex"),
    "filter": Step("s02", "selection.s02_filter_topic", "select", "offline",
                   "rounds 1-2: research papers about or using LLMs"),
    "find-repos": Step("s03", "selection.s03_find_repos", "select", "internet, pdftotext",
                       "round 3: the GitHub Artifact linked in each paper's full text"),
    "screen": Step("s04", "selection.s04_screen_repos", "select", "internet, git",
                   "rounds 3-5: cloneable, open-weight models, runnable Python"),
    "rank": Step("s05", "selection.s05_rank_select", "select", "offline",
                 "rank, apply manual round 6 (data/manual_screening.csv), select the top 10"),
    "triage": Step("--", "selection.triage", "select", "clones",
                   "print the facts a screener needs for M0-M6 (ranks FROM TO)"),
    "paper-text": Step("--", "selection.paper_text", "select", "text cache",
                       "grep a screened paper's cached full text (REPO REGEX [N])"),
    "selection-tex": Step("s07", "selection.s07_latex", "select", "offline",
                          "LaTeX tables and figure data of the selection funnel"),
    # Phase B: applying use-hpc to the selected Artifacts
    "fetch": Step("s06", "study.s06_fetch_and_scaffold", "study", "internet, git, use-hpc skill",
                  "clone each selected Artifact at its screened commit and scaffold hpc/"),
    "configure": Step("s08", "study.s08_configure", "study", "clones",
                      "install studies/configs/<id>/ into each clone's hpc/"),
    "probe": Step("s09", "study.s09_probe_config", "study", "offline",
                  "write a probe configuration from a probe spec (ID SPEC.json)"),
    "check-wheels": Step("s10", "study.s10_check_wheels", "study", "Alliance modules, wheelhouse",
                         "dry-run pip against the wheelhouse before submitting"),
    "results": Step("s11", "study.s11_results", "study", "run logs, sacct",
                    "reproduction outcomes and cost per Artifact"),
    "gates": Step("s12", "study.s12_study_gates", "study", "offline (--refresh: run logs)",
                  "setup gates, causes, cancellations, cost, configuration size"),
    # Pilot (RQ1-2)
    "pilot": Step("--", "pilot.analyze_pilot", "pilot", "pilot logs",
                  "benefit and cost of use-hpc on the 44,352-run pilot (--logs DIR)"),
}


def _list() -> None:
    print(f"{'command':<14} {'step':<4} {'phase':<7} {'needs':<30} summary")
    for name, s in COMMANDS.items():
        print(f"{name:<14} {s.step:<4} {s.phase:<7} {s.needs:<30} {s.summary}")


def _paths() -> None:
    from use_hpc_eval import config as C
    for k in ("ROOT", "DATA", "PILOT", "STUDIES", "CONFIGS", "COMMON", "PROBES", "WORK"):
        print(f"{k:<8} {getattr(C, k)}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        _list()
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        _list()
        return 0
    if cmd == "paths":
        _paths()
        return 0
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\n")
        _list()
        return 2
    mod = importlib.import_module(f"use_hpc_eval.{COMMANDS[cmd].module}")
    sys.argv = [f"use-hpc-eval {cmd}", *rest]
    return int(mod.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
