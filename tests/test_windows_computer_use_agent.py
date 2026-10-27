# RÔLE DE CE FICHIER :
# Suite de tests complète pour l'architecture d'agent opérateur Windows de NeoHarness :
#   1. Policy Engine (SAFE, LOW, MEDIUM, HIGH, CRITICAL, BLOCKED + règles custom)
#   2. Human-In-The-Loop (autorisé, refusé, timeout UI, session, refus session sur HIGH/CRITICAL, retour STRICT)
#   3. Tool Gateway & Observabilité (namespaces, exécution, traces horodatées, journal .jsonl)
#   4. Computer Use (screenshot, comparaison avant/après, clic, clavier, Fail-Safe, boucle fermée)
#   5. Terminal Interactif Persistant Windows (commande simple, persistance d'état, interactif, arrêt)
#   6. Process Manager, Fenêtres Windows & Clipboard
#   7. Boucle Agentique E2E en boucle fermée (Perception -> Action -> Vérification -> Auto-correction)

from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from agents.coder import CodeAgent
from core.agent_loop import AgentLoop
from core.intent_engine import IntentEngine
from core.permissions import PermissionLevel, PermissionPolicy, RiskLevel, format_hitl_box
from core.planner import Planner
from core.policy_engine import PolicyEngine, PolicyRule
from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall
from tools.clipboard import clipboard_get, clipboard_set
from tools.computer_use import (
    ComputerUseFailSafeError,
    computer_action_verified,
    computer_click,
    computer_compare_screens,
    computer_hotkey,
    computer_mouse_move,
    computer_press,
    computer_screenshot,
    computer_type,
)
from tools.filesystem import WorkspaceFilesystem
from tools.process_manager import process_list, process_start, process_status, process_stop
from tools.registry import ToolCall, ToolRegistry
from tools.terminal import (
    terminal_list,
    terminal_read,
    terminal_send,
    terminal_start,
    terminal_stop,
)
from tools.windows import window_active, window_find, window_list
from ui.server import NeoHarnessRuntimeBridge


class _ScriptedClosedLoopProvider(BaseProvider):
    """Fournisseur déterministe simulant un agent Computer Use en boucle fermée."""

    def __init__(self, turns: list[AgentTurn]) -> None:
        self._turns = list(turns)
        self._index = 0

    def generate(self, prompt: str = "") -> str:
        return "OK"

    def execute(self, instruction: str = "") -> str:
        return "OK"

    def get_name(self) -> str:
        return "ScriptedClosedLoopProvider"

    def get_model_name(self) -> str:
        return "test-operator-v1"

    def get_status_label(self) -> str:
        return "[TEST CONNECTÉ]"

    def generate_agent_turn(self, prompt, tools, continuation=None, tool_results=None) -> AgentTurn:
        if self._index < len(self._turns):
            turn = self._turns[self._index]
            self._index += 1
            return turn
        return AgentTurn(text="Mission opérateur vérifiée et terminée.")


