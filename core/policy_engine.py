# RÔLE DE CE FICHIER :
# Moteur de politiques de sécurité (Policy Engine) séparé et extensible.
# Classifie chaque action (outil + arguments) selon son niveau de risque réel
# (SAFE, LOW, MEDIUM, HIGH, CRITICAL, BLOCKED), détecte les tentatives de
# contournement de sécurité Windows (UAC, Defender, secrets, arrêt système)
# et génère l'explication humaine destinée au Human-In-The-Loop (HITL).

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from core.permissions import RiskLevel


RISK_LABELS: dict[int, str] = {
    int(RiskLevel.READ_ONLY): "SAFE",
    int(RiskLevel.LOW): "LOW",
    int(RiskLevel.MODERATE): "MEDIUM",
    int(RiskLevel.HIGH): "HIGH",
    int(RiskLevel.DESTRUCTIVE): "CRITICAL",
}

RISK_LABELS_FR: dict[str, str] = {
    "SAFE": "Sûr",
    "LOW": "Faible",
    "MEDIUM": "Moyen",
    "HIGH": "Élevé",
    "CRITICAL": "Critique",
    "BLOCKED": "Interdit (Bloqué)",
}


@dataclass
class PolicyRule:
    """Règle déclarative du Policy Engine."""

    rule_id: str
    category: str
    risk_level: RiskLevel
    risk_label: str
    matcher: Callable[[str, dict[str, Any]], bool]
    describe: Callable[[str, dict[str, Any]], str]
    blocked: bool = False
    block_reason: str = ""


@dataclass
class PolicyEvaluation:
    """Résultat complet de l'évaluation d'une action par le Policy Engine."""

    tool_name: str
    canonical_action: str
    category: str
    risk_level: RiskLevel
    risk_label: str
    risk_label_fr: str
    human_description: str
    arguments: dict[str, Any] = field(default_factory=dict)
    mutates: bool = False
    blocked: bool = False
    block_reason: str = ""
    requires_confirmation: bool = False
    allow_session_approval: bool = True
    matched_rule_id: str = "default"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_level"] = self.risk_level.name
        data["risk_value"] = int(self.risk_level)
        return data


