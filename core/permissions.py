# RÔLE DE CE FICHIER :
# Applique les règles d'autorisation des outils avant toute écriture, exécution,
# suppression ou autre action qui change l'espace de travail.

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable


class RiskLevel(IntEnum):
    READ_ONLY = 0
    LOW = 1
    MODERATE = 2
    HIGH = 3
    DESTRUCTIVE = 4


@dataclass
class PermissionPolicy:
    """Les lectures passent; les actions mutantes demandent une décision."""

    confirm: Callable[[str, RiskLevel], bool] | None = None
    dry_run: bool = False
    autonomous: bool = False

    def authorize(self, name: str, risk: RiskLevel, mutates: bool) -> tuple[bool, str]:
        if not mutates and risk <= RiskLevel.LOW:
            return True, "lecture autorisée"
        if self.dry_run:
            return False, "dry-run : aucune modification ni commande exécutée"
        if self.autonomous:
            return True, "mode autonome explicitement activé"
        if self.confirm is None:
            return False, "confirmation utilisateur requise"
        try:
            approved = bool(self.confirm(name, risk))
        except (EOFError, KeyboardInterrupt):
            return False, "confirmation interrompue"
        return (
            (True, "autorisé par l'utilisateur")
            if approved
            else (False, "refusé par l'utilisateur")
        )

