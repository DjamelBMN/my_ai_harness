# RÔLE DE CE FICHIER :
# Vérifie la découverte de plugins, les décisions d'intention, la délégation
# bornée et une mission multi-agents avec de vrais tools/workspace et des LLM simulés.

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType

from core.agent_registry import AgentRegistry
from core.agent_selector import AgentSelector
from core.agent_loop import AgentLoop
from core.context import Context
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy
from core.planner import Planner
from core.router import ModelRouter
from core.task import Task
from core.task_state import TaskState
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry


class ScriptedProvider(BaseProvider):
    def __init__(self, name: str, turns: list[AgentTurn]) -> None:
        self.name = name
        self.turns = list(turns)
        self.prompts: list[str] = []
        self.schemas: list[list[dict]] = []
        self.received_tool_results: list[list[dict]] = []

    def generate(self, prompt: str = "") -> str:
        return "Réponse de test."

    def execute(self, instruction: str = "") -> str:
        return "Aucune commande provider."

    def get_name(self) -> str:
        return self.name

    def get_model_name(self) -> str:
        return "test-double"

    def get_status_label(self) -> str:
        return "[TEST MOCK]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.prompts.append(prompt or "")
        self.schemas.append(list(tools))
        self.received_tool_results.append(list(tool_results or []))
        if not self.turns:
            raise AssertionError(f"Tour de modèle inattendu pour {self.name}.")
        return self.turns.pop(0)


def tool(name: str, arguments: dict, call_id: str) -> AgentTurn:
    return AgentTurn(tool_calls=[ProviderToolCall(name, arguments, call_id)])


class IntentDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = Planner()

    def test_user_language_maps_to_expected_intents_and_flags(self) -> None:
        cases = {
            "code un programme": ("coding", True, True, True),
            "corrige ce bug": ("coding", True, True, True),
            "lance les tests": ("testing", True, False, True),
            "analyse ce PDF": ("file_analysis", True, False, False),
            "cherche les programmes officiels de Première spé maths": ("research", False, False, False),
            "qu'est-ce qu'un programme informatique ?": ("general_question", False, False, False),
            "vérifie mon code": ("review", False, False, False),
            "crée un sujet de bac blanc de maths Terminale spé": ("exam_creation", False, False, False),
        }
        for request, expected in cases.items():
            with self.subTest(request=request):
                state = self.planner.plan(Task(request))
                self.assertEqual(state.intent, expected[0])
                decision = state.intent_decision
                self.assertEqual(decision["requires_workspace"], expected[1])
                self.assertEqual(decision["requires_modification"], expected[2])
                self.assertEqual(decision["requires_tests"], expected[3])

    def test_ambiguous_python_requests_clarification(self) -> None:
        with self.assertRaisesRegex(ValueError, "ambigue|ambigüe|ambiguë"):
            self.planner.plan(Task("Python"))

    def test_compound_missions_declare_secondaries(self) -> None:
        coding = self.planner.plan(Task("cherche pourquoi mon code plante et corrige-le"))
        self.assertEqual(coding.intent, "coding")
        self.assertEqual(coding.intent_decision["secondary_capabilities"], ["research", "testing"])
        exam = self.planner.plan(
            Task("crée un bac blanc et vérifie qu'il respecte le programme officiel")
        )
        self.assertEqual(exam.intent, "exam_creation")
        self.assertEqual(exam.intent_decision["secondary_capabilities"], ["research", "review"])
        self.assertTrue(exam.intent_decision["requires_web"])


