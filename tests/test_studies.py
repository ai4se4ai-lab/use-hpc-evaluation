import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from tests import _path  # noqa: F401
from use_hpc_eval import config as C

spec = importlib.util.spec_from_file_location("compare_lib", C.COMMON / "compare_lib.py")
compare_lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare_lib)


class StudyConfigsTest(unittest.TestCase):
    def test_every_selected_artifact_has_a_configuration(self):
        selected = {r["repo"].replace("/", "__") for r in csv.DictReader((C.DATA / "selected.csv").open())}
        configured = {p.name for p in C.CONFIGS.iterdir() if p.is_dir()}
        self.assertEqual(selected, configured)

    def test_configurations_are_complete(self):
        for d in C.CONFIGS.iterdir():
            with self.subTest(artifact=d.name):
                graph = json.loads((d / "experiments.json").read_text())
                self.assertTrue(graph["stages"])
                for f in ("compare.py", "reported.csv", "requirements.txt"):
                    self.assertTrue((d / f).exists(), f)
                hooks = d / "hooks.txt"
                if hooks.exists():
                    for line in hooks.read_text().split("\n"):
                        if line.strip():
                            self.assertTrue((C.COMMON / f"{line.split()[1]}.sh").exists(), line)

    def test_probe_specs_parse(self):
        for p in C.PROBES.glob("*.json"):
            with self.subTest(probe=p.name):
                spec = json.loads(p.read_text())
                self.assertTrue(spec["entry_points"])


class CompareLibTest(unittest.TestCase):
    def test_statuses(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            rep = td / "reported.csv"
            rep.write_text("key,metric,reported,tolerance,source,comparable\n"
                           "a,pass@1,40.0,2,T1,yes\n"
                           "b,pass@1,40.0,2,T1,yes\n"
                           "c,pass@1,40.0,,T1,yes\n"
                           "d,pass@1,40.0,,T1,evaluation code missing\n")
            measured = [{"key": "a", "metric": "pass@1", "measured": "41.5"},
                        {"key": "b", "metric": "pass@1", "measured": "35.0"}]
            rows = {r["key"]: r["status"] for r in compare_lib.compare(td, rep, measured)}
            self.assertEqual(rows, {"a": "reproduced", "b": "deviates", "c": "missing", "d": "not_comparable"})
            self.assertTrue((td / "compare" / "comparison.csv").exists())
