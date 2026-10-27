# RÔLE DE CE FICHIER :
# Applique les règles d'autorisation des outils avant toute écriture, exécution,
# suppression ou autre action qui change l'espace de travail ou pilote Windows.
# Supporte les niveaux STRICT, SESSION et AUTOMATIC, ainsi que le PolicyEngine.

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from core.policy_engine import PolicyEngine, PolicyEvaluation


class RiskLevel(IntEnum):
    READ_ONLY = 0
    SAFE = 0
    LOW = 1
    MODERATE = 2
    MEDIUM = 2
    HIGH = 3
    DESTRUCTIVE = 4
    CRITICAL = 4


class PermissionLevel(StrEnum):
    STRICT = "STRICT"
    SESSION = "SESSION"
    AUTOMATIC = "AUTOMATIC"


def format_hitl_box(evaluation: "PolicyEvaluation") -> str:
    """Construit l'encadré d'autorisation humaine (HITL) adapté au niveau de risque."""
    is_dangerous = (
        evaluation.risk_level >= RiskLevel.HIGH
        or evaluation.risk_label in {"HIGH", "CRITICAL", "BLOCKED"}
    )
    if is_dangerous:
        lines = [
            "┌─────────────────────────────────────────────────────────┐",
            "│ ⚠️ ACTION À RISQUE                                      │",
            "│                                                         │",
            f"│ {evaluation.human_description[:55]:<55} │",
            "│                                                         │",
            f"│ Outil  : {evaluation.category:<46} │",
            f"│ Risque : {evaluation.risk_label_fr:<46} │",
            "│                                                         │",
            "│ [Refuser]   [Autoriser une fois]                        │",
            "└─────────────────────────────────────────────────────────┘",
        ]
    else:
        lines = [
            "┌─────────────────────────────────────────────────────────┐",
            "│ 🔐 AUTORISATION NÉCESSAIRE                              │",
            "│                                                         │",
            "│ NeoHarness souhaite effectuer :                         │",
            "│                                                         │",
            f"│ {evaluation.human_description[:55]:<55} │",
            "│                                                         │",
            f"│ Outil  : {evaluation.category:<46} │",
            f"│ Risque : {evaluation.risk_label_fr:<46} │",
            "│                                                         │",
            "│ [ Refuser ]  [ Autoriser ]                              │",
            "│ [ Autoriser pour cette session ]                        │",
            "└─────────────────────────────────────────────────────────┘",
        ]
    return "\n".join(lines)


@dataclass
class PermissionPolicy:
    """Les lectures passent; les actions mutantes ou sensibles demandent une décision."""

    confirm: Callable[..., Any] | None = None
    dry_run: bool = False
    autonomous: bool = False
    mode: str = "ACCEPT"
    permission_level: str = PermissionLevel.SESSION.value
    edit_preview: Callable[[str, dict], None] | None = None
    policy_engine: "PolicyEngine | None" = None
    session_approved_tools: set[str] = field(default_factory=set)
    session_approved_categories: set[str] = field(default_factory=set)
    enforce_hitl_on_high_risk: bool = False

    def _get_policy_engine(self) -> "PolicyEngine":
        if self.policy_engine is None:
            from core.policy_engine import PolicyEngine

            self.policy_engine = PolicyEngine()
        return self.policy_engine

    def set_permission_level(self, level: str | PermissionLevel) -> str:
        normalized = str(level).strip().upper()
        if normalized not in {
            PermissionLevel.STRICT.value,
            PermissionLevel.SESSION.value,
            PermissionLevel.AUTOMATIC.value,
        }:
            raise ValueError(
                f"Niveau de permission inconnu : {level}. Attendu : STRICT, SESSION ou AUTOMATIC."
            )
        self.permission_level = normalized
        if normalized == PermissionLevel.STRICT.value:
            self.session_approved_tools.clear()
            self.session_approved_categories.clear()
        return self.permission_level

    def reset_to_strict(self) -> str:
        """Permet à l'utilisateur de revenir immédiatement au mode STRICT."""
        self.autonomous = False
        return self.set_permission_level(PermissionLevel.STRICT)

    def grant_session_permission(
        self,
        *,
        tool_name: str | None = None,
        category: str | None = None,
    ) -> None:
        if tool_name:
            self.session_approved_tools.add(tool_name)
        if category:
            self.session_approved_categories.add(category.lower())

