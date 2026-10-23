# RÔLE DE CE FICHIER :
# Parse les entrées slash et résout explicitement le Skill. main.py l'utilise
# avant tout AgentSelector/Planner afin qu'une slash command soit prioritaire.

from __future__ import annotations

import re
from dataclasses import dataclass

from skills.loader import SkillDefinition, SkillLoadError, SkillLoader
from skills.registry import SkillRegistry


class SkillCommandError(ValueError):
    """Commande slash inconnue ou mal formée; elle ne doit pas tomber au Planner."""


@dataclass(frozen=True)
class SkillCommand:
    name: str
    mission: str


@dataclass
class SkillLaunch:
    command: SkillCommand
    skill: SkillDefinition


class SkillRouter:
    COMMAND_PATTERN = re.compile(r"^/([a-zA-Z0-9_-]+)(?:\s+(.*))?$", re.DOTALL)

    def __init__(self, registry: SkillRegistry, loader: SkillLoader) -> None:
        self.registry = registry
        self.loader = loader

    @classmethod
    def parse(cls, message: str) -> SkillCommand | None:
        stripped = message.strip()
        if not stripped.startswith("/"):
            return None
        match = cls.COMMAND_PATTERN.fullmatch(stripped)
        if match is None:
            raise SkillCommandError("Commande slash mal formée. Utilise /nom_du_skill <mission>.")
        return SkillCommand(name=match.group(1).casefold(), mission=(match.group(2) or "").strip())

    def resolve(self, message: str) -> SkillLaunch | None:
        command = self.parse(message)
        if command is None:
            return None
        descriptor = self.registry.get(command.name)
        if descriptor is None:
            available = "\n".join(f"  /{name}" for name in self.registry.names) or "  (aucun)"
            reason = self.registry.invalid.get(command.name)
            detail = f"\nDétail : {reason}" if reason else ""
            raise SkillCommandError(
                f"Skill '/{command.name}' introuvable.{detail}\n\nSkills disponibles :\n{available}"
            )
        try:
            skill = self.loader.load(descriptor)
        except SkillLoadError as error:
            raise SkillCommandError(f"[SKILL ERROR] Impossible de charger /{command.name} : {error}") from None
        return SkillLaunch(command=command, skill=skill)
