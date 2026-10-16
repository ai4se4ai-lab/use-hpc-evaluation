"""Shared configuration of the evaluation: paths and every selection criterion (RQ3 of the MSR paper, RQ5 of EMSE).

Every criterion of every filtering round is defined here, so the papers can cite one place.
Standard library only. Paths can be overridden with environment variables:

    USE_HPC_EVAL_DATA     committed evaluation data (default: <repo>/data)
    USE_HPC_EVAL_STUDIES  per-Artifact use-hpc configurations (default: <repo>/studies)
    REPRO_WORK            large, uncommitted work files: PDFs, clones, runs (default: $SCRATCH/use-hpc-eval)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                       # repository root (src/use_hpc_eval/ -> ..)
DATA = Path(os.environ.get("USE_HPC_EVAL_DATA", str(ROOT / "data")))
STUDIES = Path(os.environ.get("USE_HPC_EVAL_STUDIES", str(ROOT / "studies")))
CONFIGS = STUDIES / "configs"     # one directory per selected Artifact (owner__name)
COMMON = STUDIES / "common"       # compare_lib.py and model-server hooks shared by all Artifacts
PROBES = STUDIES / "probes"       # probe specifications (s09) for Artifacts that cannot run as documented
PILOT = DATA / "pilot"            # sacct dump and derived CSVs of the 44,352-run pilot (RQ1-2)
MAILTO = os.environ.get("OPENALEX_MAILTO", "ai4se4ai@gmail.com")   # OpenAlex "polite pool"
SCRATCH = Path(os.environ.get("SCRATCH", str(Path.home() / "scratch")))
WORK = Path(os.environ.get("REPRO_WORK", str(SCRATCH / "use-hpc-eval")))   # clones, PDFs (not in git)

# ── Round 0: venues and years (OpenAlex source IDs; FSE = the FSE issues of PACMSE from 2024) ─
YEARS = "2024-2026"
VENUES = {
    "ICSE": {"source": "S7407086679"},
    "FSE": {"source": "S4404663975", "issue": "FSE"},          # Proc. ACM Softw. Eng. (PACMSE), FSE track
    "ASE": {"source": "S4363608212"},
    "TSE": {"source": "S8351582"},
    "EMSE": {"source": "S109852484"},
    "TOSEM": {"source": "S142627899"},
}

# ── Round 1: research papers only (no front matter, keynotes, very short papers) ─────────
MIN_PAGES = 8                     # when OpenAlex has page numbers; journals often lack them (then kept)
EXCLUDE_TITLE = re.compile(r"^(front matter|frontmatter|message from|welcome|keynote|panel|tutorial|"
                           r"proceedings|table of contents|index|erratum|correction|editorial|"
                           r"introduction to the special|in memoriam)", re.I)

# ── Round 2: topic = LLM-based or LLM-evaluating work (title or abstract) ──────────────────
LLM_TOPIC = re.compile(r"\b(large language models?|LLMs?|language models?|code models?|foundation models?|"
                       r"GPT-?\d|ChatGPT|Codex|Code ?Llama|Llama|StarCoder|DeepSeek|Qwen|Mistral|"
                       r"transformer-based|pre-?trained models? of code|code generation models?|AI coding)\b", re.I)

# ── Round 3: artefact = a public GitHub repository is linked from the paper ────────────────
GITHUB_URL = re.compile(r"github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]{1,100})", re.I)
NOT_ARTEFACT_OWNERS = {"features", "topics", "about", "orgs", "sponsors", "marketplace", "apps", "login", "settings",
                       "openai", "microsoft", "facebookresearch", "meta-llama", "huggingface", "ollama", "pytorch",
                       "tensorflow", "google", "google-research", "deepmind", "anthropics", "evalplus",
                       "bigcode-project", "deepseek-ai", "qwenlm", "mistralai", "langchain-ai", "features",
                       "tree-sitter", "apache", "github", "dear-github", "badges", "shields", "nltk", "scikit-learn", "numpy", "pandas-dev"}

# ── Round 4: open-weight models (repository content) ─────────────────────────────────────
OLLAMA = re.compile(r"\bollama\b", re.I)
OPEN_WEIGHT = re.compile(r"\b(ollama|vllm|llama[._-]?cpp|text-generation-inference|code[-_ ]?llama|llama[-_ ]?[23]|"
                         r"llama-?3\.\d|deepseek[-_ ]?coder|qwen\d?(\.\d)?[-_ ]?(coder)?|starcoder2?|mistral|mixtral|"
                         r"codegemma|gemma|phi-?[234]|wizardcoder|magicoder|codet5p?|santacoder|incoder|codegen2?|"
                         r"granite|AutoModelForCausalLM|from_pretrained)\b", re.I)
PROPRIETARY = re.compile(r"\b(openai\.|OpenAI\(|OPENAI_API_KEY|gpt-4|gpt-3\.5|anthropic|claude-|gemini-|"
                         r"google\.generativeai|azure_openai)\b", re.I)

# ── Round 5: runnable on the cluster ─────────────────────────────────────────────────────
DEP_FILES = ("requirements.txt", "requirements", "environment.yml", "environment.yaml", "pyproject.toml",
             "setup.py", "setup.cfg", "Pipfile", "poetry.lock", "Dockerfile")
MAX_REPO_MB_SMALL_FILES = 500     # size of the repository without blobs > 1 MB
PUSHED_AFTER = "2023-06-01"       # last commit after this date (maintained around publication)

# ── Round 6: feasibility within the study's budget (manual, see manual_screening.csv) ──────
MAX_MODEL_PARAMS_B = 34           # one model must fit one 80 GB H100 (4-bit or bf16 <= 34B)
MAX_SMOKE_GPU_HOURS = 2
MAX_FULL_GPU_HOURS = 300          # per repository, for the reported subset of experiments
TOP_K = 10


def norm_repo(owner: str, name: str) -> str:
    name = re.sub(r"(\.git|[.,;:)\]}>'\"]+)$", "", name)
    return f"{owner}/{name}".lower()