# Actions opérateur à faible risque (LOW) qui s'exécutent sans friction HITL hors mode STRICT
    _LOW_FRICTION_OPERATOR_TOOLS: frozenset[str] = frozenset(
        {
            "computer_screenshot",
            "copy_to_desktop",
            "clipboard_set",
            "window_focus",
            "window_minimize",
            "window_maximize",
            "window_restore",
            "terminal_start",
            "terminal_stop",
        }
    )

    def authorize(
        self,
        name: str,
        risk: RiskLevel,
        mutates: bool,
        arguments: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        engine = self._get_policy_engine()
        evaluation = engine.evaluate(
            name,
            arguments,
            default_risk=risk,
            mutates=mutates,
        )
        # Si l'outil n'est pas connu du PolicyEngine, utiliser le risque statique déclaré
        if evaluation.matched_rule_id == name and risk > evaluation.risk_level:
            evaluation.risk_level = risk
            if risk >= RiskLevel.HIGH:
                evaluation.allow_session_approval = False

        if evaluation.blocked:
            return False, f"Action bloquée par le Policy Engine : {evaluation.block_reason}"

        if self.mode == "PLAN" and (mutates or evaluation.mutates):
            return False, "PLAN MODE : aucune modification, commande ou suite mutatrice autorisée"

        if self.dry_run and (mutates or evaluation.mutates):
            return False, "dry-run : aucune modification ni commande exécutée"

        # Principe de proportionnalité :
        # 1. Toute action SAFE (READ_ONLY) passe immédiatement
        if not mutates and evaluation.risk_level <= RiskLevel.LOW:
            return True, "lecture ou observation sûre autorisée"

        # 2. Les actions opérateur simples à risque LOW passent sans friction sauf en mode STRICT
        if (
            name in self._LOW_FRICTION_OPERATOR_TOOLS
            and evaluation.risk_level <= RiskLevel.LOW
            and self.permission_level != PermissionLevel.STRICT.value
        ):
            return True, "action simple à faible risque autorisée directement"

        if self.mode == "EDIT" and name in {"write_file", "patch_file"} and self.permission_level != PermissionLevel.STRICT.value:
            return True, "autorisé par EDIT après affichage de l'aperçu"

        # Vérification des permissions de session (uniquement si mode != STRICT et risque < HIGH)
        if (
            self.permission_level == PermissionLevel.SESSION.value
            and evaluation.allow_session_approval
            and (
                name in self.session_approved_tools
                or evaluation.canonical_action in self.session_approved_tools
                or evaluation.category.lower() in self.session_approved_categories
            )
        ):
            return True, "autorisé pour cette session"

        # Mode autonome : si enforce_hitl_on_high_risk est activé ou si permission_level == AUTOMATIC,
        # seules les actions sûres / non destructives passent automatiquement.
        if self.autonomous or self.permission_level == PermissionLevel.AUTOMATIC.value:
            if self.enforce_hitl_on_high_risk and evaluation.risk_level >= RiskLevel.HIGH:
                pass  # Exige quand même la confirmation humaine ci-dessous
            elif self.autonomous:
                return True, "mode autonome explicitement activé"
            elif evaluation.risk_level <= RiskLevel.LOW:
                return True, "autorisé automatiquement (action sûre)"

        if self.confirm is None:
            return False, "confirmation utilisateur requise"

        try:
            decision = self._invoke_confirm(name, evaluation.risk_level, evaluation)
        except (EOFError, KeyboardInterrupt):
            return False, "confirmation interrompue"

        if isinstance(decision, str):
            norm_dec = decision.strip().lower()
            if norm_dec in {"allow_session", "allow_task", "session", "always", "allow_always"}:
                if evaluation.allow_session_approval and self.permission_level != PermissionLevel.STRICT.value:
                    self.grant_session_permission(tool_name=name, category=evaluation.category)
                    return True, "autorisé pour cette session par l'utilisateur"
                return True, "autorisé une fois par l'utilisateur (session refusée pour risque élevé)"
            if norm_dec in {"allow_once", "allow", "oui", "o", "yes", "y", "true", "1"}:
                return True, "autorisé par l'utilisateur"
            return False, "refusé par l'utilisateur"

        approved = bool(decision)
        return (
            (True, "autorisé par l'utilisateur")
            if approved
            else (False, "refusé par l'utilisateur")
        )

    def _invoke_confirm(
        self,
        name: str,
        risk: RiskLevel,
        evaluation: "PolicyEvaluation",
    ) -> Any:
        if self.confirm is None:
            return False
        try:
            sig = inspect.signature(self.confirm)
            params = list(sig.parameters.values())
            accepts_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
            positional_count = sum(
                1
                for p in params
                if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            )
            if accepts_varargs or positional_count >= 3:
                return self.confirm(name, risk, evaluation)
        except (ValueError, TypeError):
            pass
        return self.confirm(name, risk)