class PolicyEngineTests(unittest.TestCase):
    """Tests de la classification des risques et du blocage de sécurité du Policy Engine."""

    def setUp(self) -> None:
        self.engine = PolicyEngine()

    def test_canonical_risk_classifications(self) -> None:
        ev_read = self.engine.evaluate("read_file", {"path": "main.py"})
        self.assertEqual(ev_read.canonical_action, "filesystem.read")
        self.assertEqual(ev_read.risk_label, "SAFE")
        self.assertEqual(ev_read.risk_level, RiskLevel.READ_ONLY)

        ev_write = self.engine.evaluate("write_file", {"path": "notes.txt", "content": "ok"})
        self.assertEqual(ev_write.canonical_action, "filesystem.write")
        self.assertEqual(ev_write.risk_label, "LOW")
        self.assertTrue(ev_write.allow_session_approval)

        ev_proc = self.engine.evaluate("process_start", {"executable": "code"})
        self.assertEqual(ev_proc.canonical_action, "process.start")
        self.assertEqual(ev_proc.risk_label, "MEDIUM")
        self.assertIn("VS Code", ev_proc.human_description)
        self.assertTrue(ev_proc.allow_session_approval)

        ev_pkg = self.engine.evaluate("terminal_send", {"command": "pip install requests"})
        self.assertEqual(ev_pkg.canonical_action, "package.install")
        self.assertEqual(ev_pkg.risk_label, "MEDIUM")

        ev_del_many = self.engine.evaluate(
            "filesystem.delete_many",
            {"paths": [f"f_{i}.txt" for i in range(143)]},
        )
        self.assertEqual(ev_del_many.risk_label, "HIGH")
        self.assertFalse(ev_del_many.allow_session_approval)
        self.assertIn("143", ev_del_many.human_description)

        ev_reg = self.engine.evaluate(
            "terminal_send",
            {"command": "reg add HKCU\\Software\\Test /v Flag /t REG_DWORD /d 1"},
        )
        self.assertEqual(ev_reg.canonical_action, "registry.modify")
        self.assertEqual(ev_reg.risk_label, "HIGH")
        self.assertFalse(ev_reg.allow_session_approval)

        ev_shutdown = self.engine.evaluate(
            "terminal_send",
            {"command": "shutdown /s /t 0"},
        )
        self.assertEqual(ev_shutdown.canonical_action, "system.shutdown")
        self.assertEqual(ev_shutdown.risk_label, "CRITICAL")
        self.assertEqual(ev_shutdown.risk_level, RiskLevel.DESTRUCTIVE)
        self.assertFalse(ev_shutdown.allow_session_approval)

    def test_security_guardrails_block_forbidden_actions(self) -> None:
        ev_defender = self.engine.evaluate(
            "terminal_send",
            {"command": "Set-MpPreference -DisableRealtimeMonitoring $true"},
        )
        self.assertTrue(ev_defender.blocked)
        self.assertEqual(ev_defender.risk_label, "BLOCKED")

        ev_uac = self.engine.evaluate(
            "process_start",
            {"executable": "fodhelper.exe"},
        )
        self.assertTrue(ev_uac.blocked)

        ev_lsass = self.engine.evaluate(
            "terminal_send",
            {"command": "procdump -ma lsass.exe lsass.dmp"},
        )
        self.assertTrue(ev_lsass.blocked)

    def test_custom_policy_rule_registration(self) -> None:
        self.engine.register_rule(
            PolicyRule(
                rule_id="custom.prod_deploy",
                category="Déploiement",
                risk_level=RiskLevel.HIGH,
                risk_label="HIGH",
                matcher=lambda name, args: "deploy_prod" in str(args.get("command", "")),
                describe=lambda name, args: "Déployer en production",
            )
        )
        ev = self.engine.evaluate("terminal_send", {"command": "./deploy_prod.sh"})
        self.assertEqual(ev.canonical_action, "custom.prod_deploy")
        self.assertEqual(ev.risk_label, "HIGH")
        self.assertFalse(ev.allow_session_approval)


