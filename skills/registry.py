# RÔLE DE CE FICHIER :
# Découvre les dossiers Skill sans liste codée en dur. SkillRouter interroge ce
# registre pour résoudre une slash command vers son dossier métier.

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CANONICAL_SKILL_ORDER: tuple[str, ...] = (
    "analyze",
    "auto",
    "bacblanc",
    "compare",
    "context",
    "debug",
    "diagnostic",
    "export",
    "memory",
    "mode",
    "model",
    "plan",
    "refactor",
    "research",
    "review",
    "route",
    "test",
    "workflow",
)


@dataclass(frozen=True)
class SkillDescriptor:
    name: str
    path: Path
    manifest_path: Path


class SkillRegistry:
    """Découvre les Skills dont le dossier contient un skill.md non vide."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self._skills: dict[str, SkillDescriptor] = {}
        self.invalid: dict[str, str] = {}

    @classmethod
    def from_directory(cls, root: str | Path) -> "SkillRegistry":
        registry = cls(root)
        registry.discover()
        return registry

    @staticmethod
    def normalize(name: str) -> str:
        return re.sub(r"[^a-z0-9_-]+", "", name.strip().casefold())

    @staticmethod
    def canonical_sort_key(name: str) -> tuple[int, str]:
        normalized = SkillRegistry.normalize(name)
        try:
            index = CANONICAL_SKILL_ORDER.index(normalized)
        except ValueError:
            index = len(CANONICAL_SKILL_ORDER)
        return (index, normalized)

    def discover(self) -> list[SkillDescriptor]:
        self._skills.clear()
        self.invalid.clear()
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            self.invalid[str(self.root)] = "Le chemin des Skills n'est pas un dossier."
            return []

        for folder in sorted(
            self.root.iterdir(),
            key=lambda path: self.canonical_sort_key(path.name),
        ):
            if not folder.is_dir() or folder.name.startswith("_"):
                continue
            name = self.normalize(folder.name)
            manifest = folder / "skill.md"
            try:
                resolved = folder.resolve(strict=True)
                resolved.relative_to(self.root)
                resolved_manifest = manifest.resolve(strict=True)
                resolved_manifest.relative_to(resolved)
            except (OSError, ValueError):
                self.invalid[folder.name] = (
                    "Le dossier ou son manifeste sort de la racine autorisée du Skill."
                )
                continue
            if not manifest.is_file():
                continue
            try:
                content = manifest.read_text(encoding="utf-8-sig").strip()
                if not name or not content:
                    raise ValueError("Le nom ou le manifeste skill.md est vide.")
            except (OSError, UnicodeError, ValueError) as error:
                self.invalid[folder.name] = f"{type(error).__name__}: {error}"
                continue
            if name in self._skills:
                self.invalid[folder.name] = f"Nom de Skill dupliqué : {name}."
                continue
            descriptor = SkillDescriptor(name=name, path=resolved, manifest_path=resolved_manifest)
            self._skills[name] = descriptor
        return self.list_skills()

    def get(self, name: str) -> SkillDescriptor | None:
        return self._skills.get(self.normalize(name))

    def list_skills(self) -> list[SkillDescriptor]:
        ordered_names = sorted(self._skills, key=self.canonical_sort_key)
        return [self._skills[name] for name in ordered_names]

    @property
    def names(self) -> list[str]:
        return sorted(self._skills, key=self.canonical_sort_key)
