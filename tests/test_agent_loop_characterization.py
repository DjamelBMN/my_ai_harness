# tests/test_agent_loop_characterization.py
# RÔLE : Tests de caractérisation stricts de l'AgentLoop avec un provider simulé
# Couvre la Phase 0.B : tour avec outil, réponse finale, vérification corrigée,
# limites d'itérations et d'outils, arrêt utilisateur, délégation, réponse partielle.

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from agents.coder import CodeAgent
from agents.researcher import ResearchAgent
from core.agent_loop import AgentLoop
from core.agent_registry import AgentRegistry
from core.agent_selector import AgentSelector
from core.delegation import DelegationEngine
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.permissions import PermissionPolicy
from core.planner import Planner
from core.task import Task
from core.task_state import TaskStatus
from core.verifier import Verifier
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry


class CharacterizationProbeProvider(BaseProvider):
    """Fournisseur de test déterministe préprogrammé avec une liste de tours."""

    def __init__(self, name: str = "CharacterizationProbe", turns: list[AgentTurn] | None = None) -> None:
        self.name = name
        self.turns: list[AgentTurn] = list(turns or [])
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str = "") -> str:
        return "probe text"

    def execute(self, instruction: str = "") -> str:
        return "No execution"

    def get_name(self) -> str:
        return self.name

    def get_model_name(self) -> str:
        return "probe-v1"

    def get_status_label(self) -> str:
        return "[TEST PROBE]"

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        self.calls.append({
            "prompt": prompt,
            "tools": tools,
            "continuation": continuation,
            "tool_results": tool_results or [],
        })
        if not self.turns:
            raise AssertionError(f"Tour inattendu : aucun tour restant dans {self.name} ({len(self.calls)} tours déjà reçus)")
        return self.turns.pop(0)


