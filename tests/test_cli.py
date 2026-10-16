import importlib
import io
import unittest
from contextlib import redirect_stdout

from tests import _path  # noqa: F401
from use_hpc_eval import cli


class CliTest(unittest.TestCase):
    def test_every_command_module_imports_and_has_main(self):
        for name, step in cli.COMMANDS.items():
            with self.subTest(command=name):
                mod = importlib.import_module(f"use_hpc_eval.{step.module}")
                self.assertTrue(callable(getattr(mod, "main", None)))

    def test_list_and_unknown_command(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(cli.main(["list"]), 0)
            self.assertEqual(cli.main(["no-such-step"]), 2)
        self.assertIn("find-repos", buf.getvalue())

    def test_step_numbers_are_unique(self):
        nums = [s.step for s in cli.COMMANDS.values() if s.step != "--"]
        self.assertEqual(len(nums), len(set(nums)))
