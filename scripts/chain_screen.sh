#!/bin/bash
# Selection rounds 3-5 in sequence (network-bound, hours): find Artifact links, screen the repositories, rank.
# Run where outbound internet is allowed; logs go to data/s0{3,4,5}.log. Resumable: rerun after an interruption.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m use_hpc_eval find-repos > data/s03.log 2>&1
python3 -m use_hpc_eval screen --workers 6 > data/s04.log 2>&1
python3 -m use_hpc_eval rank > data/s05.log 2>&1
echo CHAIN_DONE >> data/s05.log
