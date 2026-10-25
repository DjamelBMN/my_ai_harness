import unittest
import tempfile
from pathlib import Path
from evals.tasks import EvalTask
from evals.runner import run_single_eval, run_eval_suite
from tests.test_phase0c_sanitization import FakeProbeProvider
from providers.base_provider import AgentTurn
from tools.registry import ToolCall


class TestEvalsRunner(unittest.TestCase):
    def test_run_single_eval_with_mock_provider(self):
        task = EvalTask(
            id="test-task-calc",
            category="code_simple",
            prompt="Crée calc.py avec add(a, b)",
            description="Test calculatrice",
            expected_files=["calc.py"],
        )

        turns = [
            AgentTurn(
                text="Écriture du fichier",
                tool_calls=[
                    ToolCall("write_file", {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}, call_id="c1")
                ]
            ),
            AgentTurn(text="Fichier calc.py créé avec succès.", tool_calls=[])
        ]
        provider = FakeProbeProvider(turns)

        res = run_single_eval(task, default_provider=provider)
        self.assertTrue(res["success"])
        self.assertEqual(res["id"], "test-task-calc")
        self.assertGreaterEqual(res["tools_count"], 1)

    def test_run_eval_suite_small(self):
        tasks = [
            EvalTask(
                id="small-01",
                category="code_simple",
                prompt="Fichier simple",
                description="Test suite",
                expected_files=["f.txt"],
            )
        ]
        turns = [
            AgentTurn(
                text="Écriture de f.txt",
                tool_calls=[ToolCall("write_file", {"path": "f.txt", "content": "ok"}, call_id="c1")]
            ),
            AgentTurn(text="Fait", tool_calls=[])
        ]
        provider = FakeProbeProvider(turns)

        summary = run_eval_suite(tasks=tasks, provider=provider)
        self.assertEqual(summary["total_tasks"], 1)
        self.assertEqual(summary["passed_tasks"], 1)
        self.assertEqual(summary["success_rate_percent"], 100.0)
        self.assertTrue(Path("evals/results.json").exists())
        self.assertTrue(Path("evals/BASELINE.md").exists())


if __name__ == "__main__":
    unittest.main()
