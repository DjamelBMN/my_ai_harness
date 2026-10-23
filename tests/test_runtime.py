# RÔLE DE CE FICHIER :
# Vérifie le routeur, le cycle agentique, les outils, les permissions, les formats de
# documents et les adaptateurs providers sans effectuer d'appel distant réel.

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agents.coder import CodeAgent
from agents.researcher import ResearchAgent
import main as main_module
from core.agent_loop import AgentLoop
from core.agent_registry import AgentRegistry
from core.agent_selector import AgentSelector
from core.context import Context
from core.context_manager import ContextManager
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy
from core.planner import ClarificationRequired, Planner
from core.router import ModelRouter, load_config
from core.task import Task
from core.task_state import AgentResult, TaskState
from core.verifier import Verifier
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from providers.claude import ClaudeProvider
from providers.gemini import GeminiProvider, GeminiProviderError
from providers.local import LocalProvider
from providers.ollama import OllamaProvider
from providers.openai import OpenAIProvider, OpenAIProviderError
from tools.documents import read_document
from tools.filesystem import WorkspaceFilesystem
from tools.git import GitWorkspace
from tools.registry import ToolCall, ToolRegistry
from tools.process_utils import safe_subprocess_environment
from tools.search import search_web
from tools.terminal import run_python_script, run_test_suite


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TemporaryWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory(
            prefix="harness-test-", dir=PROJECT_ROOT / "workspace"
        )
        self.root = Path(self._temporary.name)
        self.fs = WorkspaceFilesystem(self.root)

    def tearDown(self):
        self._temporary.cleanup()


class ProbeProvider(BaseProvider):
    def __init__(self, name="probe", turns=None):
        self.name = name
        self.turns = list(turns or [])
        self.calls = []

    def generate(self, prompt=""):
        return "probe response"

    def execute(self, instruction=""):
        return "No command execution."

    def get_name(self):
        return self.name

    def get_model_name(self):
        return "probe-model"

    def get_status_label(self):
        return "[TEST DOUBLE]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None):
        self.calls.append({
            "prompt": prompt,
            "tools": tools,
            "continuation": continuation,
            "tool_results": tool_results or [],
        })
        if not self.turns:
            raise AssertionError("Unexpected provider turn")
        return self.turns.pop(0)


