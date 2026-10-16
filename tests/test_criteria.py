import unittest

from tests import _path  # noqa: F401
from use_hpc_eval import config as C
from use_hpc_eval.selection.s05_rank_select import score


class CriteriaTest(unittest.TestCase):
    def test_llm_topic(self):
        self.assertTrue(C.LLM_TOPIC.search("Are Large Language Models good at fixing bugs?"))
        self.assertTrue(C.LLM_TOPIC.search("Evaluating Qwen on code review"))
        self.assertFalse(C.LLM_TOPIC.search("A study of flaky tests in CI pipelines"))

    def test_non_research_titles(self):
        self.assertTrue(C.EXCLUDE_TITLE.search("Message from the Chairs"))
        self.assertFalse(C.EXCLUDE_TITLE.search("Mining keynote talks"))  # anchored at the start

    def test_github_link_and_normalisation(self):
        m = C.GITHUB_URL.search("code at https://github.com/ISEngLab/RetriGen.git).")
        self.assertEqual(C.norm_repo(*m.groups()), "isenglab/retrigen")

    def test_open_weight_vs_proprietary(self):
        self.assertTrue(C.OPEN_WEIGHT.search("vllm serve Qwen2.5-Coder-7B"))
        self.assertTrue(C.PROPRIETARY.search("client = OpenAI(api_key=...)"))

    def test_rank_score(self):
        r = {"ollama_hits": 1, "open_weight_hits": 3, "readme_run_cmds": 9, "last_commit": "2025-02-01",
             "license": "MIT", "proprietary_hits": 0}
        self.assertEqual(score(r), 10 + 4 + 5 + 2 + 1)
        self.assertEqual(score({**r, "proprietary_hits": 2}), score(r) - 2)
