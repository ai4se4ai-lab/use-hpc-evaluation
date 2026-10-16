# Convenience targets; every target is a thin wrapper around `use-hpc-eval`.
# Offline targets (tex, test, check) are light enough for a login node; the network steps are not run here.
PY      ?= python3
export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))
CLI     := $(PY) -m use_hpc_eval

.PHONY: help list paths test check rebuild-selection tex clean

help:            ## show the targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

list:            ## list every evaluation step
	@$(CLI) list

paths:           ## show resolved data, study and work paths
	@$(CLI) paths

test:            ## unit tests (stdlib unittest, offline, seconds)
	$(PY) -m unittest discover -s tests -t . -v

check: test      ## tests + verify the committed selection data regenerate byte for byte
	$(PY) scripts/verify_offline.py

rebuild-selection: ## rerun the offline selection steps (s02, s05, s07) on the committed data
	$(CLI) filter && $(CLI) rank && $(CLI) selection-tex

tex:             ## regenerate every LaTeX table from the committed CSVs
	$(CLI) selection-tex && $(CLI) gates

clean:           ## remove caches and build outputs
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf build dist src/*.egg-info .venv