class RouterAndPlannerTests(unittest.TestCase):
    def test_code_un_programme_is_coding_and_selects_code_agent(self):
        task = Task("code un programme")
        state = Planner().plan(task)
        registry = AgentRegistry.from_package()
        selection = AgentSelector(registry).select(task, state)
        self.assertEqual(state.intent, "coding")
        self.assertEqual(selection.agent.name, "CodeAgent")
        self.assertNotEqual(selection.agent.name, "ResearchAgent")
        self.assertTrue(state.intent_decision["requires_workspace"])
        self.assertTrue(state.intent_decision["requires_modification"])
        self.assertTrue(state.intent_decision["requires_tests"])

    def test_config_loads_complexity_routes(self):
        settings = load_config(PROJECT_ROOT / "config" / "config.yaml")
        self.assertEqual(
            settings["routing"]["general_question:simple"], "gemini_flash_lite"
        )
        self.assertEqual(settings["providers"]["openai"]["model"], "gpt-5-mini")

    def test_router_uses_task_route_and_falls_back_when_missing(self):
        openai = ProbeProvider("OpenAIProvider")
        local = ProbeProvider("OllamaProvider")
        router = ModelRouter(
            providers={"openai": openai, "ollama": local},
            agent_provider_map={"coder": "ollama"},
            default_provider="ollama",
            task_provider_map={"coding:complex": "openai", "research": "gemini"},
        )
        self.assertIs(router.get_provider("coder", "coding", "complex"), openai)
        self.assertIs(router.get_provider("coder", "research", "simple"), local)

    def test_api_harness_registers_available_model_routes_without_network(self):
        gemini = GeminiProvider("gemini-3.8-flash")
        gemini._available_models = {
            "gemini-3.8-flash": "Gemini 3.8 Flash",
            "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
        }
        gemini._verified = True
        settings = {
            "providers": {
                "openai": {"enabled": True, "model": "gpt-5-mini"},
                "gemini": {"enabled": True, "model": "gemini-3.8-flash"},
            },
            "routing": {
                "coding:complex": "openai",
                "research:simple": "gemini_flash_lite",
            },
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only", "GEMINI_API_KEY": "test-only"}):
            orchestrator = main_module.construire_harness(
                gemini, "gemini", settings, mode="api"
            )
        self.assertIsInstance(
            orchestrator.router.get_provider("coder", "coding", "complex"),
            OpenAIProvider,
        )
        lightweight = orchestrator.router.get_provider("researcher", "research", "simple")
        self.assertEqual(lightweight.get_model_name(), "gemini-3.5-flash-lite")

    def test_planner_honors_explicit_agent_and_detects_ambiguity(self):
        planner = Planner()
        state = planner.plan(Task("Analyse ce fichier", type="researcher", explicit_agent=True))
        self.assertEqual(state.assigned_agent, "researcher")
        self.assertEqual(state.intent, "file_analysis")
        self.assertEqual(state.complexity, "complex")
        with self.assertRaises(ClarificationRequired):
            planner.classify("code")


class FilesystemAndDocumentTests(TemporaryWorkspaceTestCase):
    def test_filesystem_is_confined_and_redacts_secrets(self):
        (self.root / "notes.txt").write_text(
            "OPENAI_API_KEY=PLACEHOLDER_TEST_VALUE", encoding="utf-8"
        )
        self.assertIn("[REDACTED]", self.fs.read_file("notes.txt"))
        with self.assertRaises(ValueError):
            self.fs.read_file("../outside.txt")
        with self.assertRaises(PermissionError):
            self.fs.read_file(".env")
        with self.assertRaises(PermissionError):
            self.fs.write_file("saved.txt", "GEMINI_API_KEY=PLACEHOLDER_TEST_VALUE")

    def test_write_patch_move_delete_and_no_implicit_overwrite(self):
        created = self.fs.write_file("nested/item.txt", "alpha beta")
        self.assertEqual(created["path"], "nested/item.txt")
        with self.assertRaises(FileExistsError):
            self.fs.write_file("nested/item.txt", "replacement")
        patched = self.fs.patch_file("nested/item.txt", "alpha", "gamma")
        self.assertEqual(patched["replacements"], 1)
        self.assertEqual(self.fs.read_file("nested/item.txt"), "gamma beta")
        moved = self.fs.move_file("nested/item.txt", "renamed.txt")
        self.assertEqual(moved["destination"], "renamed.txt")
        self.fs.delete_file("renamed.txt")
        self.assertFalse((self.root / "renamed.txt").exists())

    def test_documents_text_json_csv_html_and_pdf(self):
        (self.root / "data.json").write_text('{"ok": true}', encoding="utf-8")
        (self.root / "data.csv").write_text("name,value\na,1", encoding="utf-8")
        (self.root / "page.html").write_text(
            "<h1>Visible</h1><script>secretText()</script>", encoding="utf-8"
        )
        self.assertEqual(read_document("data.json", filesystem=self.fs)["format"], "json")
        self.assertIn("name | value", read_document("data.csv", filesystem=self.fs)["text"])
        html_text = read_document("page.html", filesystem=self.fs)["text"]
        self.assertIn("Visible", html_text)
        self.assertNotIn("secretText", html_text)

        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF absent")
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Verified PDF text")
        pdf_path = self.root / "sample.pdf"
        pdf_path.write_bytes(document.tobytes())
        document.close()
        extracted = read_document("sample.pdf", filesystem=self.fs)
        self.assertIn("Verified PDF text", extracted["text"])
        self.assertEqual(extracted["metadata"]["extraction"], "embedded_text")

    def test_scanned_pdf_uses_ocr_when_tesseract_is_available(self):
        try:
            import fitz
            import pytesseract
            from PIL import Image, ImageDraw, ImageFont

            pytesseract.get_tesseract_version()
        except Exception:
            self.skipTest("Tesseract/Pillow/PyMuPDF OCR stack absent")
        image = Image.new("RGB", (1200, 400), "white")
        draw = ImageDraw.Draw(image)
        draw.text((80, 140), "SCANNED PAGE CHECK", fill="black", font=ImageFont.load_default(size=72))
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        document = fitz.open()
        page = document.new_page(width=600, height=200)
        page.insert_image(page.rect, stream=image_buffer.getvalue())
        (self.root / "scanned.pdf").write_bytes(document.tobytes())
        document.close()

        extracted = read_document("scanned.pdf", filesystem=self.fs)
        self.assertEqual(extracted["metadata"]["extraction"], "ocr")
        self.assertIn("SCANNED", extracted["text"].upper())

    def test_docx_xlsx_and_pptx_extraction(self):
        document_xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>DOCX content</w:t></w:r></w:p></w:body></w:document>'
        )
        with zipfile.ZipFile(self.root / "sample.docx", "w") as archive:
            archive.writestr("word/document.xml", document_xml)
        self.assertIn("DOCX content", read_document("sample.docx", filesystem=self.fs)["text"])

        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl absent")
        workbook = Workbook()
        workbook.active["A1"] = "XLSX content"
        workbook.save(self.root / "sample.xlsx")
        self.assertIn("XLSX content", read_document("sample.xlsx", filesystem=self.fs)["text"])

        slide_xml = (
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            '<a:t>PPTX content</a:t></p:sld>'
        )
        with zipfile.ZipFile(self.root / "sample.pptx", "w") as archive:
            archive.writestr("ppt/slides/slide1.xml", slide_xml)
        self.assertIn("PPTX content", read_document("sample.pptx", filesystem=self.fs)["text"])

    def test_registry_validates_calls_and_obeys_dry_run(self):
        registry = ToolRegistry(
            self.fs,
            PermissionPolicy(dry_run=True),
        )
        self.fs.write_file("readme.md", "readable")
        read_result = registry.execute(ToolCall("read_file", {"path": "readme.md"}))
        self.assertEqual(read_result.status, "success")
        invalid = registry.execute(ToolCall("read_file", {"unknown": "x"}))
        self.assertEqual(invalid.status, "error")
        denied = registry.execute(
            ToolCall("write_file", {"path": "new.txt", "content": "x"})
        )
        self.assertEqual(denied.status, "dry_run")
        self.assertFalse((self.root / "new.txt").exists())

        self.fs.write_file("script.py", "print('executed')")
        script = registry.execute(
            ToolCall("run_python", {"script_path": "script.py"})
        )
        self.assertEqual(script.status, "dry_run")

        self.fs.write_file("protected.txt", "keep")
        denying_registry = ToolRegistry(
            self.fs,
            PermissionPolicy(confirm=lambda _name, _risk: False),
        )
        deletion = denying_registry.execute(
            ToolCall("delete_file", {"path": "protected.txt"})
        )
        self.assertEqual(deletion.status, "denied")
        self.assertTrue((self.root / "protected.txt").exists())

    def test_test_runner_never_calls_empty_suite_a_pass(self):
        empty = run_test_suite(self.root)
        self.assertEqual(empty["status"], "no_tests")
        (self.root / "test_sample.py").write_text(
            "import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self): self.assertEqual(2, 1 + 1)\n",
            encoding="utf-8",
        )
        result = run_test_suite(self.root)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["test_count"], 1)

    def test_python_script_runs_without_inheriting_api_keys(self):
        self.fs.write_file(
            "environment.py",
            "import os\nprint(os.getenv('OPENAI_API_KEY', 'missing'))\n",
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-reach-child"}):
            result = run_python_script(self.root, "environment.py")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["stdout"].strip(), "missing")

    def test_corrupt_pdf_is_an_error_and_web_search_does_not_fake_sources(self):
        (self.root / "corrupt.pdf").write_bytes(b"not a PDF")
        with self.assertRaises(Exception):
            read_document("corrupt.pdf", filesystem=self.fs)
        with self.assertRaisesRegex(RuntimeError, "Aucun backend de recherche Web"):
            search_web("current information")

    def test_git_workspace_operations_and_repository_boundary(self):
        executable = shutil.which("git")
        if executable is None:
            self.skipTest("Git absent")

        def git(*args):
            return subprocess.run(
                [executable, *args], cwd=self.root, env=safe_subprocess_environment(),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                check=True, shell=False,
            )

        git("init", "--quiet")
        git("config", "user.name", "Harness Test")
        git("config", "user.email", "harness-test@example.invalid")
        git("config", "commit.gpgsign", "false")
        self.fs.write_file("base.txt", "base")
        git("add", "base.txt")
        git("commit", "--quiet", "-m", "base")

        repository = GitWorkspace(self.root)
        initial_branch = repository.current_branch()["branch"]
        self.assertTrue(initial_branch)
        repository.create_branch("feature/harness-test")
        self.fs.write_file("feature.txt", "feature")
        git("add", "feature.txt")
        repository.commit_staged("feature work")
        git("switch", initial_branch)
        merged = repository.merge("feature/harness-test")
        self.assertEqual(merged["branch"], "feature/harness-test")
        self.assertTrue((self.root / "feature.txt").is_file())
        self.assertIn("## ", repository.status()["output"])

        nested = self.root / "nested"
        nested.mkdir()
        with self.assertRaisesRegex(PermissionError, "au-dessus du workspace"):
            GitWorkspace(nested).status()