class AgentLoopCharacterizationTests(unittest.TestCase):
    """Tests de caractérisation sans appel réseau ni mock excessif."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_path = Path(self.temp_dir.name)
        self.fs = WorkspaceFilesystem(self.workspace_path)
        self.policy = PermissionPolicy(autonomous=True)
        self.tools = ToolRegistry(filesystem=self.fs, permissions=self.policy)
        self.planner = Planner()
        self.verifier = Verifier()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_tool_call_and_observation_feeding(self) -> None:
        """1. Tour avec outil : l'outil s'exécute et son résultat observable est transmis au tour suivant."""
        self.fs.write_file("hello.txt", "Contenu de test")
        turns = [
            # Tour 1 : appel de read_file
            AgentTurn(
                text="Je vais lire le fichier.",
                tool_calls=[ProviderToolCall(name="read_file", arguments={"path": "hello.txt"}, call_id="c1")],
            ),
            # Tour 2 : réponse finale basée sur l'observation
            AgentTurn(text="Le fichier contient : Contenu de test.", tool_calls=[]),
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = ResearchAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, emit=None)

        task = Task("lis le fichier hello.txt et dis ce qu'il contient", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertIn("Contenu de test", result.answer)
        self.assertEqual(len(provider.calls), 2)
        # Vérifier que le résultat d'outil a été passé au tour 2
        call_2 = provider.calls[1]
        self.assertEqual(len(call_2["tool_results"]), 1)
        self.assertEqual(call_2["tool_results"][0]["name"], "read_file")
        self.assertEqual(call_2["tool_results"][0]["status"], "success")

    def test_02_direct_final_answer(self) -> None:
        """2. Réponse finale directe sans appel d'outil."""
        turns = [
            AgentTurn(text="La réponse est 42.", tool_calls=[]),
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = ResearchAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, emit=None)

        task = Task("quelle est la réponse universelle ?", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertIn("42", result.answer)
        self.assertEqual(len(provider.calls), 1)

    def test_03_verification_failure_and_repair(self) -> None:
        """3. Vérification échouée puis corrigée : échec sur tour 1 via validate_final_answer, repair prompt, puis réussite."""
        class ValidatedAgent(ResearchAgent):
            def validate_final_answer(self, final_answer, task, state, filesystem):
                if "2026" not in final_answer:
                    return {"required": True, "complete": False, "missing": ["mentionner l'année 2026"]}
                return {"required": True, "complete": True, "checks": [{"check": "year_check", "status": "passed"}]}

            def completion_repair_prompt(self, report):
                return "Ajoute impérativement l'année 2026 dans ta réponse."

        turns = [
            # Tour 1 : réponse sans l'année requise (rejetée par le validateur)
            AgentTurn(text="Voici la réponse sans année.", tool_calls=[]),
            # Tour 2 : suite au prompt de réparation, réponse complétée
            AgentTurn(text="Voici la réponse conforme datée de 2026.", tool_calls=[]),
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = ValidatedAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, max_retries=2, emit=None)

        task = Task("donne les informations officielles", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertIn(result.status, {"answered", "verified", "success"})
        self.assertIn("2026", result.answer)
        self.assertEqual(len(provider.calls), 2)

    def test_04_iteration_limit_exhaustion(self) -> None:
        """4. Limite d'itérations atteinte : arrêt propre, rapport d'épuisement sans boucle infinie."""
        turns = [
            AgentTurn(text="Étape", tool_calls=[ProviderToolCall(name="list_files", arguments={}, call_id=f"c_{i}")])
            for i in range(10)
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = ResearchAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=3, emit=None)

        task = Task("explore tout indéfiniment", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertEqual(result.status, "failed")
        self.assertIn("limite de 3 tours", result.summary)

    def test_05_max_tool_calls_limit(self) -> None:
        """5. Limite d'appels d'outils atteinte : arrêt propre en BLOCKED/failed."""
        turns = [
            AgentTurn(
                text="Beaucoup d'appels",
                tool_calls=[
                    ProviderToolCall(name="list_files", arguments={}, call_id="c1"),
                    ProviderToolCall(name="list_files", arguments={}, call_id="c2"),
                    ProviderToolCall(name="list_files", arguments={}, call_id="c3"),
                ],
            ),
            AgentTurn(
                text="Encore un appel",
                tool_calls=[ProviderToolCall(name="list_files", arguments={}, call_id="c4")],
            ),
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = ResearchAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, max_tool_calls=2, emit=None)

        task = Task("liste les fichiers", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertEqual(result.status, "failed")
        self.assertIn("limite d'appels d'outils", result.summary.lower())

    def test_06_user_stop_request(self) -> None:
        """6. Arrêt utilisateur : _stop_requested interrompt immédiatement l'exécution."""
        provider = CharacterizationProbeProvider(turns=[])
        agent = ResearchAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, emit=None)
        setattr(loop, "_stop_requested", True)

        task = Task("mission annulée", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertEqual(result.status, "failed")
        self.assertTrue(
            any(word in result.answer.lower() for word in ("arrêtée", "interrompue", "arrêtee")),
            f"Message d'interruption attendu : {result.answer}",
        )
        self.assertEqual(len(provider.calls), 0)

    def test_07_delegation_execution(self) -> None:
        """7. Délégation : un tour délègue à un sous-agent via DelegationEngine."""
        parent_turns = [
            AgentTurn(
                text="Je délègue à ResearchAgent.",
                tool_calls=[ProviderToolCall(name="delegate_to_agent", arguments={"agent": "researcher", "task": "trouve la date"}, call_id="del1")],
            ),
            AgentTurn(text="Reçu du sous-agent : Mission fille accomplie.", tool_calls=[]),
        ]
        child_turns = [
            AgentTurn(text="Voici la réponse déléguée : 2026.", tool_calls=[]),
        ]
        parent_prov = CharacterizationProbeProvider(name="ParentProbe", turns=parent_turns)
        child_prov = CharacterizationProbeProvider(name="ChildProbe", turns=child_turns)

        registry = AgentRegistry.from_package()
        selector = AgentSelector(registry)
        coordinator = MultiAgentCoordinator()

        class MockRouter:
            def get_provider(self, *args, **kwargs):
                return child_prov

        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=5, emit=None)
        engine = DelegationEngine(
            registry=registry,
            selector=selector,
            router=MockRouter(),
            agent_loop=loop,
            coordinator=coordinator,
        )
        loop.delegation_engine = engine

        parent_agent = CodeAgent()
        parent_agent.set_provider(parent_prov)
        task = Task("coordonne la recherche", mode="ACCEPT")
        result = loop.run(parent_agent, task)

        self.assertIn("Mission fille", result.answer)
        self.assertEqual(len(parent_prov.calls), 2)
        self.assertEqual(len(child_prov.calls), 1)

    def test_08_partial_delivery_on_failure(self) -> None:
        """8. Réponse partielle : si l'agent active partial_delivery_on_failure, un résultat provisoire est retourné."""
        class PartialAgent(ResearchAgent):
            def __init__(self):
                super().__init__()
                self.skill_config = {"partial_delivery_on_failure": True}

            def partial_delivery_message(self, reason, partial_content, state, filesystem):
                return f"[PARTIEL] {partial_content} (Raison : {reason})"

        turns = [
            AgentTurn(text="Calcul partiel 50%", partial=True, tool_calls=[]),
        ]
        provider = CharacterizationProbeProvider(turns=turns)
        agent = PartialAgent()
        agent.set_provider(provider)
        loop = AgentLoop(tools=self.tools, planner=self.planner, verifier=self.verifier, max_iterations=1, emit=None)

        task = Task("calcul long", mode="ACCEPT")
        result = loop.run(agent, task)

        self.assertEqual(result.status, "incomplete")
        self.assertIn("[PARTIEL]", result.answer)
        self.assertIn("Calcul partiel 50%", result.answer)


if __name__ == "__main__":
    unittest.main()
