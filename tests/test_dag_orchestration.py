# RÔLE DE CE FICHIER :
# Teste de manière unitaire et intégrée l'orchestration asynchrone en graphe (DAG).
# Valide la détection de cycles, le tri topologique, l'exécution parallèle,
# l'isolation des contextes, la gestion des pannes et la boucle de critique/remédiation.

from __future__ import annotations

import time
import unittest
from typing import Any

from core.dag_engine import (
    AsyncDAGEngine,
    CyclicDAGError,
    DAGNode,
    InvalidDAGError,
    NodeStatus,
    TaskDAG,
)
from core.multi_agent_coordinator import CritiqueRequest, CritiqueVerdict


class TestDAGOrchestration(unittest.TestCase):
    def test_01_dag_validation_and_cycle_detection(self) -> None:
        """Vérifie la validation de structure, le tri topologique et la détection d'interblocage/cycles."""
        dag = TaskDAG(mission_id="mission_01")
        dag.add_node(DAGNode(id="research", agent="researcher", title="Recherche doc", dependencies=[]))
        dag.add_node(DAGNode(id="tests", agent="tester", title="Création tests TDD", dependencies=[]))
        dag.add_node(DAGNode(id="code", agent="coder", title="Écriture code", dependencies=["research"]))
        dag.add_node(DAGNode(id="review", agent="reviewer", title="Revue", dependencies=["code", "tests"]))

        order = dag.topological_sort()
        self.assertEqual(len(order), 4)
        # 'research' et 'tests' doivent précéder 'code' et 'review'
        self.assertLess(order.index("research"), order.index("code"))
        self.assertLess(order.index("code"), order.index("review"))
        self.assertLess(order.index("tests"), order.index("review"))

        # Test dépendance inexistante
        bad_dag = TaskDAG(mission_id="bad_01")
        bad_dag.add_node(DAGNode(id="step_a", agent="coder", title="A", dependencies=["ghost_node"]))
        with self.assertRaises(InvalidDAGError):
            bad_dag.topological_sort()

        # Test cycle direct A -> B -> A
        cycle_dag = TaskDAG(mission_id="cycle_01")
        cycle_dag.add_node(DAGNode(id="node_a", agent="coder", title="A", dependencies=["node_b"]))
        cycle_dag.add_node(DAGNode(id="node_b", agent="tester", title="B", dependencies=["node_a"]))
        with self.assertRaises(CyclicDAGError):
            cycle_dag.topological_sort()

        # Test cycle triangulaire A -> B -> C -> A
        cycle_tri = TaskDAG(mission_id="cycle_02")
        cycle_tri.add_node(DAGNode(id="n1", agent="researcher", title="N1", dependencies=["n3"]))
        cycle_tri.add_node(DAGNode(id="n2", agent="coder", title="N2", dependencies=["n1"]))
        cycle_tri.add_node(DAGNode(id="n3", agent="tester", title="N3", dependencies=["n2"]))
        with self.assertRaises(CyclicDAGError):
            cycle_tri.topological_sort()

    def test_02_parallel_wave_execution(self) -> None:
        """Vérifie que les nœuds indépendants s'exécutent en parallèle, réduisant le temps total."""
        dag = TaskDAG(mission_id="mission_parallel")
        # Nœuds 1 et 2 indépendants qui dorment chacun 0.15s
        dag.add_node(DAGNode(id="n1", agent="researcher", title="Recherche", dependencies=[]))
        dag.add_node(DAGNode(id="n2", agent="tester", title="Tests", dependencies=[]))
        # Nœud 3 dépendant de n1 et n2
        dag.add_node(DAGNode(id="n3", agent="coder", title="Code", dependencies=["n1", "n2"]))

        def slow_worker(ctx: dict[str, Any]) -> dict[str, Any]:
            time.sleep(0.12)
            return {
                "status": "success",
                "summary": f"Fini par {ctx['agent']} pour {ctx['id']}",
                "artifacts": [{"uri": f"out_{ctx['id']}.txt", "sha256": f"hash_{ctx['id']}"}],
            }

        engine = AsyncDAGEngine(max_workers=4)
        start_time = time.monotonic()
        res = engine.execute_dag(
            dag=dag,
            worker_executors={
                "researcher": slow_worker,
                "tester": slow_worker,
                "coder": slow_worker,
            },
        )
        elapsed = time.monotonic() - start_time

        self.assertEqual(res["status"], "success")
        self.assertEqual(dag.nodes["n1"].status, NodeStatus.COMPLETED)
        self.assertEqual(dag.nodes["n2"].status, NodeStatus.COMPLETED)
        self.assertEqual(dag.nodes["n3"].status, NodeStatus.COMPLETED)

        # En séquentiel pur : 0.12 * 3 = 0.36s minimum.
        # En parallèle (n1 et n2 ensemble puis n3) : ~0.24s à 0.30s.
        self.assertLess(elapsed, 0.34, f"L'exécution a pris {elapsed:.3f}s, pas de parallélisation efficace.")

    def test_03_context_isolation_and_artifact_propagation(self) -> None:
        """Vérifie que les contextes sont strictement isolés et que les artefacts des parents sont transmis."""
        dag = TaskDAG(mission_id="mission_context")
        dag.add_node(DAGNode(id="parent_a", agent="researcher", title="Doc", dependencies=[]))
        dag.add_node(DAGNode(id="child_b", agent="coder", title="Impl", dependencies=["parent_a"]))

        received_context: dict[str, Any] = {}

        def parent_exec(ctx: dict[str, Any]) -> dict[str, Any]:
            return {
                "status": "success",
                "summary": "Spécification API",
                "artifacts": [{"uri": "workspace/spec.json", "sha256": "spec123"}],
            }

        def child_exec(ctx: dict[str, Any]) -> dict[str, Any]:
            nonlocal received_context
            received_context = dict(ctx)
            return {"status": "success", "summary": "Code écrit", "artifacts": []}

        engine = AsyncDAGEngine()
        res = engine.execute_dag(
            dag=dag,
            worker_executors={"researcher": parent_exec, "coder": child_exec},
        )

        self.assertEqual(res["status"], "success")
        # Le child_b doit avoir reçu les artefacts de son parent_a
        self.assertIn("input_artifacts", received_context)
        uris = [a["uri"] for a in received_context["input_artifacts"]]
        self.assertIn("workspace/spec.json", uris)
        # Le child_b a son propre ID isolé
        self.assertEqual(received_context["id"], "child_b")

    def test_04_node_failure_and_downstream_blocking(self) -> None:
        """Vérifie qu'un échec sur une branche bloque ses dépendants sans bloquer les branches indépendantes."""
        dag = TaskDAG(mission_id="mission_failure")
        # Branche 1 (échoue)
        dag.add_node(DAGNode(id="fail_a", agent="researcher", title="Fail A", dependencies=[]))
        dag.add_node(DAGNode(id="blocked_b", agent="coder", title="Blocked B", dependencies=["fail_a"]))
        # Branche 2 (indépendante, doit réussir)
        dag.add_node(DAGNode(id="ok_c", agent="tester", title="OK C", dependencies=[]))

        def failing_exec(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"status": "failed", "summary": "Erreur réseau source", "error": "Source introuvable"}

        def ok_exec(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"status": "success", "summary": "Tests rédigés", "artifacts": []}

        engine = AsyncDAGEngine()
        res = engine.execute_dag(
            dag=dag,
            worker_executors={"researcher": failing_exec, "coder": ok_exec, "tester": ok_exec},
        )

        self.assertEqual(res["status"], "partial_failure")
        self.assertEqual(dag.nodes["fail_a"].status, NodeStatus.FAILED)
        self.assertEqual(dag.nodes["blocked_b"].status, NodeStatus.BLOCKED)
        self.assertEqual(dag.nodes["ok_c"].status, NodeStatus.COMPLETED)

    def test_05_critic_verdict_and_targeted_remediation(self) -> None:
        """Vérifie l'évaluation du Critic avec rejet initial, remédiation ciblée et approbation finale."""
        dag = TaskDAG(mission_id="mission_critic", requirements=["Format DOCX conforme", "Maths vérifiées"])
        dag.add_node(DAGNode(id="code_task", agent="coder", title="Code exercice", dependencies=[]))

        attempts = 0

        def coder_exec(ctx: dict[str, Any]) -> dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return {
                    "status": "success",
                    "summary": "Première version avec coquille dans la formule",
                    "artifacts": [{"uri": "workspace/doc.docx", "sha256": "v1"}],
                }
            return {
                "status": "success",
                "summary": "Version corrigée : racine carrée correctement simplifiée",
                "artifacts": [{"uri": "workspace/doc.docx", "sha256": "v2_fixed"}],
            }

        def critic_eval(req: CritiqueRequest) -> CritiqueVerdict:
            if "v1" in [a.get("sha256") for a in req.artifacts]:
                return CritiqueVerdict(
                    decision="REJECT",
                    defects=["Erreur de signe dans le développement de l'identité remarquable."],
                    confidence=0.95,
                    remediation_suggestions=["Corriger (a-b)^2 = a^2 - 2ab + b^2"],
                )
            return CritiqueVerdict(decision="APPROVE", defects=[], confidence=1.0)

        engine = AsyncDAGEngine()
        res = engine.execute_dag(
            dag=dag,
            worker_executors={"coder": coder_exec},
            critic_evaluator=critic_eval,
            max_remediation_rounds=2,
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["verdict"]["decision"], "APPROVE")
        self.assertEqual(res["remediation_rounds"], 1)
        self.assertEqual(attempts, 2)

    def test_06_event_sink_notifications(self) -> None:
        """Vérifie la diffusion des événements d'avancement pour l'UI Cockpit."""
        dag = TaskDAG(mission_id="mission_events")
        dag.add_node(DAGNode(id="n1", agent="researcher", title="Recherche", dependencies=[]))

        events: list[dict[str, Any]] = []

        def sink(event_name: str, payload: dict[str, Any]) -> None:
            events.append({"event": event_name, **payload})

        def simple_worker(ctx: dict[str, Any]) -> dict[str, Any]:
            return {"status": "success", "summary": "OK"}

        engine = AsyncDAGEngine(event_sink=sink)
        engine.execute_dag(dag=dag, worker_executors={"researcher": simple_worker})

        event_names = [e["event"] for e in events]
        self.assertIn("dag.started", event_names)
        self.assertIn("dag.node_started", event_names)
        self.assertIn("dag.node_completed", event_names)
        self.assertIn("dag.completed", event_names)

    def test_07_delegation_engine_dag_tool(self) -> None:
        """Vérifie que DelegationEngine expose le schéma execute_dag et l'exécute avec succès."""
        from core.agent_registry import AgentRegistry
        from core.agent_selector import AgentSelector
        from core.delegation import DelegationEngine
        from core.multi_agent_coordinator import MultiAgentCoordinator
        from core.task_state import TaskState, AgentResult
        from agents.coder import CodeAgent
        from agents.researcher import ResearchAgent

        registry = AgentRegistry()
        coder = CodeAgent()
        researcher = ResearchAgent()
        registry.register(coder, key="coder")
        registry.register(researcher, key="researcher")

        selector = AgentSelector(registry)

        class MockLoop:
            def __init__(self):
                self.planner = type("MockPlanner", (), {"plan": lambda s, t: TaskState(user_request=t.description)})()
                self.event_sink = None

            def run(self, agent, task, state=None, delegation_stack=()):
                return AgentResult(status="completed", answer=f"Résultat pour {agent.name}", summary="OK")

        class MockRouter:
            def get_provider(self, *args, **kwargs):
                return None

        loop = MockLoop()
        coordinator = MultiAgentCoordinator()
        delegation = DelegationEngine(registry, selector, MockRouter(), loop, coordinator)

        # Vérification du schéma
        schema = delegation.dag_schema()
        self.assertEqual(schema["name"], "execute_dag")
        self.assertIn("nodes", schema["parameters"]["properties"])

        # Exécution du DAG via l'outil
        state = TaskState(user_request="Mission DAG")
        res = delegation.execute(
            parent_agent=researcher,
            parent_state=state,
            arguments={
                "nodes": [
                    {"id": "doc", "agent": "researcher", "title": "Doc", "prompt": "Rechercher", "dependencies": []},
                    {"id": "impl", "agent": "coder", "title": "Impl", "prompt": "Coder", "dependencies": ["doc"]},
                ]
            },
            stack=(),
            tool_name="execute_dag",
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.tool, "execute_dag")
        self.assertEqual(res.data["status"], "success")
        self.assertEqual(len(res.data["dag"]["nodes"]), 2)


if __name__ == "__main__":
    unittest.main()
