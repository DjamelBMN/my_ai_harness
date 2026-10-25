from __future__ import annotations

import unittest
from typing import Any

from core.multi_agent_coordinator import (
    CritiqueRequest,
    CritiqueVerdict,
    CyclicDelegationError,
    HierarchicalCoordinator,
    MaxDepthExceededError,
    MultiAgentCoordinator,
    TaskAssignment,
    TaskCompletion,
)
from core.task_state import TaskState


class TestMultiAgentHierarchy(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = HierarchicalCoordinator(max_depth=3)

    def test_01_manager_to_workers_to_critic_success(self) -> None:
        """Mission Manager -> 2 Workers (Coder, Tester) -> Critic avec succès."""
        # 1. Sous-tâches définies par le Manager
        assignments = [
            TaskAssignment(
                task_id="subtask-coder-01",
                parent_task_id="manager-root",
                assigned_to="coder",
                instructions="Créer la fonction calculate_metrics() dans metrics.py",
                input_artifacts=[],
            ),
            TaskAssignment(
                task_id="subtask-tester-01",
                parent_task_id="manager-root",
                assigned_to="tester",
                instructions="Tester la conformité de calculate_metrics()",
                input_artifacts=[{"uri": "workspace/metrics.py", "sha256": "abc123hash"}],
            ),
        ]

        # 2. Exécuteurs simulés de Workers
        def coder_exec(ctx: dict[str, Any]) -> TaskCompletion:
            return TaskCompletion(
                task_id=ctx["task_id"],
                status="success",
                output_artifacts=[{"uri": "workspace/metrics.py", "sha256": "abc123hash"}],
                summary="Code de calculate_metrics implémenté avec succès.",
            )

        def tester_exec(ctx: dict[str, Any]) -> TaskCompletion:
            return TaskCompletion(
                task_id=ctx["task_id"],
                status="success",
                output_artifacts=[{"uri": "workspace/test_metrics.py", "sha256": "test456hash"}],
                summary="Tous les tests unitaires sont passés (3/3 verts).",
            )

        # 3. Évaluateur Critic indépendant
        def critic_eval(req: CritiqueRequest) -> CritiqueVerdict:
            return CritiqueVerdict(
                decision="APPROVE",
                defects=[],
                confidence=1.0,
                remediation_suggestions=[],
            )

        res = self.coordinator.execute_hierarchy(
            manager_id="manager-root",
            assignments=assignments,
            worker_executors={"coder": coder_exec, "tester": tester_exec},
            critic_evaluator=critic_eval,
            requirements=["Implémenter metrics", "Valider tests"],
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["verdict"]["decision"], "APPROVE")
        self.assertEqual(len(res["artifacts"]), 2)
        self.assertEqual(res["remediation_rounds"], 0)

    def test_02_critic_rejection_and_remediation_loop(self) -> None:
        """Rejet initial par le Critic -> réassignation au Worker avec feedback -> approbation."""
        attempts = 0

        assignments = [
            TaskAssignment(
                task_id="subtask-coder-02",
                parent_task_id="manager-root",
                assigned_to="coder",
                instructions="Implémenter le parsing CSV dans parser.py",
            )
        ]

        def coder_exec(ctx: dict[str, Any]) -> TaskCompletion:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return TaskCompletion(
                    task_id=ctx["task_id"],
                    status="success",
                    output_artifacts=[{"uri": "workspace/parser.py", "sha256": "v1"}],
                    summary="Parsing naïf implémenté.",
                )
            else:
                # Après feedback du critic
                self.assertIn("CORRECTIONS EXIGÉES PAR LE CRITIC", ctx["instructions"])
                return TaskCompletion(
                    task_id=ctx["task_id"],
                    status="success",
                    output_artifacts=[{"uri": "workspace/parser.py", "sha256": "v2"}],
                    summary="Parsing conforme gérant les délimiteurs complexes et quotes.",
                )

        def critic_eval(req: CritiqueRequest) -> CritiqueVerdict:
            if attempts == 1:
                return CritiqueVerdict(
                    decision="REJECT",
                    defects=["Gestion des guillemets absente dans le parser CSV."],
                    confidence=0.9,
                    remediation_suggestions=["Utiliser le module standard csv.reader"],
                )
            return CritiqueVerdict(
                decision="APPROVE",
                defects=[],
                confidence=1.0,
            )

        res = self.coordinator.execute_hierarchy(
            manager_id="manager-root",
            assignments=assignments,
            worker_executors={"coder": coder_exec},
            critic_evaluator=critic_eval,
            requirements=["Parser CSV robuste"],
            max_remediation_rounds=2,
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["verdict"]["decision"], "APPROVE")
        self.assertEqual(res["remediation_rounds"], 1)
        self.assertEqual(attempts, 2)

    def test_03_cyclic_delegation_cut(self) -> None:
        """Détection et coupure nette d'une boucle de délégation cyclique (A -> B -> A)."""
        coord = MultiAgentCoordinator(max_depth=3)
        parent_state = TaskState(
            user_request="Mission principale",
            mode="ACCEPT",
            intent="coding",
            task_id="t-root",
        )

        # 1. Délégation de manager vers coder (autorisée)
        stack1 = (("manager", "créer un module"),)
        rec1 = coord.begin(parent_state, "coder", "écrire le code", stack1)
        self.assertTrue(rec1.task_id)

        # 2. Coder tente de déléguer à reviewer (autorisée)
        stack2 = (("manager", "créer un module"), ("coder", "écrire le code"))
        rec2 = coord.begin(parent_state, "reviewer", "relire le code", stack2)
        self.assertTrue(rec2.task_id)

        # 3. Reviewer tente de redéléguer à coder -> CYCLE DÉTECTÉ
        stack3 = (
            ("manager", "créer un module"),
            ("coder", "écrire le code"),
            ("reviewer", "relire le code"),
        )
        with self.assertRaises(CyclicDelegationError):
            coord.begin(parent_state, "coder", "réécrire le code", stack3)

    def test_04_worker_context_strict_isolation(self) -> None:
        """Isolation stricte des contextes de workers (Worker B ne voit pas les données internes de Worker A)."""
        # Worker A a des données internes privées
        worker_a_assignment = TaskAssignment(
            task_id="t-worker-a",
            parent_task_id="manager-root",
            assigned_to="researcher",
            instructions="Rechercher les spécifications de l'API",
        )
        worker_a_internal_state = {
            "private_tokens": "secret_api_key_12345",
            "scratchpad": "Tentatives privées non publiées...",
        }

        # Création du contexte pour Worker B
        worker_b_assignment = TaskAssignment(
            task_id="t-worker-b",
            parent_task_id="manager-root",
            assigned_to="coder",
            instructions="Coder le client API",
            input_artifacts=[{"uri": "specs/api.json", "sha256": "hash999"}],
        )
        isolated_b_ctx = HierarchicalCoordinator.create_isolated_worker_context(worker_b_assignment)

        # Vérification d'étanchéité stricte
        self.assertNotIn("secret_api_key_12345", str(isolated_b_ctx))
        self.assertNotIn("scratchpad", isolated_b_ctx)
        self.assertEqual(len(isolated_b_ctx["input_artifacts"]), 1)
        self.assertEqual(isolated_b_ctx["input_artifacts"][0]["uri"], "specs/api.json")


if __name__ == "__main__":
    unittest.main()
