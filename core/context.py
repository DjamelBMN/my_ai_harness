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
    """Contexte isolé à la session, plus résumé explicite de la dernière mission."""

    history: list[str] = field(default_factory=list)
    current_task: Task | None = None
    agent_results: dict[str, str] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    last_result: str = ""
    mission_memory: dict[str, object] = field(default_factory=dict)
    last_skill: str = ""
    skill_rag_resources: list[str] = field(default_factory=list)
    skill_templates: list[str] = field(default_factory=list)
    task_context: Any | None = None

    def sync_task_context(self, tc: Any) -> None:
        """Synchronise le contexte d'exécution avec le TaskContext de la tâche active."""
        self.task_context = tc
        if tc is not None:
            if getattr(tc, "last_skill", ""):
                self.last_skill = tc.last_skill
            for f in getattr(tc, "files", []):
                if f not in self.files:
                    self.files.append(f)

    def remember_file(self, path: str, snippet: str = "") -> None:
        """Enregistre un fichier dans le contexte actif et conserve un extrait si fourni."""
        if path not in self.files:
            self.files.append(path)
        if self.task_context is not None and hasattr(self.task_context, "record_file"):
            self.task_context.record_file(path)
        if snippet:
            self.history.append(f"[Fichier joint {path}]: {snippet[:1000]}")

    def describe(self) -> str:
        """Produit une description courte du contexte pour l'agent."""
        details = []
        if self.task_context is not None and hasattr(self.task_context, "describe_for_agent"):
            tc_desc = self.task_context.describe_for_agent()
            if tc_desc:
                details.append(f"Tâche active : {tc_desc}")
        if self.files:
            details.append("Fichiers concernés : " + ", ".join(self.files))
        if self.history:
            details.append("Échanges précédents : " + " | ".join(self.history[-3:]))
        return "; ".join(details)