class AgentRegistryTests(unittest.TestCase):
    def test_discovery_and_alias_lookup(self) -> None:
        registry = AgentRegistry.from_package()
        self.assertIsNotNone(registry.get("CodeAgent"))
        self.assertIsNone(registry.get("bac_blanc"))
        self.assertEqual(registry.find_by_capability("exam_creation"), [])
        self.assertEqual(registry.find_by_capability("bac_blanc"), [])

    def test_dynamic_plugin_is_discovered_and_selected_without_router_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-plugin-") as temporary:
            root = Path(temporary)
            (root / "fake_specialized.py").write_text(
                "class FakeSpecializedAgent:\n"
                "    name = 'FakeSpecializedAgent'\n"
                "    capabilities = ['special_test_capability']\n",
                encoding="utf-8",
            )
            (root / "broken_plugin.py").write_text("raise RuntimeError('plugin broken')\n", encoding="utf-8")
            package_name = "harness_plugin_fixture"
            package = ModuleType(package_name)
            package.__path__ = [str(root)]
            package.__package__ = package_name
            sys.modules[package_name] = package
            try:
                registry = AgentRegistry.from_package(package)
                self.assertIsNotNone(registry.get("FakeSpecializedAgent"))
                self.assertIn("broken_plugin", registry.unavailable)
                planner = Planner()
                planner.set_agent_registry(registry)
                task = Task("create special_test_capability")
                state = planner.plan(task)
                selection = AgentSelector(registry).select(task, state)
                self.assertEqual(selection.agent.name, "FakeSpecializedAgent")
                self.assertEqual(selection.agent.routing_key, "fake_specialized")
                provider = ScriptedProvider("DefaultMock", [AgentTurn(text="Plugin exécuté.")])
                router = ModelRouter({"default": provider}, {}, default_provider="default")
                with tempfile.TemporaryDirectory(prefix="agent-plugin-workspace-") as workspace:
                    filesystem = WorkspaceFilesystem(Path(workspace))
                    tools = ToolRegistry(filesystem, PermissionPolicy(autonomous=True))
                    loop = AgentLoop(tools, emit=None, max_retries=0)
                    orchestrator = Orchestrator(registry, router, context=Context())
                    with redirect_stdout(io.StringIO()):
                        result = orchestrator.run_agentic(task, loop)
                self.assertIn("Plugin exécuté", result.answer)
                self.assertEqual(provider.get_model_name(), "test-double")
            finally:
                sys.modules.pop(package_name, None)

    def test_invalid_agent_is_rejected(self) -> None:
        registry = AgentRegistry()
        with self.assertRaises(TypeError):
            registry.register(object())  # type: ignore[arg-type]