class HITLAndPermissionsTests(unittest.TestCase):
    """Tests du Human-In-The-Loop : autorisation, refus, session, mode strict et timeout."""

    def test_hitl_allow_deny_and_session_permissions(self) -> None:
        decisions = ["allow_once", "deny", "allow_session"]
        call_count = 0

        def _confirm(name, risk, evaluation):
            nonlocal call_count
            dec = decisions[min(call_count, len(decisions) - 1)]
            call_count += 1
            return dec

        policy = PermissionPolicy(confirm=_confirm, permission_level=PermissionLevel.SESSION.value)

        # 1. allow_once -> autorisé, mais ne mémorise pas pour la session
        ok1, _ = policy.authorize("process_start", RiskLevel.MODERATE, True, {"executable": "code"})
        self.assertTrue(ok1)
        self.assertEqual(call_count, 1)

        # 2. deny -> refusé
        ok2, reason2 = policy.authorize("process_start", RiskLevel.MODERATE, True, {"executable": "code"})
        self.assertFalse(ok2)
        self.assertIn("refusé", reason2)
        self.assertEqual(call_count, 2)

        # 3. allow_session -> autorisé et mémorisé pour la session
        ok3, _ = policy.authorize("process_start", RiskLevel.MODERATE, True, {"executable": "code"})
        self.assertTrue(ok3)
        self.assertEqual(call_count, 3)

        # 4. Appel suivant sur le même outil/catégorie -> passe sans rappeler _confirm !
        ok4, reason4 = policy.authorize("process_start", RiskLevel.MODERATE, True, {"executable": "notepad"})
        self.assertTrue(ok4)
        self.assertIn("session", reason4)
        self.assertEqual(call_count, 3)

        # 5. Retour au mode STRICT -> efface les permissions de session et redemande validation
        policy.reset_to_strict()
        self.assertEqual(policy.permission_level, "STRICT")
        self.assertEqual(len(policy.session_approved_tools), 0)

    def test_high_risk_action_never_grants_session_approval(self) -> None:
        confirm_calls = 0

        def _confirm(name, risk, evaluation):
            nonlocal confirm_calls
            confirm_calls += 1
            # Même si l'appelant renvoie allow_session sur une action HIGH, la session ne doit pas être accordée
            return "allow_session"

        policy = PermissionPolicy(confirm=_confirm, permission_level=PermissionLevel.SESSION.value)
        ok1, _ = policy.authorize("delete_file", RiskLevel.DESTRUCTIVE, True, {"path": "a.txt"})
        self.assertTrue(ok1)
        self.assertEqual(confirm_calls, 1)
        self.assertNotIn("delete_file", policy.session_approved_tools)

        # Un deuxième delete_file redemande obligatoirement la confirmation
        ok2, _ = policy.authorize("delete_file", RiskLevel.DESTRUCTIVE, True, {"path": "b.txt"})
        self.assertTrue(ok2)
        self.assertEqual(confirm_calls, 2)

    def test_format_hitl_box_renders_appropriate_buttons(self) -> None:
        engine = PolicyEngine()
        low_ev = engine.evaluate("process_start", {"executable": "code"})
        low_box = format_hitl_box(low_ev)
        self.assertIn("AUTORISATION NÉCESSAIRE", low_box)
        self.assertIn("Autoriser pour cette session", low_box)

        high_ev = engine.evaluate("filesystem.delete_many", {"paths": ["a", "b", "c"]})
        high_box = format_hitl_box(high_ev)
        self.assertIn("ACTION À RISQUE", high_box)
        self.assertIn("[Autoriser une fois]", high_box)
        self.assertNotIn("Autoriser pour cette session", high_box)

    def test_ui_bridge_hitl_timeout_and_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = NeoHarnessRuntimeBridge(workspace=tmp)
            bridge.approval_timeout_seconds = 0.15
            # Timeout sans réponse -> refusé
            approved = bridge._confirm_tool_action("process_start", RiskLevel.MODERATE)
            self.assertFalse(approved)

            # Résolution asynchrone positive
            bridge.approval_timeout_seconds = 3.0
            result_holder: list[Any] = []

            def _worker() -> None:
                ev = bridge.permissions._get_policy_engine().evaluate(
                    "process_start", {"executable": "code"}
                )
                res = bridge._confirm_tool_action("process_start", RiskLevel.MODERATE, ev)
                result_holder.append(res)

            t = threading.Thread(target=_worker)
            t.start()
            time.sleep(0.1)
            pending = bridge.list_pending_approvals()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["human_description"], "Ouvrir l'application VS Code")
            bridge.resolve_approval(pending[0]["id"], "allow_once")
            t.join(timeout=2.0)
            self.assertEqual(result_holder, [True])


