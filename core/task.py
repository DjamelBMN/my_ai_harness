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
