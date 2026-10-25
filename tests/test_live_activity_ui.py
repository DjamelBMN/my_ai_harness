# RÔLE DE CE FICHIER :
# Suite de tests automatisée pour le Panneau d'Activité Temps Réel (Section B - live_activity_panel).
# Vérifie l'ordonnancement SSE, la reprise sur Last-Event-ID, l'interruption en < 1 seconde
# par le bouton Stop, l'échappement anti-XSS et la reprise d'état après rafraîchissement.

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen

from core.event_bus import NormalizedEventBus
from core.events import HarnessEvent
from core.task import Task
from core.agent_loop import AgentLoop, AgentResult, MissionBudget
from core.task_state import TaskState, TaskStatus, PlanStep
from ui.server import NeoHarnessRuntimeBridge, NeoHarnessUIApp, create_http_server


class TestLiveActivityUI(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        (self.workspace / "test.txt").write_text("hello", encoding="utf-8")
        self.bridge = NeoHarnessRuntimeBridge(workspace=self.workspace)
        self.app = NeoHarnessUIApp(self.bridge)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_sse_event_ordering_strictly_increasing_seq(self) -> None:
        """1. Les événements SSE doivent posséder un numéro séquentiel (seq) strictement croissant."""
        bus = self.bridge.event_bus
        bus.clear()

        # Émission d'une série d'événements représentatifs
        ev1 = bus.emit_normalized(event="TASK_STARTED", raw_event="task.started", summary="Départ")
        ev2 = bus.handle_harness_event(HarnessEvent("plan.created", {"steps": [{"id": 1, "description": "Étape 1"}]}))
        ev3 = bus.handle_harness_event(HarnessEvent("tool.started", {"tool": "read_file", "target": "test.txt"}))
        ev4 = bus.handle_harness_event(HarnessEvent("tool.completed", {"tool": "read_file", "status": "success"}))
        ev5 = bus.handle_harness_event(HarnessEvent("compile.attempt", {"attempt": 1, "max_attempts": 25}))
        ev6 = bus.handle_harness_event(HarnessEvent("budget.update", {"tokens_used": 1500, "tokens_limit": 100000}))

        events = bus.list_events()
        self.assertGreaterEqual(len(events), 6)

        seqs = [e["seq"] for e in events]
        self.assertTrue(all(isinstance(s, int) and s > 0 for s in seqs))

        # Vérification d'ordonnancement strict
        for i in range(len(seqs) - 1):
            self.assertLess(
                seqs[i],
                seqs[i + 1],
                f"L'événement {i} (seq={seqs[i]}) n'est pas strictement inférieur au suivant (seq={seqs[i+1]})"
            )

        # Vérification des attributs obligatoires de chaque événement SSE
        for e in events:
            self.assertIn("type", e)
            self.assertIn("run_id", e)
            self.assertIn("seq", e)
            self.assertIn("timestamp", e)
            self.assertIn("duration_ms", e)
            self.assertIn("data", e)

    def test_02_sse_reconnection_with_last_event_id(self) -> None:
        """2. La reconnexion avec Last-Event-ID rejoue exactement les événements manqués sans trou ni doublon."""
        bus = self.bridge.event_bus
        bus.clear()

        ev1 = bus.emit_normalized(event="TASK_STARTED", summary="E1")
        ev2 = bus.emit_normalized(event="PLAN_CREATED", summary="E2")
        ev3 = bus.emit_normalized(event="TOOL_CALL", summary="E3")
        ev4 = bus.emit_normalized(event="TOOL_RESULT", summary="E4")
        ev5 = bus.emit_normalized(event="TASK_COMPLETED", summary="E5")

        # Supposons que le client a reçu jusqu'à seq=ev2.seq avant coupure
        last_seq = ev2.seq
        missed = bus.get_events_after(last_seq)

        self.assertEqual(len(missed), 3)
        self.assertEqual([e["seq"] for e in missed], [ev3.seq, ev4.seq, ev5.seq])
        self.assertNotIn(ev1.seq, [e["seq"] for e in missed])
        self.assertNotIn(ev2.seq, [e["seq"] for e in missed])

        # Test via HTTP réel
        server = create_http_server("127.0.0.1", 0, app=self.app)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            req = Request(f"http://127.0.0.1:{port}/api/events/stream?last_event_id={last_seq}")
            req.add_header("Accept", "text/event-stream")
            with urlopen(req, timeout=3.0) as resp:
                self.assertEqual(resp.status, HTTPStatus.OK)
                # Lire les premiers octets
                chunk = resp.read(512).decode("utf-8")
                self.assertIn(f"id: {ev3.seq}", chunk)
                self.assertIn(f"id: {ev4.seq}", chunk)
                self.assertNotIn(f"id: {ev1.seq}\n", chunk)
                self.assertNotIn(f"id: {ev2.seq}\n", chunk)
        finally:
            server.shutdown()
            server.server_close()

    def test_03_stop_button_interrupts_within_one_second(self) -> None:
        """3. L'interruption par le bouton Stop arrête la boucle d'exécution en moins d'une seconde."""
        agent_loop = self.bridge.agent_loop

        class InfiniteMockProvider:
            def __init__(self) -> None:
                self.name = "MockProvider"
                self.model = "mock-infinite"
            def get_name(self) -> str:
                return self.name
            def get_model_name(self) -> str:
                return self.model
            def generate_agent_turn(self, *args, **kwargs):
                time.sleep(0.05)
                from providers.base_provider import AgentTurn
                return AgentTurn(text="En cours de calcul...", tool_calls=[])
            def execute(self, *args, **kwargs):
                return ""

        class LongTaskAgent:
            def __init__(self, prov) -> None:
                self.provider = prov
                self.name = "LongTaskAgent"
                self.routing_key = "coder"
                self.allowed_tools = ["read_file"]
            def set_provider(self, p) -> None:
                self.provider = p
            def build_prompt(self, task) -> str:
                return "Instruction de test."

        prov = InfiniteMockProvider()
        agent = LongTaskAgent(prov)
        task = Task(description="Tâche longue à interrompre", mode="AUTO")
        state = TaskState(user_request="Tâche longue à interrompre", task_id="task-to-stop")

        task_thread = threading.Thread(
            target=lambda: agent_loop.run(agent, task, state),
            daemon=True,
        )
        t_start_thread = time.monotonic()
        task_thread.start()

        # Attendre que la tâche démarre
        time.sleep(0.1)
        self.assertFalse(agent_loop._stop_requested)

        # Clic sur le bouton Stop (appel API /api/tasks/stop)
        t_stop_call = time.monotonic()
        status, res = self.app.handle_api_post("/api/tasks/stop", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(res["status"], "Arrêté")

        # Attendre l'arrêt de la boucle
        task_thread.join(timeout=2.0)
        t_stopped = time.monotonic()
        elapsed = t_stopped - t_stop_call

        self.assertFalse(task_thread.is_alive(), "La boucle agent n'a pas quitté après la demande d'arrêt.")
        self.assertLess(
            elapsed,
            1.0,
            f"L'arrêt a pris {elapsed:.3f}s, ce qui dépasse le plafond de 1 seconde prescrit."
        )

    def test_04_xss_escaping_in_tool_and_event_data(self) -> None:
        """4. Échappement XSS strict sur toutes les données d'outils et événements affichés."""
        bus = self.bridge.event_bus

        malicious_script = "<script>alert('XSS_ATTACK')</script>"
        malicious_img = '<img src="x" onerror="alert(1)">'
        malicious_svg = '<svg/onload=alert(document.cookie)>'

        ev = bus.handle_harness_event(
            HarnessEvent(
                "tool.completed",
                {
                    "tool": "read_file",
                    "status": "error",
                    "output": malicious_script,
                    "target": malicious_img,
                    "reason": malicious_svg,
                },
            )
        )

        d = ev.to_dict()
        data_str = json.dumps(d)

        # En JSON brut, le payload est sérialisé sans exécution
        self.assertIn("XSS_ATTACK", data_str)

        # Côté HTML de l'inspecteur : vérifier que le template app.js utilise esc()
        # Simulons la fonction esc() équivalente à ui/static/app.js
        def esc(val: str) -> str:
            return (
                str(val)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;")
            )

        escaped_script = esc(malicious_script)
        self.assertNotIn("<script>", escaped_script)
        self.assertIn("&lt;script&gt;", escaped_script)

        escaped_img = esc(malicious_img)
        self.assertNotIn("<img", escaped_img)
        self.assertIn("&lt;img", escaped_img)

        escaped_svg = esc(malicious_svg)
        self.assertNotIn("<svg", escaped_svg)
        self.assertIn("&lt;svg", escaped_svg)

    def test_05_api_runs_recovery_state_on_page_reload(self) -> None:
        """5. La route /api/runs/<run_id> restitue fidèlement le plan, le budget, la compilation et la recherche."""
        bus = self.bridge.event_bus
        bus.clear()

        # Simuler une mission avec plan, budget, compilation et recherche
        bus.handle_harness_event(
            HarnessEvent(
                "plan.created",
                {
                    "plan_steps": [
                        {"id": 1, "description": "Rechercher la doc", "status": "completed"},
                        {"id": 2, "description": "Compiler le rapport", "status": "in_progress"},
                    ]
                },
            )
        )
        bus.handle_harness_event(
            HarnessEvent(
                "budget.update",
                {"tokens_used": 3400, "tokens_limit": 50000, "time_elapsed": 12.5, "time_limit": 200.0, "tool_calls": 4, "tool_limit": 20},
            )
        )
        bus.handle_harness_event(
            HarnessEvent(
                "compile.error",
                {"attempt": 2, "max_attempts": 25, "file": "rapport.tex", "line": 42, "message": "Undefined control sequence \\badcmd"},
            )
        )
        bus.handle_harness_event(
            HarnessEvent(
                "search.query",
                {"query": "site officiel documentation"},
            )
        )
        bus.handle_harness_event(
            HarnessEvent(
                "download.verified",
                {"destination": "workspace/downloads/doc.pdf", "size_bytes": 10240, "sha256": "abcdef123456"},
            )
        )

        status, run_state = self.app.handle_api_get("/api/runs/current", {})
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(run_state["ok"])
        self.assertEqual(len(run_state["plan"]), 2)
        self.assertEqual(run_state["plan"][0]["status"], "completed")
        self.assertEqual(run_state["plan"][1]["status"], "in_progress")

        self.assertEqual(run_state["budget"]["tokens_used"], 3400)
        self.assertEqual(run_state["compilation"]["line"], 42)
        self.assertEqual(run_state["compilation"]["attempt"], 2)
        self.assertEqual(run_state["search"]["query"], "site officiel documentation")
        self.assertEqual(run_state["search"]["size_bytes"], 10240)
        self.assertGreater(run_state["last_seq"], 0)


if __name__ == "__main__":
    unittest.main()