class ToolGatewayAndObservabilityTests(unittest.TestCase):
    """Tests du Tool Gateway, des namespaces et de la journalisation d'observabilité."""

    def test_gateway_records_full_trace_and_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fs = WorkspaceFilesystem(tmp)
            fs.write_file("hello.txt", "Bonjour NeoHarness", overwrite=True)
            policy = PermissionPolicy(confirm=lambda *_: True)
            registry = ToolRegistry(fs, policy)

            namespaces = registry.gateway.list_tools_by_namespace()
            self.assertIn("read_file", namespaces["filesystem"])
            self.assertIn("computer_screenshot", namespaces["computer_use"])
            self.assertIn("terminal_send", namespaces["terminal"])
            self.assertIn("window_list", namespaces["windows"])
            self.assertIn("process_list", namespaces["process"])
            self.assertIn("clipboard_get", namespaces["clipboard"])

            res = registry.execute(ToolCall(name="read_file", arguments={"path": "hello.txt"}))
            self.assertEqual(res.status, "success")

            traces = registry.gateway.list_traces()
            step_types = [t["step_type"] for t in traces]
            self.assertIn("AGENT_CALL", step_types)
            self.assertIn("POLICY", step_types)
            self.assertIn("HITL", step_types)
            self.assertIn("VERIFICATION", step_types)

            audit_file = Path(tmp) / ".harness" / "operator_audit.jsonl"
            self.assertTrue(audit_file.is_file())
            lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 4)

            # Action bloquée par le PolicyEngine
            blocked_res = registry.execute(
                ToolCall(
                    name="terminal_send",
                    arguments={"command": "Set-MpPreference -DisableRealtimeMonitoring $true"},
                )
            )
            self.assertEqual(blocked_res.status, "denied")
            self.assertIn("Policy Engine", blocked_res.summary)


