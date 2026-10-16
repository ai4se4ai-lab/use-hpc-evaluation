# Reproduction study log (RQ5)

Chronological record of decisions, defects and deviations. Times are EDT, 2026-10-13 unless noted.

## Selection pipeline

- DBLP's search API and table-of-contents exports are behind bot protection (Anubis), so OpenAlex is used (s01).
- s03 v1 dropped the hyphen at line breaks inside URLs (e.g. `google-\nresearch` became `googleresearch`), so such
  repositories looked unreachable. It was fixed (a line break after "-" keeps the hyphen) and all 1,574 papers were
  rescanned from scratch with the fixed code. The v1 output is kept as `r3_links.buggy-hyphen.jsonl`.
- s04 v1 crashed on a repository with a file name longer than the filesystem allows (osslab-pku/smartnote). It now
  records such errors as "clone failed".
- The manual round M0 ("own artefact") was added after the ranking surfaced third-party tools that papers had linked
  (OpenCompass, LlamaFactory, aider, crawl4ai, flash-attention, mypy).

## Defects found in use-hpc by smoke runs (fixed in the skill template)

| # | Defect | Found by | Fix |
|---|---|---|---|
| T1 | Placeholders inside `vars` values were not expanded (e.g. `WORK = {RESULTS}/work`) | configuring RetriGen (self-test) | `hpclib.fill` resolves up to 5 levels |
| T2 | The extra-wheel variable was named `PIP_FIND_LINKS`; pip reads every `PIP_*` environment variable as its own option, so it replaced the cluster wheelhouse and `pip install` found nothing | LLM4Perf smoke run (setup failed after 11 s; the gate cancelled its dependents) | renamed `EXTRA_WHEELS`, with a warning in `cluster.env` |

## Artefact defects and deviations (per repository)

- **klsc749/llm4perf**: the evaluation (performance-model training and metrics) is not in the artefact (sampler only),
  so the paper's numbers are not comparable. Dependencies are pinned newer than the wheelhouse; the exact pins were
  downloaded from PyPI into the study wheel directory.
- **isenglab/retrigen**:
  - `embed.sh` iterates `seq 1 3` over a 0-indexed bash array, so it skips the train split and passes an empty path
    (fixed in glue).
  - No code converts the hybrid-retrieval CSVs into `datas/*.jsonl`, or the predictions into the `RetriGen_{Label,Result}.txt`
    files that `acc.py` reads (glue added).
  - The embedding URL is hard-coded to `localhost:11434` and the model is `codellama:7b-code-fp16` (the README says
    `codellama:7b`).
  - torch 1.13.1 is unavailable, so 2.1.2 is used. CodeBLEU uses the `codebleu` package, because the authors' script
    needs tree_sitter 0.20.
- **frabbisw/robustextended**:
  - The README points to `generate_single_code_single_gpu.py` at the root; the file is in `run_code/`.
  - Model paths are hard-coded to `/home/f_rabbi/models/...` (mapped to Hugging Face ids in glue).
  - `requirements.txt` is a conda export (not pip-installable). It pins transformers 4.21.1, which cannot load
    Qwen2.5, so 4.45.2 is used.
  - The metrics script is a module-level driver hard-coded to all six models; its functions are loaded via `ast`
    instead.
  - The batch scripts target SGE (`qsub`) with conda and home-directory paths.
  - The paper reports the same configuration in Table 8 (EvalPlus tests) and Table 9 (HumanEval-X tests);
    measurements are compared with both.

## Screening correction (after cloning)

- **xiaozheng03asada/translibeval** was included on the basis of its README and model names, but its code calls
  Llama3-8B and CodeLlama-7B through the paid Baidu Qianfan API (`qianfan.Completion`). It fails M6, which was
  missed in the first screening pass (1 error in 21 decisions). Following the protocol, screening continued in rank
  order: #22 naturalcc (M0: general toolkit), #23 mazebreaker (M6: gpt-4o-mini mutator and judge), and
  #24 **leaperovo/logreasoner** (included as R10).

## Deviations found by setup gates (smoke runs, before any GPU computation)

- The wheelhouse's vLLM depends on `opencv-noinstall`, which is satisfied by loading the `opencv` module. Added
  `opencv/4.13.0` to MODULES for the vLLM repositories (ExeCRE, ProvenanceGuard, binary SPD).
- RetriGen pins `numpy==1.26.2`, which has no cp311 wheel, so 1.26.4 is used.
- ExeCRE needs `crowd-kit`, which is not in the wheelhouse; it was downloaded with its dependencies into the study
  wheel directory.
- Added a pre-submission wheel check (s10_check_wheels.py: `pip install --dry-run` against the wheelhouse on the
  login node), so these failures surface in seconds instead of after a queue wait.

## Executability probes

SemGuard, EffiSkel, IRCoCo and LogReasoner run as probes: every documented entry point, in README order, at
minimal size, in the real environment on a GPU node. A probe records each step's exit code and first error line.
Static observations made before the probes ran:

- **SemGuard**:
  - the README requires `requirements.txt`, which is absent;
  - the evaluator path inside the vendored `transformers/generation/utils.py` is the literal string `"evaluator path"`;
  - `from Models.models import CodeT5ClassBCE` refers to a module that does not exist;
  - `generate.py` loads `RobertaTokenizer`/`T5ForConditionalGeneration` for StarCoder2-7B;
  - `test_one_solution.sh` contains placeholder paths.
- **EffiSkel**: same code base as SemGuard; `AutoTokenizer.from_pretrained("")`.
- **IRCoCo**:
  - requires Python 3.7 and torch 1.9.1 (Python 3.7 is not available on the cluster; 3.10 is used);
  - SFT is delegated to the external CodeXGLUE pipeline;
  - the README commands contain placeholder paths (`PATH_OF_FINETUNED_GPT2`).
- **LogReasoner**:
  - configurations reference local model directories and the dataset names `reason_guidelines`/`reason_dpo_*`;
  - `inference_with_vllm.py` hard-codes `llama_models/llama-reason-lora` and `input/alarm_*.json`.
- `pyext==0.7`, the APPS test harness dependency of SemGuard, EffiSkel and IRCoCo, does not build on Python 3.11
  (`inspect.getargspec` was removed), so these probes run on Python 3.10, the newest version on which it builds. On
  Python 3.10 the arrow module provides no pyarrow, so the unused Hugging Face `datasets` dependency was dropped
  from the SemGuard and EffiSkel probes (their scripts import a local `Datasets/` package).
- `javalang` (IRCoCo) is not in the wheelhouse; its wheel was downloaded from PyPI into the study wheel directory.
- ExeCRE: loading LiveCodeBench prompts interactively for trust_remote_code (blocks batch jobs); set HF_DATASETS_TRUST_REMOTE_CODE=1 in the step environment (no code change).
