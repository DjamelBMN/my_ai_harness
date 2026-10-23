# RÔLE DE CE FICHIER :
# Contient le petit contexte partagé pendant l'exécution. L'Orchestrator y note la
# tâche et le résultat ; les Agents transmettent ce contexte au LLM choisi.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.task import Task


@dataclass
class Context:
    """État léger de la session, sans mémoire persistante ni logique avancée."""

    history: list[str] = field(default_factory=list)
    current_task: Task | None = None
    agent_results: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)

    def describe(self) -> str:
        """Produit une description courte du contexte pour l'agent."""
        details = []
        if self.files:
            details.append("Fichiers concernés : " + ", ".join(self.files))
        if self.history:
            details.append("Échanges précédents : " + " | ".join(self.history[-3:]))
        return "; ".join(details)
