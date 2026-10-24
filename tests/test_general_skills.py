# RÔLE DE CE FICHIER : teste les Skills généralistes, les commandes de supervision,
# le changement de provider, l'export, la mémoire et les événements sans API réelle.

from __future__ import annotations

import io
import os
import sys
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import main
from core.agent_loop import AgentLoop
from core.agent_registry import AgentRegistry
from core.context import Context
from core.events import EventTranslator
from core.memory import MemoryManager
from core.modes import HarnessMode, ModeManager
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy
from core.router import ModelRouter
from core.task import Task
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from skills.runtime import SkillRuntime
from skills.router import SkillRouter
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolCall, ToolRegistry


class ProbeProvider(BaseProvider):
    def __init__(self, name: str, model: str, answer: str = "Réponse de test.", error=None):
        self.name = name
        self.model = model
        self.answer = answer
        self.error = error
        self.prompts: list[str] = []
        self.tool_schemas: list[list[str]] = []

    def generate(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.answer

    def execute(self, instruction: str = "") -> str:
        return "No command execution."

    def get_name(self) -> str:
        return self.name

    def get_model_name(self) -> str:
        return self.model

    def get_status_label(self) -> str:
        return "[TEST MOCK]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.tool_schemas.append([item.get("name", "") for item in tools])
        return AgentTurn(text=self.generate(prompt or ""))


class GeneralSkillTests(unittest.TestCase):
    PROJECT = Path(__file__).resolve().parents[1]
    EXPECTED_SKILLS = {
        "model", "auto", "compare", "route", "workflow", "plan", "diagnostic",
        "research", "analyze", "debug", "review", "test", "refactor", "context",
        "memory", "export", "bacblanc", "mode",
    }

    def make_runtime(self, *, providers=None, routing=None):
        temporary = tempfile.TemporaryDirectory(prefix="general-skills-")
        self.addCleanup(temporary.cleanup)
        filesystem = WorkspaceFilesystem(temporary.name)
        tools = ToolRegistry(
            filesystem,
            PermissionPolicy(confirm=lambda _name, _risk: True),
        )
        events = []
        loop = AgentLoop(tools, max_iterations=3, max_retries=0, emit=None, event_sink=events.append)
        agents = AgentRegistry.from_package()
        providers = providers or {"mistral": ProbeProvider("MistralProvider", "mistral-test")}
        router = ModelRouter(
            providers,
            {agent.routing_key: "mistral" for agent in agents.list_agents()},
            default_provider="mistral",
            task_provider_map=routing or {},
        )
        orchestrator = Orchestrator(agents, router, context=Context())
        skills_root = self.PROJECT / "skills"
        registry = SkillRegistry.from_directory(skills_root)
        loader = SkillLoader(skills_root)
        orchestrator.skill_registry = registry
        orchestrator.skill_loader = loader
        orchestrator.skill_router = SkillRouter(registry, loader)
        settings = {
            "providers": {
                "openai": {"enabled": True, "model": "gpt-test"},
                "gemini": {"enabled": True, "model": "gemini-test"},
                "mistral": {"enabled": True, "model": "mistral-test"},
            },
            "routing": routing or {},
        }
        runtime = SkillRuntime(orchestrator, loop, settings, "api", memory=MemoryManager(tools))
        runtime.mode_manager = ModeManager(
            tools.permissions,
            on_change=lambda previous, current: loop._event(
                "mode.changed", previous=previous.value, current=current.value
            ),
        )
        return runtime, events

    def execute_slash(self, runtime, command: str) -> str:
        output = io.StringIO()
        with redirect_stdout(output):
            main._executer_mission(
                runtime.orchestrator,
                runtime.agent_loop,
                command,
                SimpleNamespace(agent=None, verbose=False),
                runtime=runtime,
            )
        return output.getvalue()

    def test_all_general_skills_are_discovered_and_loaded(self):
        runtime, _ = self.make_runtime()
        self.assertTrue(self.EXPECTED_SKILLS.issubset(set(runtime.orchestrator.skill_registry.names)))
        for name in self.EXPECTED_SKILLS - {"bacblanc"}:
            with self.subTest(skill=name):
                descriptor = runtime.orchestrator.skill_registry.get(name)
                loaded = runtime.orchestrator.skill_loader.load(descriptor)
                self.assertTrue(loaded.instructions)
                if name in {"model", "compare", "plan", "diagnostic", "context", "memory", "export", "auto", "route", "workflow", "mode"}:
                    self.assertTrue(callable(loaded.command_handler))

    def test_auto_routes_and_runs_through_existing_agent_loop(self):
        provider = ProbeProvider("GeminiProvider", "gemini-fast", "Réponse automatique.")
        runtime, events = self.make_runtime(
            providers={"gemini": provider},
            routing={"general_question:simple": "gemini"},
        )
        output = self.execute_slash(runtime, "/auto explique les fonctions Python")
        self.assertIn("[ROUTING]", output)
        self.assertIn("GeminiProvider", output)
        self.assertIn("ResearchAgent", output)
        self.assertTrue(provider.prompts)
        self.assertIn("Skill du Harness", provider.prompts[0])
        self.assertTrue(any(event.name == "delivery.completed" for event in events))

    def test_auto_routes_coding_and_limits_tools_to_intent_requirements(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Plan de code reçu.")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        output = self.execute_slash(runtime, "/auto code un programme Python")
        self.assertIn("[INTENT] coding", output)
        self.assertIn("CodeAgent", output)
        self.assertTrue(provider.tool_schemas)
        visible_tools = set(provider.tool_schemas[0])
        self.assertIn("write_file", visible_tools)
        self.assertIn("run_tests", visible_tools)
        self.assertNotIn("git_merge", visible_tools)

    def test_route_skill_runs_selector_and_router(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Réponse routée.")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        output = self.execute_slash(runtime, "/route code un programme")
        self.assertIn("[ROUTING]", output)
        self.assertIn("CodeAgent", output)
        self.assertTrue(provider.prompts)

    def test_skill_dispatch_reuses_legacy_agents_and_injects_skill_instructions(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Revue terminée.")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        output = self.execute_slash(runtime, "/review examine ce module")
        self.assertIn("[SKILL] Review", output)
        self.assertIn("ReviewAgent", output)
        self.assertIn("Skill du Harness", provider.prompts[0])

    def test_task_skills_dispatch_to_existing_agents(self):
        cases = {
            "research": ("explique les suites", "ResearchAgent"),
            "analyze": ("analyse cette idée", "ResearchAgent"),
            "debug": ("diagnostique cette erreur", "CodeAgent"),
            "review": ("relis cette proposition", "ReviewAgent"),
            "test": ("explique une stratégie de test", "TestAgent"),
            "refactor": ("refactorise cet algorithme conceptuellement", "CodeAgent"),
        }
        for command, (mission, expected_agent) in cases.items():
            with self.subTest(command=command):
                provider = ProbeProvider("MistralProvider", "mistral-test", "Réponse.")
                runtime, _ = self.make_runtime(providers={"mistral": provider})
                output = self.execute_slash(runtime, f"/{command} {mission}")
                self.assertIn(expected_agent, output)
                self.assertTrue(provider.prompts)

    def test_model_status_hides_key_and_model_switch_is_dynamic(self):
        mistral = ProbeProvider("MistralProvider", "mistral-test")
        gemini = ProbeProvider("GeminiProvider", "gemini-test")
        runtime, _ = self.make_runtime(providers={"mistral": mistral, "gemini": gemini})
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-secret-value"}):
            output = self.execute_slash(runtime, "/model status")
        self.assertIn("mistral-test", output)
        self.assertIn("présente", output)
        self.assertNotIn("test-secret-value", output)
        switched = self.execute_slash(runtime, "/model gemini")
        self.assertIn("Provider épinglé : gemini / gemini-test", switched)
        self.assertFalse(runtime.orchestrator.router.automatic_routing)
        self.assertIs(runtime.orchestrator.router.get_provider("coder"), gemini)
        self.execute_slash(runtime, "/model auto")
        self.assertTrue(runtime.orchestrator.router.automatic_routing)
        self.assertIs(runtime.orchestrator.router.get_provider("coder"), mistral)

    def test_plan_is_a_no_api_no_write_preview(self):
        provider = ProbeProvider("MistralProvider", "mistral-test")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        output = self.execute_slash(runtime, "/plan code un programme Python")
        self.assertIn("PRÉVISUALISATION", output)
        self.assertIn("Intention : coding", output)
        self.assertFalse(provider.prompts)
        self.assertEqual(runtime.agent_loop.tools.filesystem.list_files(), [])

    def test_compare_keeps_successful_models_when_one_fails(self):
        quota = RuntimeError("quota")
        quota.category = "quota"
        bad = ProbeProvider("MistralProvider", "mistral-limited", error=quota)
        good = ProbeProvider("GeminiProvider", "gemini-fast", "Réponse Gemini.")
        second = ProbeProvider("OpenAIProvider", "gpt-test", "Réponse GPT.")
        runtime, _ = self.make_runtime(providers={"mistral": bad, "gemini": good, "openai": second})
        output = self.execute_slash(runtime, "/compare explique ce concept")
        self.assertIn("[COMPARE INDISPONIBLE] MistralProvider", output)
        self.assertIn("[COMPARE OK] GeminiProvider", output)
        self.assertIn("[COMPARE OK] OpenAIProvider", output)
        self.assertIn("[REVIEW SYNTHESIS]", output)

    def test_diagnostic_reports_components_and_does_not_claim_tests_pass(self):
        runtime, _ = self.make_runtime()
        output = self.execute_slash(runtime, "/diagnostic")
        self.assertIn("MY AI HARNESS — DIAGNOSTIC", output)
        self.assertIn("/bacblanc", output)
        self.assertIn("CodeAgent", output)
        self.assertIn("aucun test exécuté", output)
        self.assertIn("Workspace", output)

    def test_workflow_command_uses_agent_loop_and_skill_instructions(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Étapes observées.")
        runtime, events = self.make_runtime(providers={"mistral": provider})
        output = self.execute_slash(runtime, "/workflow explique la mission")
        self.assertIn("[ROUTING]", output)
        self.assertTrue(provider.prompts)
        self.assertIn("workflow", provider.prompts[0].casefold())
        self.assertTrue(any(event.name == "provider.started" for event in events))

    def test_mode_skill_displays_table_and_changes_global_policy(self):
        runtime, events = self.make_runtime()
        help_output = self.execute_slash(runtime, "/mode")
        self.assertIn("MODES DU HARNESS", help_output)
        self.assertIn("Mode actif : ACCEPT", help_output)
        plan_output = self.execute_slash(runtime, "/mode PlAn")
        self.assertIn("ACCEPT → PLAN", plan_output)
        self.assertEqual(runtime.agent_loop.tools.permissions.mode, "PLAN")
        self.assertTrue(runtime.agent_loop.tools.permissions.dry_run)
        self.execute_slash(runtime, "/mode EDIT")
        self.assertEqual(runtime.mode_manager.current, HarnessMode.EDIT)
        self.assertFalse(runtime.agent_loop.tools.permissions.dry_run)
        self.execute_slash(runtime, "/mode accept")
        self.assertEqual(runtime.agent_loop.tools.permissions.mode, "ACCEPT")
        self.assertFalse(runtime.agent_loop.tools.permissions.autonomous)
        self.execute_slash(runtime, "/mode AUTO")
        self.assertEqual(runtime.agent_loop.tools.permissions.mode, "AUTO")
        self.assertTrue(runtime.agent_loop.tools.permissions.autonomous)
        self.assertTrue(any(event.name == "mode.changed" for event in events))

    def test_plan_mode_blocks_mutation_at_shared_permission_layer(self):
        with tempfile.TemporaryDirectory(prefix="mode-plan-") as directory:
            fs = WorkspaceFilesystem(directory)
            policy = PermissionPolicy(confirm=lambda _name, _risk: True)
            ModeManager(policy, "PLAN")
            tools = ToolRegistry(fs, policy)
            execution = tools.execute(
                ToolCall("write_file", {"path": "draft.py", "content": "x = 1"})
            )
            self.assertEqual(execution.status, "dry_run")
            self.assertFalse((Path(directory) / "draft.py").exists())

    def test_accept_mode_asks_and_obeys_confirmation(self):
        with tempfile.TemporaryDirectory(prefix="mode-accept-") as directory:
            decisions = []
            fs = WorkspaceFilesystem(directory)
            policy = PermissionPolicy(
                confirm=lambda name, risk: decisions.append((name, risk)) or False
            )
            ModeManager(policy, "ACCEPT")
            tools = ToolRegistry(fs, policy)
            execution = tools.execute(
                ToolCall("write_file", {"path": "draft.py", "content": "x = 1"})
            )
            self.assertEqual(execution.status, "denied")
            self.assertTrue(decisions)
            self.assertFalse((Path(directory) / "draft.py").exists())

    def test_edit_mode_previews_and_permits_file_edits_without_disabling_other_permissions(self):
        with tempfile.TemporaryDirectory(prefix="mode-edit-") as directory:
            previews = []
            fs = WorkspaceFilesystem(directory)
            policy = PermissionPolicy(
                confirm=lambda _name, _risk: False,
                edit_preview=lambda name, arguments: previews.append((name, arguments["path"])),
            )
            ModeManager(policy, "EDIT")
            tools = ToolRegistry(fs, policy)
            execution = tools.execute(
                ToolCall("write_file", {"path": "draft.py", "content": "x = 1"})
            )
            self.assertEqual(execution.status, "success")
            self.assertEqual(previews, [("write_file", "draft.py")])
            self.assertEqual(fs.read_file("draft.py"), "x = 1")
            run = tools.execute(ToolCall("run_tests", {}))
            self.assertEqual(run.status, "denied")

    def test_auto_mode_uses_existing_autonomous_permissions_and_respects_dry_run(self):
        with tempfile.TemporaryDirectory(prefix="mode-auto-") as directory:
            fs = WorkspaceFilesystem(directory)
            policy = PermissionPolicy(confirm=lambda _name, _risk: False)
            manager = ModeManager(policy, "ACCEPT")
            manager.set_mode("AUTO")
            tools = ToolRegistry(fs, policy)
            allowed = tools.execute(
                ToolCall("write_file", {"path": "draft.py", "content": "x = 1"})
            )
            self.assertEqual(allowed.status, "success")
            self.assertTrue(policy.autonomous)

            manager.set_mode("ACCEPT")
            self.assertFalse(policy.autonomous)
            denied = tools.execute(
                ToolCall("write_file", {"path": "other.py", "content": "x = 2"})
            )
            self.assertEqual(denied.status, "denied")

            hard_dry_run = PermissionPolicy(
                confirm=lambda _name, _risk: True,
                dry_run=True,
            )
            dry_run_manager = ModeManager(hard_dry_run, "AUTO")
            dry_run_tools = ToolRegistry(WorkspaceFilesystem(directory), hard_dry_run)
            blocked = dry_run_tools.execute(
                ToolCall("write_file", {"path": "blocked.py", "content": "x = 3"})
            )
            self.assertEqual(blocked.status, "dry_run")
            self.assertTrue(hard_dry_run.autonomous)
            self.assertEqual(dry_run_manager.current, HarnessMode.AUTO)

        provider = ProbeProvider("MistralProvider", "mistral-test", "Étapes réalisées.")
        runtime, events = self.make_runtime(providers={"mistral": provider})
        runtime.mode_manager.set_mode("AUTO")
        output = self.execute_slash(runtime, "/workflow explique cette mission")
        self.assertIn("[MODE] AUTO", output)
        self.assertIn("Mode global du Harness : AUTO", provider.prompts[0])
        self.assertTrue(any(event.name == "delivery.completed" for event in events))

    def test_shift_tab_input_and_mode_cycle(self):
        runtime, _ = self.make_runtime()
        fake_msvcrt = SimpleNamespace(
            getwch=Mock(side_effect=["\x00", "\x0f"])
        )
        with patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
            with redirect_stdout(io.StringIO()):
                key = main._read_windows_console_line("test> ")
        self.assertEqual(key, main.SHIFT_TAB)
        for sequence in (("\x0f",), ("\x1b", "[", "Z")):
            fake_msvcrt = SimpleNamespace(getwch=Mock(side_effect=list(sequence)))
            with patch.dict(sys.modules, {"msvcrt": fake_msvcrt}):
                with redirect_stdout(io.StringIO()):
                    key = main._read_windows_console_line("test> ")
            self.assertEqual(key, main.SHIFT_TAB)
        runtime.mode_manager.set_mode("EDIT")
        transitions = [runtime.mode_manager.advance() for _ in range(4)]
        self.assertEqual(
            [(old.value, new.value) for old, new in transitions],
            [("EDIT", "PLAN"), ("PLAN", "ACCEPT"), ("ACCEPT", "AUTO"), ("AUTO", "EDIT")],
        )

    def test_prompt_toolkit_backtab_binding_returns_shift_tab_immediately(self):
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        runtime, _ = self.make_runtime()
        results = []
        errors = []
        with create_pipe_input() as pipe_input:
            reader = threading.Thread(
                target=lambda: self._capture_prompt_result(
                    results,
                    errors,
                    input=pipe_input,
                    output=DummyOutput(),
                ),
                daemon=True,
            )
            reader.start()
            pipe_input.send_text("\x1b[Z")
            reader.join(timeout=3)
        self.assertFalse(reader.is_alive(), "Shift+Tab n'a pas interrompu la saisie CLI.")
        self.assertEqual(errors, [])
        self.assertEqual(results, [main.SHIFT_TAB])
        self.assertEqual(runtime.mode_manager.current, HarnessMode.ACCEPT)
        with redirect_stdout(io.StringIO()):
            handled = main._traiter_raccourci_mode(runtime, results[0])
        self.assertTrue(handled)
        self.assertEqual(runtime.mode_manager.current, HarnessMode.AUTO)
        self.assertTrue(runtime.agent_loop.tools.permissions.autonomous)

    @staticmethod
    def _capture_prompt_result(results, errors, **kwargs):
        try:
            results.append(main._read_prompt_toolkit_line("test> ", **kwargs))
        except BaseException as error:
            errors.append(error)

    def test_mode_panel_has_active_indicator_and_ascii_fallback(self):
        panel = main.render_mode_panel("accept", unicode=True, color=False)
        self.assertTrue(panel.splitlines()[0].startswith("┌"))
        self.assertTrue(panel.splitlines()[0].endswith("┐"))
        self.assertIn("Mode : ● ACCEPT", panel)
        self.assertIn("[EDIT]   [PLAN]   [● ACCEPT]   [AUTO]", panel)
        self.assertNotIn("\x1b[", panel)

        ascii_panel = main.render_mode_panel("PLAN", unicode=False, color=False)
        self.assertIn("Mode : * PLAN", ascii_panel)
        self.assertIn("[* PLAN]", ascii_panel)
        self.assertNotIn("●", ascii_panel)

    def test_ready_banner_displays_interactive_mode_panel(self):
        provider = ProbeProvider("OllamaProvider", "qwen-local")
        output = io.StringIO()
        with redirect_stdout(output):
            main.afficher_harness_pret(
                "local", "ollama", provider, work_mode="ACCEPT"
            )
        rendered = output.getvalue()
        self.assertIn("MY AI HARNESS", rendered)
        self.assertIn("Mode :", rendered)
        self.assertIn("ACCEPT", rendered)
        self.assertIn("Shift+Tab : changer de mode", rendered)
        self.assertIn("/mode <nom>", rendered)

    def test_direct_agent_slash_commands_inherit_global_mode(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Réponse agent.")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        runtime.mode_manager.set_mode("PLAN")
        for command, expected_agent in (
            ("/coder explique cette fonction", "CodeAgent"),
            ("/reviewer relis cette réponse", "ReviewAgent"),
            ("/tester vérifie ce résultat", "TestAgent"),
        ):
            with self.subTest(command=command):
                output = self.execute_slash(runtime, command)
                self.assertIn(f"[AGENT] {expected_agent}", output)
                self.assertIn("[MODE] PLAN", output)
                self.assertIn("Mode global du Harness : PLAN", provider.prompts[-1])

    def test_any_task_skill_inherits_plan_mode(self):
        provider = ProbeProvider("MistralProvider", "mistral-test", "Analyse terminée.")
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        runtime.mode_manager.set_mode("PLAN")
        output = self.execute_slash(runtime, "/review relis cette proposition")
        self.assertIn("[MODE] PLAN", output)
        self.assertIn("Mode global du Harness : PLAN", provider.prompts[0])

    def test_delegated_agent_inherits_parent_mode(self):
        class DelegatingProvider(ProbeProvider):
            def __init__(self):
                super().__init__("MistralProvider", "mistral-test")
                self.review_turns = 0

            def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
                prompt = prompt or ""
                self.prompts.append(prompt)
                if "Tu es ReviewAgent" in prompt:
                    self.review_turns += 1
                    if self.review_turns == 1:
                        return AgentTurn(
                            tool_calls=[
                                ProviderToolCall(
                                    name="delegate_to_agent",
                                    arguments={"agent": "researcher", "task": "Apporte un éclairage général."},
                                )
                            ]
                        )
                    return AgentTurn(text="Synthèse relue avec le retour délégué.")
                if "Tu es ResearchAgent" in prompt:
                    return AgentTurn(text="Éclairage général transmis.")
                return AgentTurn(text="Réponse.")

        provider = DelegatingProvider()
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        runtime.mode_manager.set_mode("AUTO")
        task = Task("Relis cette proposition", type="reviewer", explicit_agent=True)
        with redirect_stdout(io.StringIO()):
            result = runtime.orchestrator.run_agentic(task, runtime.agent_loop)
        self.assertTrue(any("Tu es ResearchAgent" in prompt for prompt in provider.prompts))
        self.assertTrue(
            all(
                "Mode global du Harness : AUTO" in prompt
                for prompt in provider.prompts
                if isinstance(prompt, str) and prompt.strip()
            )
        )
        self.assertEqual(runtime.agent_loop.tools.permissions.mode, "AUTO")
        self.assertNotEqual(result.status, "failed", result.answer)

    def test_bacblanc_plan_mode_cannot_write_even_if_provider_requests_it(self):
        class WriteAttemptProvider(ProbeProvider):
            def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
                self.prompts.append(prompt)
                self.tool_schemas.append([item.get("name", "") for item in tools])
                return AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            name="write_file",
                            arguments={"path": "bacblanc/sujet.tex", "content": "draft"},
                        )
                    ]
                )

        with tempfile.TemporaryDirectory(prefix="mode-bacblanc-plan-") as directory:
            filesystem = WorkspaceFilesystem(directory)
            tools = ToolRegistry(filesystem, PermissionPolicy(confirm=lambda _name, _risk: True))
            loop = AgentLoop(tools, max_iterations=1, max_retries=0, emit=None)
            ModeManager(tools.permissions, "PLAN")
            provider = WriteAttemptProvider("MistralProvider", "mistral-test")
            skills_root = self.PROJECT / "skills"
            loaded = SkillLoader(skills_root).load(
                SkillRegistry.from_directory(skills_root).get("bacblanc")
            )
            loaded.agent.set_provider(provider)
            loaded.agent.skill_config["max_iterations"] = 1
            task = Task("Créer un sujet de bac blanc", type="bacblanc", skill=loaded)
            with redirect_stdout(io.StringIO()):
                loop.run(loaded.agent, task)
            self.assertNotIn("write_file", provider.tool_schemas[0])
            self.assertFalse((Path(directory) / "bacblanc" / "sujet.tex").exists())

    def test_quota_failure_keeps_selected_mode(self):
        quota = RuntimeError("HTTP 429")
        quota.category = "quota"
        provider = ProbeProvider("MistralProvider", "mistral-limited", error=quota)
        runtime, _ = self.make_runtime(providers={"mistral": provider})
        runtime.mode_manager.set_mode("AUTO")
        runtime.agent_loop.emit = None
        _, agent = runtime.orchestrator.agent_registry.resolve("coder")
        agent.set_provider(provider)
        with redirect_stdout(io.StringIO()):
            runtime.agent_loop.run(agent, Task("explique ce code", type="coder", explicit_agent=True))
        self.assertEqual(runtime.mode_manager.current, HarnessMode.AUTO)
        self.assertEqual(runtime.agent_loop.tools.permissions.mode, "AUTO")

    def test_memory_scopes_are_separate_and_sensitive_notes_are_rejected(self):
        runtime, _ = self.make_runtime()
        output = self.execute_slash(runtime, "/memory remember session note temporaire")
        self.assertIn("session", output)
        self.assertEqual(runtime.memory.session, ["note temporaire"])
        self.execute_slash(runtime, "/memory remember decision valider les tests avant livraison")
        self.execute_slash(runtime, "/memory remember preference langue=français")
        self.assertEqual(len(runtime.memory.decisions), 1)
        self.assertEqual(runtime.memory.preferences["langue"], "français")
        with self.assertRaisesRegex(ValueError, "secret"):
            runtime.memory.remember("session", "OPENAI_API_KEY=should-not-store")
        project = self.execute_slash(runtime, "/memory remember project conserver les contrats legacy")
        self.assertIn("après autorisation", project)
        self.assertEqual(len(runtime.memory.project), 1)
        stored = runtime.agent_loop.tools.filesystem.read_file(runtime.memory.PROJECT_PATH)
        self.assertIn("contrats legacy", stored)

    def test_export_generates_real_workspace_artifacts_and_checks_formats(self):
        runtime, _ = self.make_runtime()
        runtime.orchestrator.context.last_result = "# Résultat\n\nUne réponse vérifiée."
        for fmt, suffix in (("markdown", ".md"), ("latex", ".tex"), ("docx", ".docx"), ("pdf", ".pdf")):
            with self.subTest(fmt=fmt):
                output = self.execute_slash(runtime, f"/export {fmt}")
                self.assertIn("[EXPORT OK]", output)
                paths = [p for p in runtime.workspace.rglob("*") if p.is_file() and p.suffix == suffix]
                self.assertTrue(paths)
                data = paths[-1].read_bytes()
                if suffix == ".docx":
                    self.assertTrue(zipfile.is_zipfile(paths[-1]))
                if suffix == ".pdf":
                    self.assertTrue(data.startswith(b"%PDF"))

    def test_quota_failure_emits_provider_and_delivery_events(self):
        quota = RuntimeError("HTTP 429")
        quota.category = "quota"
        provider = ProbeProvider("MistralProvider", "mistral-limited", error=quota)
        runtime, events = self.make_runtime(providers={"mistral": provider})
        runtime.agent_loop.emit = print
        _, agent = runtime.orchestrator.agent_registry.resolve("coder")
        agent.set_provider(provider)
        output = io.StringIO()
        with redirect_stdout(output):
            result = runtime.agent_loop.run(agent, Task("explique ce code", type="coder", explicit_agent=True))
        names = [event.name for event in events]
        self.assertIn("provider.error", names)
        self.assertIn("delivery.failed", names)
        translated = [EventTranslator.translate(event) for event in events]
        self.assertIn("Le quota ou la limite de débit du fournisseur a été atteint.", translated)
        self.assertIn("[PROVIDER ERROR]", output.getvalue())
        self.assertIn("[DELIVERY STATUS]", output.getvalue())
        self.assertEqual(result.status, "failed")


if __name__ == "__main__":
    unittest.main()
