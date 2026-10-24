# RÔLE DE CE FICHIER : définit les modes globaux du Harness et les applique à la
# politique de permissions partagée par tous les Skills et agents.

from __future__ import annotations

from enum import StrEnum
import sys
from typing import Callable


class HarnessMode(StrEnum):
    EDIT = "EDIT"
    PLAN = "PLAN"
    ACCEPT = "ACCEPT"
    AUTO = "AUTO"


class ModeManager:
    """Source centrale du mode actif et de son effet sur les permissions."""

    CYCLE = (
        HarnessMode.EDIT,
        HarnessMode.PLAN,
        HarnessMode.ACCEPT,
        HarnessMode.AUTO,
    )
    DESCRIPTIONS = {
        HarnessMode.EDIT: "Modifications directes, avec aperçu et protections globales.",
        HarnessMode.PLAN: "Planification et lecture uniquement; aucune mutation autorisée.",
        HarnessMode.ACCEPT: "Les actions sensibles demandent une confirmation.",
        HarnessMode.AUTO: "Enchaînement autonome via les permissions prévues par le Harness.",
    }
    SHORT_DESCRIPTIONS = {
        HarnessMode.EDIT: "Modification directe",
        HarnessMode.PLAN: "Aucune modification",
        HarnessMode.ACCEPT: "Confirmation requise",
        HarnessMode.AUTO: "Permissions autonomes",
    }

    def __init__(
        self,
        permissions,
        initial_mode: str | HarnessMode = HarnessMode.ACCEPT,
        *,
        hard_dry_run: bool | None = None,
        explicit_autonomous: bool | None = None,
        on_change: Callable[[HarnessMode, HarnessMode], None] | None = None,
    ) -> None:
        self.permissions = permissions
        self.hard_dry_run = (
            permissions.dry_run if hard_dry_run is None else bool(hard_dry_run)
        )
        # Preserve the legacy --autonomous override separately from the mode.
        # Selecting AUTO activates the existing permission capability; leaving
        # AUTO turns it back off unless the user explicitly enabled the flag.
        self.explicit_autonomous = (
            bool(permissions.autonomous)
            if explicit_autonomous is None
            else bool(explicit_autonomous)
        )
        self.on_change = on_change
        self.current = HarnessMode.ACCEPT
        self.set_mode(initial_mode, announce=False)

    @staticmethod
    def normalize(value: str | HarnessMode) -> HarnessMode:
        try:
            return value if isinstance(value, HarnessMode) else HarnessMode(value.strip().upper())
        except (ValueError, AttributeError):
            allowed = ", ".join(mode.value.lower() for mode in HarnessMode)
            raise ValueError(f"Mode inconnu. Modes disponibles : {allowed}.") from None

    def set_mode(
        self,
        value: str | HarnessMode,
        *,
        announce: bool = True,
    ) -> tuple[HarnessMode, HarnessMode]:
        previous = self.current
        selected = self.normalize(value)
        self.current = selected
        self.permissions.mode = selected.value
        self.permissions.dry_run = self.hard_dry_run or selected is HarnessMode.PLAN
        self.permissions.autonomous = (
            self.explicit_autonomous or selected is HarnessMode.AUTO
        )
        if announce and previous is not selected and self.on_change is not None:
            self.on_change(previous, selected)
        return previous, selected

    def advance(self) -> tuple[HarnessMode, HarnessMode]:
        index = self.CYCLE.index(self.current)
        return self.set_mode(self.CYCLE[(index + 1) % len(self.CYCLE)])

    @classmethod
    def help_table(cls) -> str:
        rows = (
            ("EDIT", "Modification directe"),
            ("PLAN", "Planification sans modification"),
            ("ACCEPT", "Modification avec confirmation"),
            ("AUTO", "Exécution autonome selon permissions"),
        )
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            "╺─│".encode(encoding)
            unicode = True
        except (LookupError, UnicodeEncodeError):
            unicode = False
        if not unicode:
            border = "+----------+-----------------------------------+"
            return "\n".join(
                [
                    "+------------------------------------------+",
                    "|              MODES DU HARNESS            |",
                    border,
                    *(f"| {name:<8} | {description:<33} |" for name, description in rows),
                    border,
                ]
            )
        return "\n".join(
            [
                "╭──────────────────────────────────────────────╮",
                "│              MODES DU HARNESS                │",
                "├──────────┬───────────────────────────────────┤",
                *(f"│ {name:<8} │ {description:<33} │" for name, description in rows),
                "╰──────────┴───────────────────────────────────╯",
            ]
        )