class ComputerUseClosedLoopTests(unittest.TestCase):
    """Tests de Computer Use : screenshot, comparaison, souris/clavier et boucle fermée."""

    def test_screenshot_and_screen_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shot = computer_screenshot(label="test_unit", workspace=tmp)
            self.assertEqual(shot["status"], "success")
            self.assertTrue(Path(shot["abs_path"]).is_file())

            img_a = Path(tmp) / "a.png"
            img_b = Path(tmp) / "b.png"
            img_c = Path(tmp) / "c.png"
            Image.new("RGB", (200, 200), color=(255, 255, 255)).save(img_a)
            Image.new("RGB", (200, 200), color=(255, 255, 255)).save(img_b)
            im_mod = Image.new("RGB", (200, 200), color=(255, 255, 255))
            for x in range(50, 100):
                for y in range(50, 100):
                    im_mod.putpixel((x, y), (20, 40, 200))
            im_mod.save(img_c)

            same_cmp = computer_compare_screens(img_a, img_b, workspace=tmp)
            self.assertFalse(same_cmp["screen_changed"])
            self.assertEqual(same_cmp["changed_pixels"], 0)

            diff_cmp = computer_compare_screens(img_a, img_c, workspace=tmp)
            self.assertTrue(diff_cmp["screen_changed"])
            self.assertEqual(diff_cmp["changed_pixels"], 2500)
            self.assertIsNotNone(diff_cmp["changed_bbox"])

    def test_mouse_keyboard_and_failsafe_validation(self) -> None:
        with patch("tools.computer_use._is_win32", return_value=False):
            mv = computer_mouse_move(300, 400)
            self.assertEqual(mv["x"], 300)
            self.assertEqual(mv["y"], 400)

            clk = computer_click(300, 400, button="left", double=True)
            self.assertEqual(clk["action"], "double_click")

            tp = computer_type("NeoHarness")
            self.assertEqual(tp["length"], 10)

            pr = computer_press("enter")
            self.assertEqual(pr["key"], "enter")

            hk = computer_hotkey(["ctrl", "shift", "p"])
            self.assertEqual(hk["keys"], ["ctrl", "shift", "p"])

            # Fail-Safe sur (0, 0)
            with self.assertRaises(ComputerUseFailSafeError):
                computer_click(0, 0)

    def test_closed_loop_action_detects_no_effect_vs_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img_static = Path(tmp) / "static.png"
            img_changed = Path(tmp) / "changed.png"
            Image.new("RGB", (100, 100), color=(240, 240, 240)).save(img_static)
            Image.new("RGB", (100, 100), color=(10, 120, 240)).save(img_changed)

            # Cas 1 : l'écran ne change pas et la fenêtre ne change pas -> verified=False
            shots_no_change = [
                {
                    "status": "success",
                    "path": "static.png",
                    "abs_path": str(img_static),
                    "active_window": {"title": "Bureau"},
                },
                {
                    "status": "success",
                    "path": "static.png",
                    "abs_path": str(img_static),
                    "active_window": {"title": "Bureau"},
                },
            ]
            with (
                patch("tools.computer_use._is_win32", return_value=True),
                patch("tools.computer_use._check_failsafe"),
                patch("tools.computer_use.computer_click", return_value={"status": "success"}),
                patch("tools.computer_use.computer_screenshot", side_effect=shots_no_change),
            ):
                res_fail = computer_action_verified(
                    "click", x=200, y=200, settle_ms=50, workspace=tmp
                )
                self.assertFalse(res_fail["verified"])
                self.assertEqual(res_fail["error_code"], "click_or_action_had_no_effect")

            # Cas 2 : l'écran change et la fenêtre attendue "Visual Studio Code" s'ouvre -> verified=True
            shots_changed = [
                {
                    "status": "success",
                    "path": "static.png",
                    "abs_path": str(img_static),
                    "active_window": {"title": "Bureau"},
                },
                {
                    "status": "success",
                    "path": "changed.png",
                    "abs_path": str(img_changed),
                    "active_window": {"title": "NeoTab - Visual Studio Code"},
                },
            ]
            with (
                patch("tools.computer_use._is_win32", return_value=True),
                patch("tools.computer_use._check_failsafe"),
                patch("tools.computer_use.computer_click", return_value={"status": "success"}),
                patch("tools.computer_use.computer_screenshot", side_effect=shots_changed),
            ):
                res_ok = computer_action_verified(
                    "click",
                    x=200,
                    y=200,
                    expected_window="Visual Studio Code",
                    settle_ms=50,
                    workspace=tmp,
                )
                self.assertTrue(res_ok["verified"])
                self.assertTrue(res_ok["screen_changed"])
                self.assertTrue(res_ok["window_matched"])