class AgentLoopIntegrationTests(TemporaryWorkspaceTestCase):
    def test_orchestrator_tool_observation_verification_and_delivery(self):
        (self.root / "notes.md").write_text("The verified note says agent loops observe tools.", encoding="utf-8")
        provider = ProbeProvider(
            turns=[
                AgentTurn(
                    tool_calls=[ProviderToolCall("read_document", {"path": "notes.md"}, "read-1")],
                    continuation="turn-1",
                ),
                AgentTurn(text="Le document explique que la boucle observe les outils.", continuation="turn-2"),
            ]
        )
        agents = {"researcher": ResearchAgent(), "coder": CodeAgent()}
        router = ModelRouter(
            providers={"probe": provider},
            agent_provider_map={"researcher": "probe", "coder": "probe"},
            default_provider="probe",
        )
        orchestrator = Orchestrator(agents, router, Context())
        registry = ToolRegistry(self.fs, PermissionPolicy())
        loop = AgentLoop(registry, emit=None, max_iterations=4)

        with redirect_stdout(io.StringIO()):
            result = orchestrator.run_agentic(
                Task("Analyse le fichier de notes", type="researcher", explicit_agent=True),
                loop,
            )
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.verification["status"], "passed")
        self.assertEqual(len(provider.calls), 2)
        self.assertTrue(any(item.get("tool") == "read_document" for item in result.observations))
        self.assertEqual(result.artifacts, [])
        self.assertEqual(orchestrator.context.files, ["notes.md"])
        self.assertIn("observe", result.answer)

    def test_code_fix_needs_failure_before_patch_and_pass_after_patch(self):
        self.fs.write_file("target.py", "def answer():\n    return 1\n")
        self.fs.write_file(
            "test_target.py",
            "import unittest\nfrom target import answer\n"
            "class TestTarget(unittest.TestCase):\n"
            "    def test_answer(self): self.assertEqual(answer(), 2)\n",
        )
        provider = ProbeProvider(
            turns=[
                AgentTurn(
                    tool_calls=[ProviderToolCall("run_tests", {}, "before-test")],
                    continuation="turn-1",
                ),
                AgentTurn(
                    tool_calls=[ProviderToolCall(
                        "patch_file",
                        {"path": "target.py", "old_text": "return 1", "new_text": "return 2"},
                        "patch-1",
                    )],
                    continuation="turn-2",
                ),
                AgentTurn(
                    tool_calls=[ProviderToolCall("run_tests", {}, "after-test")],
                    continuation="turn-3",
                ),
                AgentTurn(text="Le test a reproduit l'échec, puis passe après la correction."),
            ]
        )
        agent = CodeAgent()
        router = ModelRouter(
            providers={"probe": provider},
            agent_provider_map={"coder": "probe"},
            default_provider="probe",
        )
        orchestrator = Orchestrator({"coder": agent}, router, Context())
        registry = ToolRegistry(
            self.fs,
            PermissionPolicy(confirm=lambda _name, _risk: True),
        )
        loop = AgentLoop(registry, emit=None, max_iterations=6, max_retries=0)

        with redirect_stdout(io.StringIO()):
            result = orchestrator.run_agentic(
                Task(
                    "Corrige le bug dans target.py après l'avoir reproduit avec les tests.",
                    type="coder",
                    explicit_agent=True,
                ),
                loop,
            )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.verification["status"], "passed")
        self.assertEqual(result.artifacts[0]["path"], "target.py")
        self.assertEqual(self.fs.read_file("target.py"), "def answer():\n    return 2\n")
        checks = {item["check"]: item["status"] for item in result.verification["checks"]}
        self.assertEqual(checks["bug_reproduced_before_change"], "passed")
        self.assertEqual(checks["tests_executed_and_passed"], "passed")

    def test_legacy_orchestrator_run_contract_remains_available(self):
        provider = ProbeProvider()
        agent = ResearchAgent()
        router = ModelRouter(
            providers={"probe": provider},
            agent_provider_map={"researcher": "probe"},
            default_provider="probe",
        )
        orchestrator = Orchestrator({"researcher": agent}, router, Context())
        with redirect_stdout(io.StringIO()):
            result = orchestrator.run(Task("Une question", type="researcher"))
        self.assertEqual(result, "probe response")
        self.assertEqual(provider.calls, [])

    def test_context_manager_bounds_session_history(self):
        context = Context(history=["old" * 1000, "middle", "recent"])
        ContextManager(max_items=2, max_characters=600).compact(context)
        self.assertEqual(context.history, ["middle", "recent"])
        self.assertLessEqual(sum(map(len, context.history)), 600)

    def test_verifier_requires_real_test_output_for_test_tasks(self):
        state = TaskState("Teste ce projet", intent="testing")
        failed = Verifier().verify(state, self.fs)
        self.assertEqual(failed["status"], "failed")
        state.tool_results.append({
            "tool": "run_tests",
            "status": "success",
            "data": {"status": "passed", "exit_code": 0, "test_count": 2},
        })
        passed = Verifier().verify(state, self.fs)
        self.assertEqual(passed["status"], "passed")

    def test_verifier_rejects_a_pass_that_happened_before_a_change(self):
        self.fs.write_file("target.py", "def answer(): return 1\n")
        state = TaskState(
            "Corrige le bug dans target.py", intent="coding"
        )
        state.tool_results.extend([
            {
                "tool": "run_tests", "status": "success",
                "data": {"status": "passed", "exit_code": 0, "test_count": 1},
            },
            {
                "tool": "patch_file", "status": "success",
                "data": {"path": "target.py", "sha256": "not-the-file-hash"},
            },
        ])
        report = Verifier().verify(state, self.fs)
        checks = {item["check"]: item["status"] for item in report["checks"]}
        self.assertEqual(checks["tests_executed_and_passed"], "failed")
        self.assertEqual(checks["bug_reproduced_before_change"], "failed")


