# RÔLE DE CE FICHIER :
# Définit les informations d'une demande utilisateur. main.py crée une Task et
# l'Orchestrator la transmet à l'agent spécialisé.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.context import Context


@dataclass
class Task:
    """Demande à traiter, type d'agent souhaité et contexte facultatif."""

    description: str
    type: str = "researcher"
    context: Context | None = None
    explicit_agent: bool = False
    skill: object | None = None
    instructions: str = ""
    allowed_tools: tuple[str, ...] | None = None
    mode: str = "ACCEPT"
    skill_name: str | None = None
    task_context: Any | None = None


def ensure_task(
    task: Task | str,
    *,
    default_type: str = "researcher",
    mode: str = "ACCEPT",
    task_context: Any | None = None,
) -> Task:
    """Normalise une demande brute (str) ou vérifie qu'il s'agit bien d'une instance Task."""
    if isinstance(task, Task):
        if not isinstance(task.description, str):
            task.description = str(task.description or "")
        if task_context is not None and task.task_context is None:
            task.task_context = task_context
        return task
    if isinstance(task, str):
        return Task(description=task, type=default_type, mode=mode, task_context=task_context)
    raise TypeError(
        f"Contrat invalide : une instance de Task ou une chaîne (str) est attendue, reçu {type(task).__name__}."
    )
