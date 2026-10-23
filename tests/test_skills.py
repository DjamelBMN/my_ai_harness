# RÔLE DE CE FICHIER :
# Vérifie le parsing prioritaire des slash commands, l'auto-découverte et le
# lancement du Skill BacBlanc avec son agent, sans casser les entrées historiques.

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import main
from core.agent_loop import AgentLoop
from core.agent_registry import AgentRegistry
from core.context import Context
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy
from core.planner import Planner
from core.router import ModelRouter
from core.task import Task
from providers.base_provider import AgentTurn, BaseProvider
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from skills.router import SkillCommandError, SkillRouter
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry


class SkillProbeProvider(BaseProvider):
    def __init__(self, turn: AgentTurn) -> None:
        self.turn = turn
        self.prompts: list[str] = []
        self.schemas: list[list[dict]] = []

    def generate(self, prompt: str = "") -> str:
        return self.turn.text

    def execute(self, instruction: str = "") -> str:
        return "No command execution."

    def get_name(self) -> str:
        return "SkillProbeProvider"

    def get_model_name(self) -> str:
        return "skill-test-model"

    def get_status_label(self) -> str:
        return "[TEST MOCK]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.prompts.append(prompt or "")
        self.schemas.append(list(tools))
        return self.turn


class SkillCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.skills_root = cls.project_root / "skills"

    def make_router(self, root: Path | None = None) -> SkillRouter:
        skills_root = root or self.skills_root
        registry = SkillRegistry.from_directory(skills_root)
        return SkillRouter(registry, SkillLoader(skills_root))

    def test_bacblanc_without_mission_is_detected(self) -> None:
        launch = self.make_router().resolve("/bacblanc")
        self.assertIsNotNone(launch)
        self.assertEqual(launch.command.name, "bacblanc")
        self.assertEqual(launch.command.mission, "")
        self.assertEqual(launch.skill.name, "bacblanc")
        self.assertEqual(launch.skill.agent.name, "BacBlancAgent")

    def test_slash_command_splits_skill_and_mission(self) -> None:
        launch = self.make_router().resolve("/bacblanc suite fonction espace")
        self.assertIsNotNone(launch)
        self.assertEqual(launch.command.name, "bacblanc")
        self.assertEqual(launch.command.mission, "suite fonction espace")
        self.assertEqual(launch.skill.agent.name, "BacBlancAgent")
        self.assertIn("durée", launch.skill.instructions.casefold())
        self.assertIn("barème", launch.skill.instructions.casefold())
        self.assertEqual(launch.skill.rag_resources, [])
        self.assertEqual(launch.skill.available_templates, [])

    def test_unknown_slash_skill_is_explicit_error(self) -> None:
        with self.assertRaises(SkillCommandError) as caught:
            self.make_router().resolve("/skill_inexistant test")
        self.assertIn("Skill '/skill_inexistant' introuvable", str(caught.exception))
        self.assertIn("/bacblanc", str(caught.exception))

    def test_skill_md_directory_is_auto_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skills-discovery-") as temporary:
            root = Path(temporary)
            skill_dir = root / "test_skill"
            skill_dir.mkdir()
            (skill_dir / "skill.md").write_text("# Test skill\nTest instructions.\n", encoding="utf-8")
            registry = SkillRegistry.from_directory(root)
            self.assertEqual(registry.names, ["test_skill"])
            launch = SkillRouter(registry, SkillLoader(root)).resolve("/test_skill test mission")
            self.assertEqual(launch.skill.name, "test_skill")
            self.assertIsNone(launch.skill.agent)

    def test_invalid_skill_configuration_reports_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="skills-invalid-") as temporary:
            root = Path(temporary)
            skill_dir = root / "broken_skill"
            skill_dir.mkdir()
            (skill_dir / "skill.md").write_text("# Broken skill\n", encoding="utf-8")
            (skill_dir / "config.yaml").write_text("name: [invalid\n", encoding="utf-8")
            router = SkillRouter(
                SkillRegistry.from_directory(root),
                SkillLoader(root),
            )
            with self.assertRaises(SkillCommandError) as caught:
                router.resolve("/broken_skill test")
            self.assertIn("Impossible de charger /broken_skill", str(caught.exception))

    def test_legacy_agent_prefix_and_normal_query_still_use_planner(self) -> None:
        known = set(AgentRegistry.from_package().agents)
        explicit = main.creer_tache("researcher: analyse ceci", known_agents=known)
        self.assertEqual(explicit.type, "researcher")
        self.assertTrue(explicit.explicit_agent)
        normal = main.creer_tache("explique-moi les suites", known_agents=known)
        state = Planner().plan(normal)
        self.assertEqual(state.intent, "general_question")
        self.assertEqual(state.assigned_agent, "researcher")

        provider = SkillProbeProvider(AgentTurn(text="Analyse reçue."))
        agents = AgentRegistry.from_package()
        model_router = ModelRouter(
            {"session": provider},
            {agent.routing_key: "session" for agent in agents.list_agents()},
            default_provider="session",
        )
        with tempfile.TemporaryDirectory(prefix="legacy-workspace-") as temporary:
            loop = AgentLoop(
                ToolRegistry(
                    WorkspaceFilesystem(Path(temporary)),
                    PermissionPolicy(autonomous=True),
                ),
                emit=None,
                max_retries=0,
            )
            orchestrator = Orchestrator(agents, model_router, context=Context())
            orchestrator.skill_router = self.make_router()
            with redirect_stdout(io.StringIO()):
                main._executer_mission(
                    orchestrator,
                    loop,
                    "researcher: analyse ceci",
                    SimpleNamespace(agent=None, verbose=False),
                )
        self.assertTrue(provider.prompts)
        self.assertIn("ResearchAgent", provider.prompts[0])

    def test_all_legacy_agent_prefixes_still_dispatch(self) -> None:
        expected_agents = {
            "coder": "CodeAgent",
            "tester": "TestAgent",
            "reviewer": "ReviewAgent",
            "researcher": "ResearchAgent",
        }
        for prefix, agent_name in expected_agents.items():
            with self.subTest(prefix=prefix):
                provider = SkillProbeProvider(AgentTurn(text="Réponse de compatibilité."))
                agents = AgentRegistry.from_package()
                model_router = ModelRouter(
                    {"session": provider},
                    {agent.routing_key: "session" for agent in agents.list_agents()},
                    default_provider="session",
                )
                with tempfile.TemporaryDirectory(prefix="legacy-prefix-workspace-") as temporary:
                    loop = AgentLoop(
                        ToolRegistry(
                            WorkspaceFilesystem(Path(temporary)),
                            PermissionPolicy(autonomous=True),
                        ),
                        emit=None,
                        max_retries=0,
                    )
                    orchestrator = Orchestrator(agents, model_router, context=Context())
                    orchestrator.skill_router = self.make_router()
                    with redirect_stdout(io.StringIO()):
                        main._executer_mission(
                            orchestrator,
                            loop,
                            f"{prefix}: explique cette demande de test",
                            SimpleNamespace(agent=None, verbose=False),
                        )
                self.assertTrue(provider.prompts)
                self.assertIn(f"Tu es {agent_name}", provider.prompts[0])

    def test_slash_skill_reaches_skill_agent_before_agent_override(self) -> None:
        provider = SkillProbeProvider(AgentTurn(text="Sujet de test construit selon les règles chargées."))
        generic_agents = AgentRegistry.from_package()
        router = ModelRouter(
            {"session": provider},
            {agent.routing_key: "session" for agent in generic_agents.list_agents()},
            default_provider="session",
        )
        with tempfile.TemporaryDirectory(prefix="skill-workspace-") as temporary:
            tools = ToolRegistry(
                WorkspaceFilesystem(Path(temporary)),
                PermissionPolicy(autonomous=True),
            )
            loop = AgentLoop(tools, emit=None, max_retries=0)
            orchestrator = Orchestrator(generic_agents, router, context=Context())
            orchestrator.skill_router = self.make_router()
            output = io.StringIO()
            with redirect_stdout(output):
                main._executer_mission(
                    orchestrator,
                    loop,
                    "/bacblanc suite fonction espace",
                    SimpleNamespace(agent="researcher", verbose=False),
                )

        terminal = output.getvalue()
        self.assertIn("[SLASH] /bacblanc", terminal)
        self.assertIn("[SKILL] BacBlanc", terminal)
        self.assertIn("[SKILL PATH] skills/bacblanc", terminal)
        self.assertIn("[SKILL SOURCE] skills/bacblanc/skill.md", terminal)
        self.assertIn("[AGENT] BacBlancAgent", terminal)
        self.assertIn("[MISSION] suite fonction espace", terminal)
        self.assertNotIn("[AGENT] ResearchAgent", terminal)
        self.assertIn("skills/bacblanc/skill.md", provider.prompts[0])
        self.assertIn("Tu es BacBlancAgent", provider.prompts[0])
        self.assertIn("Structure de sortie", provider.prompts[0])
        self.assertIn("RÈGLES DU SKILL", provider.prompts[0])
        self.assertIn("delegate_to_agent", [item["name"] for item in provider.schemas[0]])
        self.assertIn("Sujet de test construit", terminal)


if __name__ == "__main__":
    unittest.main()