class ProviderAdapterTests(unittest.TestCase):
    def test_legacy_provider_generate_contracts_return_plain_text(self):
        openai_provider = OpenAIProvider("gpt-5-mini")
        openai_provider._client = SimpleNamespace(
            responses=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(output_text="GPT text")
            )
        )
        gemini_provider = GeminiProvider("gemini-3.5-flash-lite")
        gemini_provider._verified = True
        gemini_provider._client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: SimpleNamespace(text="Gemini text")
            )
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only", "GEMINI_API_KEY": "test-only"}):
            self.assertEqual(openai_provider.generate("prompt"), "GPT text")
            self.assertEqual(gemini_provider.generate("prompt"), "Gemini text")

        from providers import ollama as ollama_module

        class LegacyResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"message": {"content": "Qwen text"}}).encode()

        ollama_provider = OllamaProvider()
        ollama_provider._verified = True
        with patch.object(ollama_module, "urlopen", return_value=LegacyResponse()):
            self.assertEqual(ollama_provider.generate("prompt"), "Qwen text")

    def test_openai_native_function_call_round_trip_without_network(self):
        first = SimpleNamespace(
            id="response-1",
            status="completed",
            output_text="",
            output=[SimpleNamespace(
                type="function_call",
                name="read_file",
                arguments='{"path":"notes.md"}',
                call_id="call-1",
            )],
        )
        second = SimpleNamespace(
            id="response-2", status="completed", output_text="Document read.", output=[]
        )

        class FakeResponses:
            def __init__(self):
                self.requests = []
                self.responses = [first, second]

            def create(self, **kwargs):
                self.requests.append(kwargs)
                return self.responses.pop(0)

        responses = FakeResponses()
        provider = OpenAIProvider("gpt-5-mini")
        provider._client = SimpleNamespace(responses=responses)
        schema = [{
            "name": "read_file", "description": "Read a file",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-never-written"}):
            turn = provider.generate_agent_turn("Read notes", schema)
            self.assertEqual(turn.tool_calls[0].name, "read_file")
            final = provider.generate_agent_turn(
                None, schema, continuation=turn.continuation,
                tool_results=[{"call_id": "call-1", "name": "read_file", "status": "success", "output": "ok"}],
            )
        self.assertEqual(final.text, "Document read.")
        self.assertEqual(responses.requests[1]["previous_response_id"], "response-1")
        self.assertEqual(responses.requests[1]["input"][0]["type"], "function_call_output")

    def test_openai_incomplete_output_is_marked_partial(self):
        response = SimpleNamespace(
            id="response-partial", status="incomplete", output_text="partial text", output=[]
        )
        provider = OpenAIProvider("gpt-5-mini")
        provider._client = SimpleNamespace(
            responses=SimpleNamespace(create=lambda **kwargs: response)
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}):
            turn = provider.generate_agent_turn("prompt", [])
        self.assertTrue(turn.partial)
        self.assertEqual(turn.text, "partial text")

    def test_openai_missing_key_fails_before_sdk_or_network(self):
        provider = OpenAIProvider("gpt-5-mini")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(OpenAIProviderError, "OPENAI_API_KEY"):
                provider.generate("test")

    def test_gemini_lists_only_generate_content_models_and_includes_flash_lite(self):
        provider = GeminiProvider()
        provider._client = SimpleNamespace(
            models=SimpleNamespace(list=lambda: [
                SimpleNamespace(name="models/gemini-3.5-flash-lite", display_name="Gemini 3.5 Flash-Lite", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/embedding-only", display_name="Embed", supported_actions=["embedContent"]),
            ])
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only"}):
            models = provider.list_available_models()
        self.assertEqual([item["model"] for item in models], ["gemini-3.5-flash-lite"])
        provider.select_model("gemini-3.5-flash-lite")
        self.assertTrue(provider.supports_model("gemini-3.5-flash-lite"))

    def test_gemini_preserves_thought_signature_and_hides_thought_text(self):
        from google.genai import types

        response_content = types.Content(
            role="model",
            parts=[
                types.Part(function_call=types.FunctionCall(
                    id="gem-call-1", name="read_file", args={"path": "x.md"}
                )),
                types.Part(text="internal thought", thought=True, thought_signature=b"signature-bytes"),
            ],
        )
        candidate = SimpleNamespace(content=response_content, finish_reason="STOP", grounding_metadata=None)
        fake_response = SimpleNamespace(candidates=[candidate], text="")
        captured = []

        def generate_content(**kwargs):
            captured.append(kwargs)
            return fake_response

        model_api = SimpleNamespace(generate_content=generate_content)
        provider = GeminiProvider("gemini-3.5-flash-lite")
        provider._verified = True
        provider._client = SimpleNamespace(models=model_api)
        turn = provider.generate_agent_turn(
            "Inspect x.md",
            [{"name": "read_file", "description": "Read", "parameters": {"type": "object", "properties": {}, "required": []}}],
        )
        self.assertEqual(turn.tool_calls[0].call_id, "gem-call-1")
        self.assertNotIn("internal thought", turn.text)
        preserved = turn.continuation["contents"][-1]
        self.assertIs(preserved, response_content)
        self.assertEqual(preserved.parts[1].thought_signature, b"signature-bytes")
        self.assertEqual(len(captured[0]["config"].tools), 1)
        self.assertEqual(
            captured[0]["config"].tools[0].function_declarations[0].name,
            "read_file",
        )

    def test_gemini_structured_output_and_grounding_metadata(self):
        from google.genai import types

        response = SimpleNamespace(text='{"status":"ok"}')
        provider = GeminiProvider("gemini-3.5-flash-lite")
        provider._verified = True
        provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
        parsed = provider.generate_structured(
            "Return status", {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}
        )
        self.assertEqual(parsed, {"status": "ok"})

        response_content = types.Content(role="model", parts=[types.Part(text="Answer")])
        candidate = SimpleNamespace(
            content=response_content,
            finish_reason="STOP",
            grounding_metadata=SimpleNamespace(
                grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri="https://example.org/source", title="Source"))]
            ),
        )
        captured = []

        def grounded_generate(**kwargs):
            captured.append(kwargs)
            return SimpleNamespace(candidates=[candidate], text="Answer")

        provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=grounded_generate))
        turn = provider.generate_agent_turn(
            "Search", [{"name": "google_search_grounding", "description": "Search", "parameters": {"type": "object", "properties": {}, "required": []}, "builtin": "google_search"}]
        )
        self.assertEqual(turn.sources[0]["url"], "https://example.org/source")
        search_tool = captured[0]["config"].tools[0]
        self.assertIsNotNone(search_tool.google_search)
        self.assertFalse(getattr(search_tool, "function_declarations", None))

    def test_gemini_missing_key_and_claude_local_stubs_are_honest(self):
        provider = GeminiProvider("gemini-3.5-flash-lite")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(GeminiProviderError) as captured:
                provider.check_available()
        self.assertEqual(captured.exception.category, "missing_key")
        with self.assertRaisesRegex(RuntimeError, "pas encore connecté"):
            ClaudeProvider().generate("hello")
        with self.assertRaisesRegex(RuntimeError, "n'est pas connecté"):
            LocalProvider().generate("hello")

    def test_gemini_retries_a_transient_service_error_with_a_bound(self):
        provider = GeminiProvider("gemini-3.5-flash-lite")
        provider._verified = True
        attempts = []

        class TemporaryServiceError(Exception):
            status_code = 503

        def generate_content(**kwargs):
            attempts.append(kwargs)
            if len(attempts) < 3:
                raise TemporaryServiceError()
            return SimpleNamespace(text="recovered")

        provider._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        with patch("providers.gemini.time.sleep"):
            self.assertEqual(provider.generate("hello"), "recovered")
        self.assertEqual(len(attempts), 3)

    def test_gemini_partial_turn_and_streaming_interface(self):
        from google.genai import types

        content = types.Content(role="model", parts=[types.Part(text="partial")])
        candidate = SimpleNamespace(content=content, finish_reason="MAX_TOKENS", grounding_metadata=None)
        calls = []

        def generate_content(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(candidates=[candidate], text="partial")

        provider = GeminiProvider("gemini-3.5-flash-lite")
        provider._verified = True
        provider._client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content,
                generate_content_stream=lambda **kwargs: [
                    SimpleNamespace(text="one "), SimpleNamespace(text="two")
                ],
            )
        )
        turn = provider.generate_agent_turn("continue", [])
        self.assertTrue(turn.partial)
        self.assertEqual(turn.text, "partial")
        self.assertEqual(calls[0]["config"].http_options.timeout, 90_000)
        self.assertEqual("".join(provider.generate_stream("stream")), "one two")

    def test_ollama_native_tool_call_is_parsed_without_network(self):
        from providers import ollama as ollama_module

        payload = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "notes.md"}}}],
            },
            "done_reason": "length",
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode()

        provider = OllamaProvider()
        provider._verified = True
        with patch.object(ollama_module, "urlopen", return_value=FakeResponse()):
            turn = provider.generate_agent_turn(
                "Read the note",
                [{"name": "read_file", "description": "Read", "parameters": {"type": "object", "properties": {}}}],
            )
        self.assertEqual(turn.tool_calls[0].name, "read_file")
        self.assertEqual(turn.tool_calls[0].arguments["path"], "notes.md")
        self.assertTrue(turn.partial)


if __name__ == "__main__":
    unittest.main()