class DelegationAndRuntimeTests(unittest.TestCase):
    def test_coordinator_bounds_depth_and_detects_repeated_subtask(self) -> None:
        coordinator = MultiAgentCoordinator(max_delegations=2, max_depth=2)
        parent = TaskState("root mission")
        signature = (("researcher", "root mission"),)
        coordinator.begin(parent, "coder", "implement feature", signature)
        with self.assertRaisesRegex(RuntimeError, "Cycle"):
            coordinator.begin(parent, "coder", "implement feature", signature + (("coder", "implement feature"),))
        child = TaskState("child", delegation_depth=2)
        with self.assertRaisesRegex(RuntimeError, "profondeur"):
            coordinator.begin(child, "tester", "run tests", signature)

    def test_e2e_real_tools_and_generic_multi_agent_handoff(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agentic-e2e-") as temporary:
            root = Path(temporary)
            (root / "reference.md").write_text("Notions à couvrir : fonctions et probabilités.\n", encoding="utf-8")
            (root / "test_sample.py").write_text(
                "import unittest\n"
                "class SmokeTest(unittest.TestCase):\n"
                "    def test_runtime_fixture(self):\n"
                "        self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )

            researcher = ScriptedProvider(
                "ResearchMock",
                [
                    tool("delegate_to_agent", {"agent": "coder", "task": "Résume les implications de la mission pour la conception."}, "r-code"),
                    AgentTurn(text="Le document source a été lu et les agents spécialisés ont contrôlé la mission."),
                ],
            )
            coder = ScriptedProvider(
                "CodeMock",
                [
                    tool("delegate_to_agent", {"agent": "tester", "task": "Lance les tests présents dans le workspace pour cette mission."}, "c-test"),
                    tool("delegate_to_agent", {"agent": "reviewer", "task": "Relis le résultat et signale les défauts ou limites non vérifiés."}, "c-review"),
                    AgentTurn(text="L'analyse de conception est terminée après les contrôles délégués."),
                ],
            )
            tester = ScriptedProvider(
                "TestMock",
                [
                    tool("run_tests", {}, "t-run"),
                    AgentTurn(text="La suite non vide a réussi."),
                ],
            )
            reviewer = ScriptedProvider("ReviewMock", [AgentTurn(text="Aucun défaut additionnel observé dans les éléments transmis.")])

            registry = AgentRegistry.from_package()
            router = ModelRouter(
                providers={"research": researcher, "code": coder, "tests": tester, "review": reviewer},
                agent_provider_map={
                    "researcher": "research",
                    "coder": "code",
                    "tester": "tests",
                    "reviewer": "review",
                },
                default_provider="research",
            )
            filesystem = WorkspaceFilesystem(root)
            tools = ToolRegistry(filesystem, PermissionPolicy(autonomous=True))
            events: list[str] = []
            loop = AgentLoop(tools, emit=events.append, max_iterations=5, max_retries=0)
            orchestrator = Orchestrator(registry, router, context=Context())

            with redirect_stdout(io.StringIO()):
                result = orchestrator.run_agentic(
                    Task(
                        "Analyse reference.md puis examine les notions demandées.",
                        type="researcher",
                        explicit_agent=True,
                    ),
                    loop,
                )

            self.assertEqual(result.status, "verified")
            self.assertIn("reference.md", str(result.observations))
            self.assertTrue(
                any(
                    item.get("kind") == "tool_result"
                    and item.get("tool") == "read_document"
                    and item.get("status") == "success"
                    for item in result.observations
                )
            )
            coordinator_snapshot = next(
                item["subtasks"]
                for item in result.observations
                if item.get("kind") == "multi_agent_coordinator"
            )
            self.assertEqual([item["agent"] for item in coordinator_snapshot], ["coder", "tester", "reviewer"])
            self.assertTrue(
                all(item["status"] in {"answered", "verified", "success"} for item in coordinator_snapshot),
                coordinator_snapshot,
            )
            tester_record = coordinator_snapshot[1]["result"]
            self.assertTrue(
                any(
                    observation.get("tool") == "run_tests"
                    and observation.get("status") == "success"
                    for observation in tester_record["observations"]
                )
            )
            self.assertTrue(any("[DELEGATION]" in event for event in events))
            self.assertIn("delegate_to_agent", [item["name"] for item in coder.schemas[0]])

    def test_code_un_programme_selects_code_agent_and_runs_real_file_tools(self) -> None:
        with tempfile.TemporaryDirectory(prefix="coding-e2e-") as temporary:
            root = Path(temporary)
            (root / "test_sample.py").write_text(
                "import unittest\n"
                "class SmokeTest(unittest.TestCase):\n"
                "    def test_fixture(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            coder = ScriptedProvider(
                "CodeAgentMock",
                [
                    tool("write_file", {"path": "generated.py", "content": "def main():\n    return 2\n"}, "write"),
                    tool("read_file", {"path": "generated.py"}, "read"),
                    tool("run_tests", {}, "tests"),
                    AgentTurn(text="Le module a été écrit, relu et la suite de tests a réussi."),
                ],
            )
            agents = AgentRegistry.from_package()
            router = ModelRouter(
                {"session": coder},
                {key: "session" for key in agents.agents},
                default_provider="session",
            )
            filesystem = WorkspaceFilesystem(root)
            tools = ToolRegistry(filesystem, PermissionPolicy(autonomous=True))
            loop = AgentLoop(tools, emit=None, max_iterations=5, max_retries=0)
            orchestrator = Orchestrator(agents, router, context=Context())
            output = io.StringIO()
            with redirect_stdout(output):
                result = orchestrator.run_agentic(Task("code un programme"), loop)

            self.assertEqual(result.status, "success")
            self.assertTrue((root / "generated.py").is_file())
            self.assertIn("CodeAgent", output.getvalue())
            self.assertIn("[INTENT] coding", output.getvalue())
            self.assertNotIn("[AGENT] ResearchAgent", output.getvalue())
            self.assertEqual(
                [item["name"] for item in coder.schemas[0] if item["name"] != "delegate_to_agent"],
                [
                    "list_files", "find_file", "search_files", "read_file", "read_document",
                    "write_file", "patch_file", "run_tests", "run_python",
                ],
            )
            verification = next(item for item in result.observations if item.get("kind") == "verification")
            self.assertEqual(verification["status"], "passed")


if __name__ == "__main__":
    unittest.main()