class PersistentTerminalAndProcessTests(unittest.TestCase):
    """Tests du terminal interactif persistant Windows, des processus, fenêtres et presse-papiers."""

    def test_persistent_terminal_keeps_state_across_commands_and_stops(self) -> None:
        sid = "test_pers_session"
        try:
            start_res = terminal_start(session_id=sid, shell="powershell")
            self.assertEqual(start_res["status"], "success")
            self.assertTrue(start_res["alive"])

            # Commande 1 : définir une variable dans la session PowerShell vivante
            terminal_send("$env:NEOHARNESS_PERSIST_VAR = 'VIVANT_42'", session_id=sid, wait_ms=400)
            # Commande 2 : relire la variable dans la même session
            out_res = terminal_send("Write-Output $env:NEOHARNESS_PERSIST_VAR", session_id=sid, wait_ms=600)
            self.assertEqual(out_res["status"], "success")
            self.assertIn("VIVANT_42", out_res["stdout"])

            sessions = terminal_list()
            self.assertTrue(any(s["session_id"] == sid for s in sessions["sessions"]))
        finally:
            stop_res = terminal_stop(session_id=sid)
            self.assertTrue(stop_res["stopped"])

    def test_process_manager_start_status_and_stop(self) -> None:
        res = process_start(
            sys.executable,
            arguments=["-c", "import time; print('READY_PROC', flush=True); time.sleep(10)"],
        )
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["alive"])
        pid = res["pid"]
        try:
            st = process_status(pid)
            self.assertTrue(st["alive"])
        finally:
            stopped = process_stop(pid, force=True)
            self.assertTrue(stopped["stopped"])

    def test_clipboard_and_window_enumeration(self) -> None:
        set_res = clipboard_set("Texte NeoHarness Presse-Papiers")
        self.assertEqual(set_res["status"], "success")
        get_res = clipboard_get()
        self.assertEqual(get_res["text"], "Texte NeoHarness Presse-Papiers")

        win_res = window_list(visible_only=True)
        self.assertEqual(win_res["status"], "success")
        self.assertIsInstance(win_res["windows"], list)

        act_res = window_active()
        self.assertEqual(act_res["status"], "success")


class ClosedLoopOperatorAgentE2ETests(unittest.TestCase):
    """Test de bout en bout de la boucle AgentLoop + IntentEngine + Verifier en mode Computer Use."""

    def test_agent_loop_recovers_from_unverified_click_and_verifies_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fs = WorkspaceFilesystem(tmp)
            policy = PermissionPolicy(confirm=lambda *_: True)
            registry = ToolRegistry(fs, policy)

            img_before = Path(tmp) / "before.png"
            img_after = Path(tmp) / "after.png"
            Image.new("RGB", (100, 100), color=(255, 255, 255)).save(img_before)
            Image.new("RGB", (100, 100), color=(30, 140, 250)).save(img_after)

            # Tour 1 : l'agent tente un clic qui n'a aucun effet (verified=False)
            # Tour 2 : le Verifier ou l'indice d'erreur amène l'agent à refaire l'action vérifiée qui réussit
            # Tour 3 : réponse finale
            turns = [
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            name="computer_action_verified",
                            arguments={"action_type": "click", "x": 150, "y": 150},
                            call_id="c1",
                        )
                    ]
                ),
                AgentTurn(
                    tool_calls=[
                        ProviderToolCall(
                            name="computer_action_verified",
                            arguments={
                                "action_type": "click",
                                "x": 300,
                                "y": 300,
                                "expected_window": "Visual Studio Code",
                            },
                            call_id="c2",
                        )
                    ]
                ),
                AgentTurn(text="VS Code a été ouvert et vérifié à l'écran."),
            ]

            call_seq = 0

            def _fake_action_verified(**kwargs):
                nonlocal call_seq
                call_seq += 1
                if call_seq == 1:
                    return {
                        "status": "warning",
                        "verified": False,
                        "action_type": "click",
                        "screen_changed": False,
                        "error_code": "click_or_action_had_no_effect",
                    }
                return {
                    "status": "success",
                    "verified": True,
                    "action_type": "click",
                    "screen_changed": True,
                    "expected_window": "Visual Studio Code",
                    "window_matched": True,
                }

            registry._tools["computer_action_verified"].execute = _fake_action_verified

            provider = _ScriptedClosedLoopProvider(turns)
            agent = CodeAgent()
            agent.set_provider(provider)
            loop = AgentLoop(registry, planner=Planner(), emit=None)

            result = loop.run(
                agent,
                "Ouvre l'application VS Code et clique sur le projet en vérifiant la fenêtre.",
            )
            self.assertIn(result.status, {"verified", "success"})
            self.assertEqual(result.verification["status"], "passed")
            checks = {c["check"]: c["status"] for c in result.verification["checks"]}
            self.assertEqual(checks.get("computer_use_closed_loop_verified"), "passed")


if __name__ == "__main__":
    unittest.main()