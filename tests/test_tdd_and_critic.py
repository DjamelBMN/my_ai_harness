import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from core.tdd_engine import TDDEngine, TestTamperingError
from agents.reviewer import IndependentCritic, ReviewAgent
from tools.filesystem import WorkspaceFilesystem


class TestTDDAndCritic(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fs = WorkspaceFilesystem(self.temp_dir.name)
        self.tdd = TDDEngine(self.fs, max_iterations=3)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- 1. Cycle RED -> GREEN normal ---
    def test_01_full_cycle_red_to_green(self):
        """Cycle TDD nominal : RED d'abord, puis GREEN."""
        test_rel = "test_calc.py"
        test_abs = self.fs.resolve(test_rel)
        test_abs.write_text("import unittest\nclass T(unittest.TestCase):\n  def test_a(self): self.assertEqual(1, 2)\n", encoding="utf-8")

        # 1. Validation RED
        red_ok, msg_red = self.tdd.validate_red_phase(
            test_rel,
            run_test_fn=lambda: {"status": "failed", "returncode": 1}
        )
        self.assertTrue(red_ok)
        self.assertEqual(self.tdd.active_cycles[test_rel].phase, "GREEN")

        # 2. Validation GREEN (le code est écrit, les tests passent)
        code_abs = self.fs.resolve("calc.py")
        code_abs.write_text("def add(a, b): return a + b\n", encoding="utf-8")

        green_ok, msg_green = self.tdd.validate_green_phase(
            test_rel,
            run_test_fn=lambda: {"status": "success", "returncode": 0}
        )
        self.assertTrue(green_ok)
        self.assertEqual(self.tdd.active_cycles[test_rel].phase, "REVIEW")

    # --- 2. Détection de triche (TestTamperingError) ---
    def test_02_test_tampering_is_blocked(self):
        """Si le codeur modifie le test pour le rendre vert sans coder, alerte levée."""
        test_rel = "test_auth.py"
        test_abs = self.fs.resolve(test_rel)
        test_abs.write_text("assert authenticate('admin', 'wrong_pass') is False\n", encoding="utf-8")

        # Enregistrement initial
        self.tdd.register_test_file(test_rel)

        # Le codeur triche en modifiant le test
        test_abs.write_text("assert True\n", encoding="utf-8")

        # La vérification doit lever TestTamperingError
        with self.assertRaises(TestTamperingError) as ctx:
            self.tdd.validate_green_phase(
                test_rel,
                run_test_fn=lambda: {"status": "success", "returncode": 0}
            )

        self.assertIn("Altération frauduleuse", str(ctx.exception))

    # --- 3. Critic Indépendant : Contexte vierge et feedback loop ---
    def test_03_critic_virgin_context_approve(self):
        """Critic approuve un diff propre et des tests passants."""
        critic = IndependentCritic()
        verdict = critic.evaluate(
            task_description="Implémenter l'addition",
            code_diff="+ def add(a, b): return a + b",
            test_output="Ran 1 test in 0.001s\nOK",
        )
        self.assertTrue(verdict.is_approved)
        self.assertEqual(verdict.decision, "APPROVE")
        self.assertEqual(len(verdict.defects), 0)

    def test_04_critic_rejects_and_provides_feedback_on_failing_tests(self):
        """Critic rejette si les tests échouent et fournit les défauts."""
        critic = IndependentCritic()
        verdict = critic.evaluate(
            task_description="Implémenter la division sécurisée",
            code_diff="+ def div(a, b): return a / b",
            test_output="FAIL: test_zero_div\nZeroDivisionError: division by zero",
            roundtrip=1,
        )
        self.assertFalse(verdict.is_approved)
        self.assertEqual(verdict.decision, "REJECT")
        self.assertGreater(len(verdict.defects), 0)

    def test_05_critic_with_mock_llm_provider(self):
        """Critic interagit correctement avec un provider LLM dédié."""
        mock_provider = MagicMock()
        mock_provider.generate.return_value = "VERDICT: REJECT\n- Cas de liste vide non géré\n- Risque d'IndexError"

        critic = IndependentCritic(provider=mock_provider)
        verdict = critic.evaluate(
            task_description="Calcul de la médiane",
            code_diff="+ def median(arr): return arr[len(arr)//2]",
            test_output="OK",
        )
        self.assertFalse(verdict.is_approved)
        self.assertEqual(verdict.decision, "REJECT")
        self.assertEqual(len(verdict.defects), 2)
        self.assertIn("Cas de liste vide non géré", verdict.defects[0])


if __name__ == "__main__":
    unittest.main()