class PolicyEngine:
    """Évalue le niveau de risque et la conformité sécurité de chaque action d'agent."""

    # Patterns strictement interdits (Section 14 — Sécurité Windows)
    _FORBIDDEN_SECURITY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(
                r"\b(Set-MpPreference|Add-MpPreference|DisableRealtimeMonitoring|"
                r"DisableIOAVProtection|DisableBehaviorMonitoring|sc\s+stop\s+WinDefend)\b",
                re.I,
            ),
            "Contournement ou désactivation de l'antivirus / Windows Defender interdit.",
        ),
        (
            re.compile(
                r"\b(fodhelper|eventvwr|sdclt|computerdefaults|cmstp)\b|"
                r"ConsentPromptBehaviorAdmin|EnableLUA\s+.*0",
                re.I,
            ),
            "Tentative de contournement UAC (User Account Control) interdite.",
        ),
        (
            re.compile(
                r"\b(mimikatz|sekurlsa|lsass\.exe|procdump.*lsass|reg\s+save\s+hklm\\(sam|security|system))\b",
                re.I,
            ),
            "Extraction de mots de passe, condensats ou ruches d'authentification système interdite.",
        ),
        (
            re.compile(
                r"\b(bcdedit\s+/set.*(testsigning|nointegritychecks)|netsh\s+advfirewall\s+set\s+.*state\s+off)\b",
                re.I,
            ),
            "Désactivation des protections système ou du pare-feu Windows interdite.",
        ),
    )

    _CRITICAL_SYSTEM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(
                r"\b(shutdown(?:\.exe)?\s+/[srp]|Stop-Computer|Restart-Computer|"
                r"format\s+[a-z]:|diskpart|cipher\s+/w)\b",
                re.I,
            ),
            "system.shutdown",
        ),
    )

    _HIGH_RISK_COMMAND_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(
                r"\b(reg(?:\.exe)?\s+(add|delete|import)|New-ItemProperty.*HKLM:|"
                r"Set-ItemProperty.*HKLM:|Remove-ItemProperty.*HKCU:)\b",
                re.I,
            ),
            "registry.modify",
        ),
        (
            re.compile(
                r"\b(Remove-Item\s+.*-Recurse|rm\s+-rf|del\s+/[fqs]|rmdir\s+/s)\b",
                re.I,
            ),
            "filesystem.delete_many",
        ),
        (
            re.compile(
                r"\b(taskkill(?:\.exe)?\s+/f|Stop-Process\s+.*-Force)\b",
                re.I,
            ),
            "process.kill",
        ),
    )

    _PACKAGE_INSTALL_PATTERNS: re.Pattern[str] = re.compile(
        r"\b(pip\s+install|python\s+-m\s+pip\s+install|npm\s+(?:install|i)\b|"
        r"pnpm\s+add|yarn\s+add|winget\s+install|choco\s+install)\b",
        re.I,
    )

    # Table canonique d'actions (Section 6 du cahier des charges)
    CANONICAL_ACTION_RISKS: dict[str, tuple[str, RiskLevel, str]] = {
        # (Catégorie, RiskLevel, RiskLabel)
        "filesystem.read": ("Filesystem", RiskLevel.READ_ONLY, "SAFE"),
        "filesystem.write": ("Filesystem", RiskLevel.LOW, "LOW"),
        "filesystem.delete": ("Filesystem", RiskLevel.HIGH, "HIGH"),
        "filesystem.delete_many": ("Filesystem", RiskLevel.HIGH, "HIGH"),
        "filesystem.move": ("Filesystem", RiskLevel.HIGH, "HIGH"),
        "process.list": ("Processus", RiskLevel.READ_ONLY, "SAFE"),
        "process.status": ("Processus", RiskLevel.READ_ONLY, "SAFE"),
        "process.start": ("Processus", RiskLevel.MODERATE, "MEDIUM"),
        "process.stop": ("Processus", RiskLevel.HIGH, "HIGH"),
        "process.kill": ("Processus", RiskLevel.HIGH, "HIGH"),
        "package.install": ("Terminal", RiskLevel.MODERATE, "MEDIUM"),
        "registry.modify": ("Système", RiskLevel.HIGH, "HIGH"),
        "system.shutdown": ("Système", RiskLevel.DESTRUCTIVE, "CRITICAL"),
        "clipboard.get": ("Presse-papiers", RiskLevel.READ_ONLY, "SAFE"),
        "clipboard.set": ("Presse-papiers", RiskLevel.LOW, "LOW"),
        "windows.list": ("Fenêtres", RiskLevel.READ_ONLY, "SAFE"),
        "windows.focus": ("Fenêtres", RiskLevel.LOW, "LOW"),
        "windows.state": ("Fenêtres", RiskLevel.LOW, "LOW"),
        "windows.close": ("Fenêtres", RiskLevel.HIGH, "HIGH"),
        "computer_use.observe": ("Computer Use", RiskLevel.READ_ONLY, "SAFE"),
        "computer_use.mouse": ("Computer Use", RiskLevel.MODERATE, "MEDIUM"),
        "computer_use.keyboard": ("Computer Use", RiskLevel.MODERATE, "MEDIUM"),
        "computer_use.action_verified": ("Computer Use", RiskLevel.MODERATE, "MEDIUM"),
        "terminal.read": ("Terminal", RiskLevel.READ_ONLY, "SAFE"),
        "terminal.start": ("Terminal", RiskLevel.LOW, "LOW"),
        "terminal.send": ("Terminal", RiskLevel.MODERATE, "MEDIUM"),
        "terminal.stop": ("Terminal", RiskLevel.LOW, "LOW"),
        "browser.observe": ("Navigateur", RiskLevel.READ_ONLY, "SAFE"),
        "browser.interact": ("Navigateur", RiskLevel.LOW, "LOW"),
        "browser.download": ("Navigateur", RiskLevel.MODERATE, "MEDIUM"),
        "git.read": ("Git", RiskLevel.READ_ONLY, "SAFE"),
        "git.mutate": ("Git", RiskLevel.HIGH, "HIGH"),
        "mcp.call": ("MCP", RiskLevel.MODERATE, "MEDIUM"),
    }

    # Correspondance entre les noms d'outils enregistrés et les actions canoniques
    TOOL_TO_CANONICAL: dict[str, str] = {
        "list_files": "filesystem.read",
        "find_file": "filesystem.read",
        "search_files": "filesystem.read",
        "read_file": "filesystem.read",
        "read_document": "filesystem.read",
        "analyze_dataset": "filesystem.read",
        "generate_excel": "filesystem.write",
        "view_file": "filesystem.read",
        "search_code": "filesystem.read",
        "code_ast_map": "filesystem.read",
        "diagnose_code": "filesystem.read",
        "write_file": "filesystem.write",
        "patch_file": "filesystem.write",
        "edit_file": "filesystem.write",
        "delete_file": "filesystem.delete",
        "delete_many_files": "filesystem.delete_many",
        "move_file": "filesystem.move",
        "run_tests": "terminal.send",
        "run_python": "process.start",
        "git_status": "git.read",
        "git_current_branch": "git.read",
        "git_create_branch": "git.mutate",
        "git_commit_staged": "git.mutate",
        "git_merge": "git.mutate",
        "web_search": "browser.observe",
        "deep_research": "browser.observe",
        "fetch_url": "browser.observe",
        "download_resource": "browser.download",
        "navigate_url": "browser.observe",
        "click_element": "browser.interact",
        "fill_input": "browser.interact",
        "download_via_browser": "browser.download",
        "screenshot_page": "browser.observe",
        "compile_document": "filesystem.write",
        "generate_math_figure": "filesystem.read",
        "generate_docx": "filesystem.write",
        "generate_pptx": "filesystem.write",
        "transcribe_image": "computer_use.observe",
        # Nouveaux outils Windows / Computer Use / Terminal / Process / Clipboard
        "clipboard_get": "clipboard.get",
        "clipboard_set": "clipboard.set",
        "process_list": "process.list",
        "process_status": "process.status",
        "process_start": "process.start",
        "process_stop": "process.stop",
        "window_list": "windows.list",
        "window_active": "windows.list",
        "window_find": "windows.list",
        "window_focus": "windows.focus",
        "window_minimize": "windows.state",
        "window_maximize": "windows.state",
        "window_restore": "windows.state",
        "window_close": "windows.close",
        "computer_screenshot": "computer_use.observe",
        "computer_ocr": "computer_use.observe",
        "computer_inspect_ui": "computer_use.observe",
        "computer_compare_screens": "computer_use.observe",
        "computer_mouse_move": "computer_use.mouse",
        "computer_click": "computer_use.mouse",
        "computer_click_element": "computer_use.action_verified",
        "computer_drag": "computer_use.mouse",
        "computer_scroll": "computer_use.mouse",
        "computer_type": "computer_use.keyboard",
        "computer_press": "computer_use.keyboard",
        "computer_hotkey": "computer_use.keyboard",
        "computer_action_verified": "computer_use.action_verified",
        "terminal_start": "terminal.start",
        "terminal_send": "terminal.send",
        "terminal_read": "terminal.read",
        "terminal_stop": "terminal.stop",
        "terminal_list": "terminal.read",
    }

    def __init__(self) -> None:
        self._custom_rules: list[PolicyRule] = []

    def register_rule(self, rule: PolicyRule) -> None:
        """Ajoute une règle personnalisée prioritaire dans le Policy Engine."""
        self._custom_rules.insert(0, rule)

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        default_risk: RiskLevel = RiskLevel.READ_ONLY,
        mutates: bool = False,
    ) -> PolicyEvaluation:
        """Évalue le niveau de risque et construit les métadonnées HITL d'un appel d'outil."""
        args = dict(arguments or {})
        raw_name = (tool_name or "").strip()

        # 1. Règles personnalisées enregistrées par l'utilisateur
        for rule in self._custom_rules:
            try:
                if rule.matcher(raw_name, args):
                    desc = rule.describe(raw_name, args)
                    is_high_or_more = rule.risk_level >= RiskLevel.HIGH or rule.blocked
                    return PolicyEvaluation(
                        tool_name=raw_name,
                        canonical_action=rule.rule_id,
                        category=rule.category,
                        risk_level=rule.risk_level,
                        risk_label=rule.risk_label,
                        risk_label_fr=RISK_LABELS_FR.get(rule.risk_label, rule.risk_label),
                        human_description=desc,
                        arguments=args,
                        mutates=mutates or rule.risk_level > RiskLevel.READ_ONLY,
                        blocked=rule.blocked,
                        block_reason=rule.block_reason,
                        requires_confirmation=rule.risk_level > RiskLevel.READ_ONLY or mutates,
                        allow_session_approval=not is_high_or_more,
                        matched_rule_id=rule.rule_id,
                    )
            except Exception:
                continue

        # 2. Détection des violations de sécurité strictes (Section 14 : UAC, antivirus, secrets...)
        serialized_args = self._extract_command_text(raw_name, args)
        for pattern, reason in self._FORBIDDEN_SECURITY_PATTERNS:
            if pattern.search(serialized_args):
                return PolicyEvaluation(
                    tool_name=raw_name,
                    canonical_action="security.violation",
                    category="Sécurité Système",
                    risk_level=RiskLevel.DESTRUCTIVE,
                    risk_label="BLOCKED",
                    risk_label_fr=RISK_LABELS_FR["BLOCKED"],
                    human_description=reason,
                    arguments=args,
                    mutates=True,
                    blocked=True,
                    block_reason=reason,
                    requires_confirmation=True,
                    allow_session_approval=False,
                    matched_rule_id="security_hard_block",
                )

        # 3. Résolution de l'action canonique de base
        if raw_name in self.CANONICAL_ACTION_RISKS:
            canonical = raw_name
        elif raw_name in self.TOOL_TO_CANONICAL:
            canonical = self.TOOL_TO_CANONICAL[raw_name]
        elif raw_name.startswith("mcp.") or raw_name.startswith("mcp_"):
            canonical = "mcp.call"
        else:
            canonical = raw_name

        if canonical in self.CANONICAL_ACTION_RISKS:
            category, risk_level, risk_label = self.CANONICAL_ACTION_RISKS[canonical]
        else:
            category = "Workspace"
            risk_level = default_risk
            risk_label = RISK_LABELS.get(int(default_risk), "MEDIUM")

        # 4. Escalade dynamique selon les arguments (ex: shutdown, registry, delete_many, package.install)
        for pattern, escalated_action in self._CRITICAL_SYSTEM_PATTERNS:
            if pattern.search(serialized_args):
                canonical = escalated_action
                category, risk_level, risk_label = self.CANONICAL_ACTION_RISKS[canonical]
                break
        else:
            for pattern, escalated_action in self._HIGH_RISK_COMMAND_PATTERNS:
                if pattern.search(serialized_args):
                    canonical = escalated_action
                    category, risk_level, risk_label = self.CANONICAL_ACTION_RISKS[canonical]
                    break
            else:
                if self._PACKAGE_INSTALL_PATTERNS.search(serialized_args):
                    canonical = "package.install"
                    category, risk_level, risk_label = self.CANONICAL_ACTION_RISKS[canonical]

        # Escalade sur suppression multiple de fichiers
        paths_arg = args.get("paths") or args.get("files")
        if isinstance(paths_arg, list) and len(paths_arg) > 1 and "delete" in raw_name.lower():
            canonical = "filesystem.delete_many"
            category, risk_level, risk_label = self.CANONICAL_ACTION_RISKS[canonical]

        # Escalade sur raccourcis clavier sensibles (Alt+F4, Ctrl+Alt+Del)
        if raw_name == "computer_hotkey":
            keys = [str(k).lower() for k in (args.get("keys") or [])]
            if ("alt" in keys and "f4" in keys) or ("win" in keys and "r" in keys):
                risk_level = max(risk_level, RiskLevel.HIGH)
                risk_label = "HIGH"

        human_desc = self._build_human_description(raw_name, canonical, args)
        effective_mutates = mutates or (risk_level >= RiskLevel.LOW)
        requires_conf = effective_mutates or (risk_level >= RiskLevel.LOW)
        allow_session = (risk_level < RiskLevel.HIGH) and (risk_label not in {"HIGH", "CRITICAL", "BLOCKED"})

        return PolicyEvaluation(
            tool_name=raw_name,
            canonical_action=canonical,
            category=category,
            risk_level=risk_level,
            risk_label=risk_label,
            risk_label_fr=RISK_LABELS_FR.get(risk_label, risk_label),
            human_description=human_desc,
            arguments=args,
            mutates=effective_mutates,
            blocked=False,
            block_reason="",
            requires_confirmation=requires_conf,
            allow_session_approval=allow_session,
            matched_rule_id=canonical,
        )

    @staticmethod
    def _extract_command_text(tool_name: str, args: dict[str, Any]) -> str:
        parts = [tool_name]
        for key in ("command", "input", "executable", "script_path", "text", "path"):
            val = args.get(key)
            if isinstance(val, str) and val:
                parts.append(val)
            elif isinstance(val, list):
                parts.extend(str(x) for x in val)
        if isinstance(args.get("arguments"), list):
            parts.extend(str(x) for x in args["arguments"])
        return " ".join(parts)

    @staticmethod
    def _build_human_description(
        tool_name: str,
        canonical: str,
        args: dict[str, Any],
    ) -> str:
        if canonical == "filesystem.delete_many":
            paths = args.get("paths") or args.get("files") or []
            count = len(paths) if isinstance(paths, list) and paths else args.get("count", "plusieurs")
            return f"Supprimer {count} fichiers"
        if tool_name == "delete_file" or canonical == "filesystem.delete":
            return f"Supprimer le fichier '{args.get('path', 'inconnu')}'"
        if tool_name in {"write_file", "patch_file", "edit_file"} or canonical == "filesystem.write":
            return f"Modifier ou écrire le fichier '{args.get('path', 'workspace')}'"
        if tool_name == "process_start" or canonical == "process.start":
            cmd = args.get("executable") or args.get("command") or args.get("script_path") or "application"
            friendly = {"code": "VS Code", "code.exe": "VS Code", "notepad": "Bloc-notes", "notepad.exe": "Bloc-notes"}.get(
                str(cmd).strip().lower(), str(cmd)
            )
            return f"Ouvrir l'application {friendly}"
        if tool_name == "process_stop" or canonical in {"process.stop", "process.kill"}:
            target = args.get("pid") or args.get("name") or "cible"
            return f"Arrêter le processus Windows ({target})"
        if canonical == "package.install":
            cmd = args.get("command") or args.get("input") or "paquet"
            return f"Installer un paquet : {str(cmd)[:100]}"
        if canonical == "registry.modify":
            return "Modifier le registre Windows"
        if canonical == "system.shutdown":
            return "Arrêter ou redémarrer le système Windows"
        if tool_name == "computer_click":
            btn = args.get("button", "left")
            dbl = "double-clic" if args.get("double") else f"clic ({btn})"
            return f"Effectuer un {dbl} aux coordonnées ({args.get('x', '?')}, {args.get('y', '?')})"
        if tool_name == "computer_type":
            preview = str(args.get("text", ""))[:40]
            return f"Saisir au clavier : '{preview}'"
        if tool_name == "computer_hotkey":
            keys = "+".join(str(k) for k in (args.get("keys") or []))
            return f"Exécuter le raccourci clavier : {keys}"
        if tool_name == "computer_inspect_ui":
            return "Inspecter l'arbre UI Automation Windows et générer la carte Set-of-Mark"
        if tool_name == "computer_click_element":
            eid = args.get("element_id", "?")
            extra = f" et saisir '{str(args.get('text_to_type'))[:30]}'" if args.get("text_to_type") else ""
            return f"Cliquer sur l'élément UI [{eid}]{extra} avec vérification en boucle fermée"
        if tool_name == "computer_action_verified":
            act = args.get("action_type") or args.get("action") or "action GUI"
            if args.get("element_id") is not None:
                target = f"l'élément UI [{args.get('element_id')}]"
            else:
                target = args.get("expected_window") or f"({args.get('x', '?')}, {args.get('y', '?')})"
            return f"Exécuter l'action Computer Use '{act}' vers {target} avec vérification visuelle"
        if tool_name == "window_focus":
            return f"Activer la fenêtre '{args.get('title') or args.get('hwnd') or ''}'"
        if tool_name == "window_close":
            return f"Fermer la fenêtre '{args.get('title') or args.get('hwnd') or ''}'"
        if tool_name == "terminal_start":
            shell = args.get("shell", "powershell")
            return f"Démarrer une session de terminal interactif ({shell})"
        if tool_name == "terminal_send":
            cmd = str(args.get("command") or args.get("input") or "").strip()
            return f"Exécuter dans le terminal : {cmd[:80]}"
        if tool_name == "clipboard_set":
            return "Copier du texte dans le presse-papiers Windows"
        if tool_name == "deep_research":
            return f"Lancer une recherche profonde parallèle (Deep Research) sur '{str(args.get('query', ''))[:60]}'"
        return f"Exécuter {tool_name}"