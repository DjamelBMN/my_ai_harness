# RÔLE DE CE FICHIER :
# Suite de tests complète pour l'interface agentique NeoHarness AI (Operating Environment).
# Couvre les 27 scénarios obligatoires (Section 50) et le test critique en 12 étapes
# sur Gemini Flash (Section 51), sans appel réseau payant.

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen

from core.event_bus import NormalizedEventBus
from core.events import HarnessEvent
from core.model_registry import ModelCapabilityRegistry
from core.skill_compatibility import SkillCompatibilityEngine
from providers.base_provider import AgentTurn
from ui.server import NeoHarnessRuntimeBridge, NeoHarnessUIApp, create_http_server


class FakeGeminiFlashProvider:
    """Fournisseur de test déterministe représentant Gemini Flash sans appel réseau."""

    def __init__(self, model: str = "gemini-3.8-flash") -> None:
        self.model = model
        self.max_output_tokens = None
        self.prompts: list[str] = []

    def generate(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        return "Réponse analytique générée par Gemini Flash."

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None) -> AgentTurn:
        if prompt:
            self.prompts.append(prompt)
        return AgentTurn(
            text="Mission accomplie et vérifiée par Gemini Flash.",
            tool_calls=[],
            continuation={"thought_signature": "SECRET_INTERNAL_SIGNATURE_DO_NOT_LEAK"},
            sources=[{"url": "https://example.edu/math-programme", "title": "Programme officiel"}],
        )

    def execute(self, instruction: str = "") -> str:
        return "Non applicable"

    def get_name(self) -> str:
        return "GeminiProvider"

    def get_model_name(self) -> str:
        return self.model

    def get_status_label(self) -> str:
        return "[RÉEL]"


class NeoHarnessUIEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        (self.workspace / "notes.md").write_text(
            "# Projet NeoHarness\nDocumentation de test pour RAG et analyse.\n",
            encoding="utf-8",
        )
        self.bridge = NeoHarnessRuntimeBridge(workspace=self.workspace)
        self.app = NeoHarnessUIApp(self.bridge)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_application_startup_and_full_state(self) -> None:
        """1. Démarrage de l'application et récupération de l'état complet."""
        status, state = self.app.handle_api_get("/api/state", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(state["app_name"], "NeoHarness AI")
        self.assertIn("models", state)
        self.assertIn("compatibility", state)
        self.assertIn("agents", state)
        self.assertIn("tools", state)
        self.assertIn("memory", state)
        self.assertIn("rag", state)

    def test_02_preservation_of_existing_routes_and_contracts(self) -> None:
        """2. Préservation des routes du ModelRouter et contrats Orchestrator."""
        router = self.bridge.orchestrator.router
        self.assertIn("coder", router.agent_provider_map)
        self.assertIn("researcher", router.agent_provider_map)
        self.assertIn("coding:complex", router.task_provider_map)
        self.assertIn("research:complex", router.task_provider_map)
        self.assertTrue(callable(self.bridge.orchestrator.run))
        self.assertTrue(callable(self.bridge.orchestrator.run_agentic))

    def test_03_conversation_lifecycle_crud(self) -> None:
        """3. Création, épinglage, renommage, archivage et suppression d'une conversation."""
        status, created = self.app.handle_api_post(
            "/api/conversations/create",
            {"title": "Audit Architecture", "project": "NeoHarness AI"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        cid = created["conversation"]["id"]
        self.assertEqual(created["conversation"]["title"], "Audit Architecture")

        status, updated = self.app.handle_api_post(
            "/api/conversations/update",
            {"id": cid, "title": "Audit Renommé", "pinned": True, "archived": True},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(updated["conversation"]["title"], "Audit Renommé")
        self.assertTrue(updated["conversation"]["pinned"])
        self.assertTrue(updated["conversation"]["archived"])

        status, deleted = self.app.handle_api_post("/api/conversations/delete", {"id": cid})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(deleted["deleted"]["id"], cid)

    def test_04_send_message_and_execute_plan_skill(self) -> None:
        """4. Envoi d'un message (slash et message chat standard) et exécution réelle via le moteur."""
        status, res = self.app.handle_api_post(
            "/api/tasks/run",
            {"prompt": "/plan Construire un module de validation Python"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(res["status"], "Terminé")
        self.assertIn("[PLAN — PRÉVISUALISATION", res["assistant_message"]["content"])
        self.assertEqual(res["assistant_message"]["skill"], "plan")

        # Test d'un message de chat standard (sans commande slash)
        fake_gemini = FakeGeminiFlashProvider()
        self.bridge.orchestrator.router.providers["gemini"] = fake_gemini
        self.bridge.select_model("gemini")
        status_chat, res_chat = self.app.handle_api_post(
            "/api/tasks/run",
            {"prompt": "Bonjour, explique le rôle du projet NeoHarness AI"},
        )
        self.assertEqual(status_chat, HTTPStatus.OK)
        self.assertEqual(res_chat["status"], "Terminé")
        self.assertIn("Gemini Flash", res_chat["assistant_message"]["content"])
        self.assertNotIn("AttributeError", res_chat["assistant_message"]["content"])

    def test_05_real_projects_only(self) -> None:
        """5. Sélection et affichage uniquement des projets réellement présents."""
        (self.workspace / "mon_sous_projet").mkdir()
        projects = self.bridge.list_projects()
        names = [p["name"] for p in projects]
        self.assertIn("NeoHarness AI", names)
        self.assertIn("mon_sous_projet", names)
        self.assertNotIn("FakeSaaSProject", names)

    def test_06_to_12_critical_gemini_flash_12_step_scenario(self) -> None:
        """6-12 & Section 51. Scénario critique en 12 étapes pour Gemini Flash."""
        # Étape 1 : Ouvrir le sélecteur de modèles (/api/models)
        status, models_payload = self.app.handle_api_get("/api/models", {})
        self.assertEqual(status, HTTPStatus.OK)
        model_ids = [m["id"] for m in models_payload["models"]]
        self.assertIn("gemini", model_ids)

        # Étape 2 : Sélectionner Gemini Flash
        status, select_res = self.app.handle_api_post(
            "/api/models/select",
            {"model": "Gemini Flash"},
        )
        self.assertEqual(status, HTTPStatus.OK)

        # Étape 3 : Vérifier que le modèle actif devient Gemini Flash
        selection = select_res["selection"]
        self.assertEqual(selection["mode"], "manual")
        self.assertEqual(selection["selected_id"], "gemini")
        self.assertIn("Gemini Flash", selection["effective_model"]["display_name"])

        # Étape 4 : Vérifier que ses capacités réelles sont chargées
        caps = selection["effective_model"]["capabilities"]
        self.assertTrue(caps["vision"])
        self.assertTrue(caps["long_context"])
        self.assertTrue(caps["tools"])
        self.assertTrue(caps["structured_output"])
        self.assertTrue(caps["web_grounding"])
        self.assertTrue(caps["streaming"])
        self.assertEqual(caps["context"], 1048576)

        # Étape 5 : Vérifier que les Skills compatibles avec Gemini Flash s'affichent
        compat = select_res["compatibility"]
        avail_names = {s["name"] for s in compat["available_skills"]}
        for expected_skill in (
            "analyze",
            "auto",
            "bacblanc",
            "debug",
            "diagnostic",
            "export",
            "memory",
            "mode",
            "model",
            "plan",
            "refactor",
            "research",
            "review",
            "route",
            "test",
            "workflow",
        ):
            self.assertIn(expected_skill, avail_names)

        domain_labels = {
            d["label"]: d["available"] for d in compat["domain_capabilities"]
        }
        self.assertTrue(domain_labels["Web Research"])
        self.assertTrue(domain_labels["Document Analysis"])
        self.assertTrue(domain_labels["Mathematics"])
        self.assertTrue(domain_labels["PDF & Bureautique"])
        self.assertTrue(domain_labels["Coding & Debugging"])
        self.assertTrue(domain_labels["RAG & Templates"])

        # Étape 6 : Vérifier que les Skills incompatibles sont marqués indisponibles
        # Si un seul provider est chargé, /compare doit être marqué indisponible_session
        self.bridge.orchestrator.router.providers = {
            "gemini": FakeGeminiFlashProvider("gemini-3.8-flash")
        }
        single_compat = self.bridge.skill_compatibility.evaluate_for_model("Gemini Flash")
        unavail_names = {s["name"] for s in single_compat["unavailable_skills"]}
        self.assertIn("compare", unavail_names)

        # Étape 7 : Vérifier qu'aucun Skill inexistant n'apparaît
        real_disk_skills = set(self.bridge.orchestrator.skill_registry.names)
        reported_skills = {s["name"] for s in single_compat["skills"]}
        self.assertEqual(real_disk_skills, reported_skills)
        self.assertNotIn("computer_use", reported_skills)
        self.assertNotIn("powerpoint_designer_fake", reported_skills)

        # Étape 8 : Sélectionner un Skill compatible (ex: research)
        self.app.handle_api_post(
            "/api/preferences",
            {"skill_mode": "manual", "active_skills": ["research"]},
        )
        self.assertEqual(self.bridge.generation_preferences["active_skills"], ["research"])

        # Étape 9 : Envoyer une tâche avec le FakeGeminiFlashProvider connecté
        status, run_res = self.app.handle_api_post(
            "/api/tasks/run",
            {"prompt": "Analyse les tendances du programme de mathématiques"},
        )
        self.assertEqual(status, HTTPStatus.OK)

        # Étape 10 : Vérifier dans l'activité et l'inspector que Modèle, Skill et Tools correspondent au réel
        assistant_msg = run_res["assistant_message"]
        self.assertEqual(assistant_msg["skill"], "research")
        self.assertEqual(assistant_msg["model"], "gemini-3.8-flash")
        self.assertIn("Mission accomplie et vérifiée par Gemini Flash.", assistant_msg["content"])
        # Aucune fuite de thought_signature dans les événements ou le message
        serialized = json.dumps(run_res, ensure_ascii=False)
        self.assertNotIn("SECRET_INTERNAL_SIGNATURE_DO_NOT_LEAK", serialized)

        # Étape 11 : Changer vers un autre modèle (ex: Claude non connecté, puis OpenAI gpt-5-mini)
        _, claude_res = self.app.handle_api_post("/api/models/select", {"model": "claude"})
        claude_compat = claude_res["compatibility"]
        claude_unavail = {s["name"] for s in claude_compat["unavailable_skills"]}

        # Étape 12 : Vérifier que la liste des Skills est recalculée correctement et que le Skill manuel incompatible a été désactivé
        self.assertIn("research", claude_unavail)
        self.assertIn("bacblanc", claude_unavail)
        self.assertIn("debug", claude_unavail)
        # Les commandes purement locales restent disponibles même si Claude n'est pas connecté
        claude_avail = {s["name"] for s in claude_compat["available_skills"]}
        self.assertIn("plan", claude_avail)
        self.assertIn("diagnostic", claude_avail)
        # Le Skill manuel 'research' a été automatiquement retiré car incompatible avec Claude
        self.assertEqual(self.bridge.generation_preferences["active_skills"], [])

        # Et sur OpenAI (gpt-5-mini), Web Research (via web_search) et Coding sont tous deux disponibles
        _, openai_res = self.app.handle_api_post("/api/models/select", {"model": "openai"})
        openai_domains = {
            d["label"]: d["available"] for d in openai_res["compatibility"]["domain_capabilities"]
        }
        self.assertTrue(openai_domains["Web Research"])
        self.assertTrue(openai_domains["Coding & Debugging"])

    def test_13_real_agents_and_tools_inspection(self) -> None:
        """12 & 13. Affichage des Agents réels (5) et des Tools réels (17 dont web_search)."""
        agents = self.bridge.list_agents()
        agent_names = {a["name"] for a in agents}
        self.assertEqual(
            agent_names,
            {"CodeAgent", "ResearchAgent", "ReviewAgent", "TestAgent", "BacBlancAgent"},
        )

        tools = self.bridge.list_tools()
        tool_names = {t["name"] for t in tools}
        self.assertEqual(len(tools), 17)
        self.assertIn("web_search", tool_names)
        self.assertIn("read_document", tool_names)
        self.assertIn("write_file", tool_names)
        self.assertIn("run_tests", tool_names)
        self.assertIn("git_status", tool_names)

    def test_14_normalized_activity_events_and_no_cot_leak(self) -> None:
        """14 & 27. Événements normalisés réels et absence de fuite de chaîne de pensée."""
        bus = NormalizedEventBus()
        tid = bus.start_task(objective="Vérifier les fichiers", skill="analyze", mode="ACCEPT")
        bus.handle_harness_event(
            HarnessEvent(
                "tool.started",
                {"tool": "read_file", "agent": "ResearchAgent", "thought_signature": "PRIVATE_COT"},
            )
        )
        bus.handle_harness_event(
            HarnessEvent("tool.completed", {"tool": "read_file", "status": "success"})
        )
        bus.complete_task(status="completed", duration_ms=42)

        events = bus.list_events(task_id=tid)
        event_types = [e["event"] for e in events]
        self.assertEqual(
            event_types,
            ["TASK_STARTED", "TOOL_CALL", "TOOL_RESULT", "TASK_COMPLETED"],
        )
        dump = json.dumps(events)
        self.assertNotIn("PRIVATE_COT", dump)

    def test_15_and_16_files_modified_and_diff_viewer(self) -> None:
        """15 & 16. Suivi des fichiers créés/modifiés et génération de diffs unifiés."""
        before = self.bridge._snapshot_workspace()
        self.bridge.filesystem.write_file(
            "notes.md",
            "# Projet NeoHarness\nLigne modifiée par CodeAgent.\nNouvelle ligne ajoutée.\n",
            overwrite=True,
        )
        self.bridge.filesystem.write_file("nouveau.py", "print('ok')\n", overwrite=False)
        after = self.bridge._snapshot_workspace()

        diffs = self.bridge._record_workspace_diffs(
            before, after, agent="CodeAgent", skill="refactor", tool="write_file"
        )
        by_path = {d["path"]: d for d in diffs}
        self.assertIn("notes.md", by_path)
        self.assertEqual(by_path["notes.md"]["status"], "M")
        self.assertGreaterEqual(by_path["notes.md"]["added_lines"], 2)
        self.assertIn("+Ligne modifiée par CodeAgent.", by_path["notes.md"]["diff"])

        self.assertIn("nouveau.py", by_path)
        self.assertEqual(by_path["nouveau.py"]["status"], "+")

    def test_17_memory_ui_scopes_and_honest_unconfigured_scopes(self) -> None:
        """17. Gestion de la mémoire (session, décision, préférence) et portées non configurées."""
        self.app.handle_api_post(
            "/api/memory",
            {"action": "remember", "scope": "session", "value": "Focus sur l'architecture modulaire"},
        )
        self.app.handle_api_post(
            "/api/memory",
            {"action": "remember", "scope": "decision", "value": "Conserver config/config.yaml intact"},
        )
        self.app.handle_api_post(
            "/api/memory",
            {"action": "remember", "scope": "preference", "value": "langue=fr"},
        )
        mem = self.bridge.get_memory_state()
        self.assertIn("Focus sur l'architecture modulaire", mem["session"])
        self.assertIn("Conserver config/config.yaml intact", mem["decisions"])
        self.assertEqual(mem["preferences"].get("langue"), "fr")
        self.assertEqual(mem["long_term"]["status"], "Non configuré")
        self.assertEqual(mem["procedural"]["status"], "Non configuré")

        self.app.handle_api_post("/api/memory", {"action": "clear_session"})
        self.assertEqual(self.bridge.get_memory_state()["session"], [])

    def test_18_rag_inspector_and_search(self) -> None:
        """18. Inspection du RAG réel (templates BacBlanc + Workspace) et recherche."""
        rag = self.bridge.get_rag_state(query="Documentation de test")
        self.assertFalse(rag["embeddings"]["configured"])
        self.assertEqual(rag["embeddings"]["status"], "Non configuré")
        col_ids = {c["id"] for c in rag["collections"]}
        self.assertIn("skill:bacblanc", col_ids)
        self.assertIn("workspace", col_ids)
        self.assertGreaterEqual(len(rag["search_results"]), 1)
        self.assertEqual(rag["search_results"][0]["source"], "workspace/notes.md")

    def test_19_global_search_ctrl_k(self) -> None:
        """19. Recherche globale multi-entités (Modèles, Skills, Agents, Tools, Fichiers)."""
        res = self.bridge.global_search("bacblanc")
        self.assertTrue(any(s["name"] == "bacblanc" for s in res["skills"]))
        self.assertTrue(any(a["name"] == "BacBlancAgent" for a in res["agents"]))

    def test_20_to_23_http_server_static_assets_and_layout_elements(self) -> None:
        """20-23. Serveur HTTP local, intégrité HTML/CSS/JS, Sidebar/Inspector/Responsive."""
        server = create_http_server(host="127.0.0.1", port=0, app=self.app)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
                html = resp.read().decode("utf-8")
            self.assertIn("NeoHarness AI", html)
            self.assertIn('id="left-sidebar"', html)
            self.assertIn('id="right-inspector"', html)
            self.assertIn('id="btn-toggle-sidebar"', html)
            self.assertIn('id="btn-toggle-inspector"', html)
            self.assertIn('id="modal-global-search"', html)

            with urlopen(f"http://127.0.0.1:{port}/styles.css", timeout=5) as resp:
                css = resp.read().decode("utf-8")
            self.assertIn("@media (max-width: 1024px)", css)
            self.assertIn("--bg-primary: #0B0D10", css)

            with urlopen(f"http://127.0.0.1:{port}/api/state?model=Gemini%20Flash", timeout=5) as resp:
                state_json = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(state_json["compatibility"]["model"]["id"], "gemini")
        finally:
            server.shutdown()
            server.server_close()

    def test_24_human_in_the_loop_approval_workflow(self) -> None:
        """Validation humaine temps réel (Autoriser une fois / toujours / refuser)."""
        from core.permissions import RiskLevel

        decision_holder: list[bool] = []

        def _ask() -> None:
            allowed = self.bridge._confirm_tool_action("write_file", RiskLevel.MODERATE)
            decision_holder.append(allowed)

        t = threading.Thread(target=_ask)
        t.start()

        # Attendre que la demande d'approbation apparaisse
        for _ in range(50):
            pending = self.bridge.list_pending_approvals()
            if pending:
                break
            import time

            time.sleep(0.02)

        pending = self.bridge.list_pending_approvals()
        self.assertEqual(len(pending), 1)
        aid = pending[0]["id"]
        self.bridge.resolve_approval(aid, "allow_once")
        t.join(timeout=2.0)
        self.assertEqual(decision_holder, [True])

    def test_25_minimalist_ui_and_no_fake_planner_events_on_local_commands(self) -> None:
        """25. Inspecteur fermé par défaut, absence de barre horizontale de 18 pills et zéro faux événement Planner sur /export."""
        html_path = Path(__file__).resolve().parent.parent / "ui" / "static" / "index.html"
        html = html_path.read_text(encoding="utf-8")
        self.assertIn('id="right-inspector" class="inspector collapsed"', html)
        self.assertNotIn('id="composer-skill-pills"', html)
        self.assertIn('id="composer-skill-select"', html)

        # Produire un résultat initial via /diagnostic, puis lancer /export pdf et vérifier l'absence de PLANNER_STARTED
        self.app.handle_api_post("/api/tasks/run", {"prompt": "/diagnostic"})
        status, exp_res = self.app.handle_api_post("/api/tasks/run", {"prompt": "/export pdf"})
        self.assertEqual(status, HTTPStatus.OK)
        event_names = [e["event"] for e in exp_res["assistant_message"]["events"]]
        self.assertNotIn("PLANNER_STARTED", event_names)
        self.assertNotIn("PLAN_CREATED", event_names)

    def test_26_web_search_controlled_failure_and_honest_error(self) -> None:
        """26. Échec contrôlé de web_search sans simulation et statut honnête Erreur si fournisseur indisponible."""
        from tools.search import web_search

        with self.assertRaises(RuntimeError):
            web_search("test query", backend_enabled=False)

        # Sélectionner un modèle non connecté (Claude sans clé API) et vérifier le statut honnête Erreur
        self.app.handle_api_post("/api/models/select", {"model": "claude"})
        status, err_res = self.app.handle_api_post(
            "/api/tasks/run", {"prompt": "Analyse le fichier notes.md"}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(err_res["assistant_message"]["status"], "Erreur")

    def test_27_regression_task_string_normalization_no_attribute_error_description(self) -> None:
        """27. Régression : aucune chaîne brute passée à Planner, Orchestrator ou AgentLoop ne lève AttributeError (.description)."""
        from core.task import Task, ensure_task
        from core.task_state import PlanStep, TaskState

        t = ensure_task("Explique le théorème de Pythagore", mode="AUTO")
        self.assertIsInstance(t, Task)
        self.assertEqual(t.description, "Explique le théorème de Pythagore")

        # Planner.plan accepte directement une chaîne brute
        planned = self.bridge.agent_loop.planner.plan("Explique le théorème de Pythagore")
        self.assertEqual(planned.objective, "Explique le théorème de Pythagore")
        self.assertTrue(all(isinstance(s, PlanStep) for s in planned.plan))

        # TaskState normalise automatiquement une liste de chaînes dans plan
        ts = TaskState(user_request="test", plan=["Étape A", "Étape B"])  # type: ignore[arg-type]
        self.assertTrue(all(isinstance(s, PlanStep) for s in ts.plan))
        self.assertEqual(ts.plan[0].description, "Étape A")

        # Orchestrator.run_agentic accepte une chaîne brute avec gemini-flash-lite-latest
        fake_lite = FakeGeminiFlashProvider("gemini-flash-lite-latest")
        self.bridge.orchestrator.router.providers["gemini_flash_lite"] = fake_lite
        self.bridge.select_model("gemini_flash_lite")
        result = self.bridge.orchestrator.run_agentic("Question simple pour Gemini Flash Lite", self.bridge.agent_loop)
        self.assertIn(result.status, {"answered", "verified"})
        self.assertIn("Gemini Flash", result.answer)

    def test_28_canonical_18_skills_order_and_slash_palette_markup(self) -> None:
        """28. Ordre canonique strict des skills (avec éducation : bacblanc, exercice, dm) dans SkillRegistry et /api/skills."""
        expected_canonical = [
            "analyze",
            "auto",
            "bacblanc",
            "compare",
            "context",
            "debug",
            "diagnostic",
            "dm",
            "exercice",
            "export",
            "memory",
            "mode",
            "model",
            "plan",
            "refactor",
            "research",
            "review",
            "route",
            "test",
            "workflow",
        ]
        self.assertEqual(self.bridge.orchestrator.skill_registry.names, expected_canonical)
        status, payload = self.app.handle_api_get("/api/skills", {})
        self.assertEqual(status, HTTPStatus.OK)
        skills = payload["skills"]
        self.assertEqual([s["name"] for s in skills], expected_canonical)
        self.assertEqual([s["canonical_index"] for s in skills], list(range(1, len(expected_canonical) + 1)))

    def test_29_tectonic_latex_compilation_auto_repair_and_error_handling(self) -> None:
        """29. Compilation LaTeX réelle via Tectonic, auto-réparation et gestion d'erreur sans PDF obsolète."""
        # 1. Compilation d'un fichier .tex valide
        valid_tex = (
            "\\documentclass[12pt,a4paper]{article}\n"
            "\\usepackage{amsmath}\n"
            "\\begin{document}\n"
            "\\section*{Sujet NeoHarness}\n"
            "Formule : $E = mc^2$.\n"
            "\\end{document}\n"
        )
        self.bridge.filesystem.write_file("valid_doc.tex", valid_tex, overwrite=True)
        status, comp1 = self.app.handle_api_post("/api/files/compile-latex", {"path": "valid_doc.tex"})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(comp1["status"], "success")
        self.assertEqual(comp1["compiler"], "tectonic")
        self.assertEqual(comp1["pdf_path"], "valid_doc.pdf")
        self.assertGreaterEqual(comp1["page_count"], 1)
        pdf_bytes = self.bridge.filesystem.read_bytes("valid_doc.pdf")
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

        # 2. Auto-réparation d'un fichier .tex incomplet (sans \documentclass ni \end{document})
        broken_tex = "\\section*{Document Réparé}\nIntégrale : $\\int_0^1 x^2 dx = \\frac{1}{3}$."
        self.bridge.filesystem.write_file("repaired_doc.tex", broken_tex, overwrite=True)
        status2, comp2 = self.app.handle_api_post(
            "/api/files/compile-latex", {"path": "repaired_doc.tex", "auto_repair": True}
        )
        self.assertEqual(status2, HTTPStatus.OK)
        self.assertEqual(comp2["status"], "success")
        self.assertTrue(comp2["auto_repaired"])
        self.assertTrue(self.bridge.filesystem.read_bytes("repaired_doc.pdf").startswith(b"%PDF-"))

        # 3. Échec contrôlé sans auto-réparation sur une commande LaTeX invalide : aucun PDF obsolète ne doit subsister
        invalid_tex = "\\documentclass{article}\n\\begin{document}\n\\commandeTotalementInexistanteXYZ\n\\end{document}\n"
        self.bridge.filesystem.write_file("fail_doc.tex", invalid_tex, overwrite=True)
        status3, comp3 = self.app.handle_api_post(
            "/api/files/compile-latex", {"path": "fail_doc.tex", "auto_repair": False}
        )
        self.assertEqual(status3, HTTPStatus.BAD_REQUEST)
        self.assertEqual(comp3["status"], "error")
        self.assertFalse(self.bridge.filesystem.resolve("fail_doc.pdf").exists())

    def test_30_html_preview_sandbox_serving_and_origin_null_post_protection(self) -> None:
        """30. Écriture et service d'aperçu HTML sandboxé + blocage des requêtes POST Origin: null."""
        html_code = "<!DOCTYPE html><html><body><h1 id='title'>Aperçu NeoHarness</h1></body></html>"
        status, write_res = self.app.handle_api_post(
            "/api/files/write", {"path": "demo/app.html", "content": html_code}
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(write_res["artifact"]["type"], "html")

        server = create_http_server(host="127.0.0.1", port=0, app=self.app)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/preview/workspace/demo/app.html", timeout=5) as resp:
                served_html = resp.read().decode("utf-8")
                cors_hdr = resp.headers.get("Access-Control-Allow-Origin")
            self.assertIn("Aperçu NeoHarness", served_html)
            self.assertEqual(cors_hdr, "*")

            # Vérifier qu'une requête POST avec Origin: null (provenant d'un iframe sandboxé) est rejetée en 403
            req = Request(
                f"http://127.0.0.1:{port}/api/tasks/run",
                data=b'{"prompt": "/diagnostic"}',
                headers={"Content-Type": "application/json", "Origin": "null"},
                method="POST",
            )
            with self.assertRaises(Exception) as ctx:
                urlopen(req, timeout=5)
            self.assertTrue(
                "403" in str(ctx.exception)
                or getattr(ctx.exception, "code", None) == 403
                or isinstance(ctx.exception, (urllib.error.HTTPError, ConnectionResetError))
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_31_default_light_theme_and_gpt_voice_dictation_markup(self) -> None:
        """31. Mode clair par défaut, palette Slash Commands, dictée vocale GPT et panneau d'aperçu PDF/HTML."""
        root = Path(__file__).resolve().parent.parent / "ui" / "static"
        html = (root / "index.html").read_text(encoding="utf-8")
        css = (root / "styles.css").read_text(encoding="utf-8")
        js = (root / "app.js").read_text(encoding="utf-8")

        self.assertIn('<html lang="fr" data-theme="light">', html)
        self.assertIn('id="slash-command-palette"', html)
        self.assertIn('id="btn-voice-dictate"', html)
        self.assertIn('id="voice-dictation-bar"', html)
        self.assertIn('id="voice-waveform-canvas"', html)
        self.assertIn('id="doc-preview-container"', html)
        self.assertIn('id="doc-pdf-frame"', html)
        self.assertIn('id="doc-html-frame"', html)
        self.assertIn('sandbox="allow-scripts"', html)
        self.assertIn("--bg-primary: #FBF9F6", css)
        self.assertIn("--accent: #18181B", css)
        self.assertIn("getUserMedia", js)
        self.assertIn("createAnalyser", js)

    def test_32_markdown_bullet_and_asterisk_formatting_regression(self) -> None:
        """32. Rendu propre du Markdown : conversion des listes à puces (*, -, +, •), suppression des astérisques parasites et puces natives."""
        root = Path(__file__).resolve().parent.parent / "ui" / "static"
        js = (root / "app.js").read_text(encoding="utf-8")
        css = (root / "styles.css").read_text(encoding="utf-8")

        # 1. Vérification dans app.js du support des listes (*, -, +, •) et de l'assainissement des astérisques orphelins
        self.assertIn("[-*+•]", js)
        self.assertIn("ulMatch", js)
        self.assertIn("olMatch", js)
        self.assertIn("closeList", js)
        self.assertIn("<hr />", js)

        # 2. Vérification dans styles.css de la typographie des listes et des marqueurs
        self.assertIn(".md-prose ul {", css)
        self.assertIn("list-style-type: disc;", css)
        self.assertIn(".md-prose ol {", css)
        self.assertIn("list-style-type: decimal;", css)
        self.assertIn(".md-prose li::marker {", css)

        # 3. Exécution réelle avec Node.js d'un cas de test pour s'assurer de l'absence totale d'astérisque brut dans les puces
        node_script = """
        const fs = require('fs');
        const code = fs.readFileSync('""" + str(root / "app.js").replace("\\", "/") + """', 'utf-8');
        // Extraire formatAssistantContent et ses fonctions auxiliaires
        const ctx = { window: {}, esc: s => s };
        const fnBlock = code.match(/function esc[\\s\\S]*?function formatAssistantContent[\\s\\S]*?\\n  \\}/)[0];
        eval(fnBlock);
        const raw = `1. Les belligérants et alliances\\n\\n* **Les Puissances de l'Axe** : Menées par l'Allemagne.\\n* **Les Alliés** : Composés de la France.\\n\\n2. Phases du conflit`;
        const html = formatAssistantContent(raw);
        if (html.includes('<p>*') || html.includes('>*<')) {
            process.exit(1);
        }
        if (!html.includes('<ul><li><strong>Les Puissances') || !html.includes('<li><strong>Les Alliés')) {
            process.exit(2);
        }
        process.exit(0);
        """
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Erreur de rendu Markdown JS: {proc.stderr} {proc.stdout}")


if __name__ == "__main__":
    unittest.main()
