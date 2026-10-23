# RÔLE DE CE FICHIER :
# Charge les instructions, règles, options YAML, agent et chemins RAG/templates
# d'un Skill. SkillRouter l'appelle seulement après une résolution explicite.

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

from core.agent import Agent
from skills.registry import SkillDescriptor


class SkillLoadError(RuntimeError):
    """Un Skill découvert n'a pas pu être chargé ou validé."""


@dataclass
class SkillDefinition:
    name: str
    display_name: str
    description: str
    path: Path
    instructions: str
    rules: str
    agent: Agent | None
    tools: list[str] = field(default_factory=list)
    rag_path: Path | None = None
    rag_resources: list[Path] = field(default_factory=list)
    templates: list[str] = field(default_factory=list)
    available_templates: list[Path] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def relative_path(self) -> str:
        return self.path.as_posix()


class SkillLoader:
    def __init__(self, skills_root: str | Path) -> None:
        self.root = Path(skills_root).expanduser().resolve()

    def load(self, descriptor: SkillDescriptor) -> SkillDefinition:
        path = descriptor.path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError:
            raise SkillLoadError("Le chemin du Skill sort de skills/.") from None
        if not (path / "skill.md").is_file():
            raise SkillLoadError(f"Le manifeste de /{descriptor.name} est absent.")

        try:
            manifest_path = self._safe_file(path, "skill.md", descriptor.name, required=True)
            instructions = manifest_path.read_text(encoding="utf-8-sig").strip()
            rules_path = self._safe_file(path, "rules.md", descriptor.name)
            rules = rules_path.read_text(encoding="utf-8-sig").strip() if rules_path.is_file() else ""
            config_path = self._safe_file(path, "config.yaml", descriptor.name)
            config = self._load_yaml(config_path) if config_path.is_file() else {}
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as error:
            raise SkillLoadError(f"Impossible de lire /{descriptor.name} : {error}") from None

        if not isinstance(config, dict):
            raise SkillLoadError(f"config.yaml de /{descriptor.name} doit contenir un objet YAML.")
        name = str(config.get("name") or descriptor.name).strip().casefold()
        if name != descriptor.name:
            raise SkillLoadError(
                f"Le dossier /{descriptor.name} déclare le nom incompatible '{name}'."
            )
        description = str(config.get("description") or self._first_heading(instructions) or name)
        agent = self._load_agent(path, config, descriptor.name)
        allowed_tools = self._string_list(config.get("tools", []), "tools", descriptor.name)
        templates = self._string_list(config.get("templates", []), "templates", descriptor.name)
        rag_path = (path / str(config.get("rag_directory", "rag"))).resolve()
        try:
            rag_path.relative_to(path)
        except ValueError:
            raise SkillLoadError(f"Le chemin RAG de /{descriptor.name} sort de son dossier.") from None
        if not rag_path.exists():
            rag_path.mkdir(parents=True, exist_ok=True)
        rag_resources = self._list_files_inside(rag_path)
        templates_dir = (path / "templates").resolve()
        try:
            templates_dir.relative_to(path)
        except ValueError:
            raise SkillLoadError(f"Le chemin templates de /{descriptor.name} sort de son dossier.") from None
        available_templates = self._list_files_inside(templates_dir) if templates_dir.is_dir() else []

        if agent is not None:
            agent.skill_name = name
            agent.skill_display_name = str(config.get("display_name") or name)
            agent.skill_instructions = instructions
            agent.skill_rules = rules
            agent.skill_config = dict(config)
            agent.skill_rag_path = rag_path
            agent.skill_rag_resources = list(rag_resources)
            agent.skill_templates = list(templates)
            agent.skill_available_templates = list(available_templates)
            agent.skill_source_path = (
                Path(self.root.name) / path.relative_to(self.root) / "skill.md"
            ).as_posix()
            agent.allowed_tools = tuple(allowed_tools)

        return SkillDefinition(
            name=name,
            display_name=str(config.get("display_name") or name),
            description=description,
            path=path,
            instructions=instructions,
            rules=rules,
            agent=agent,
            tools=allowed_tools,
            rag_path=rag_path,
            rag_resources=rag_resources,
            templates=templates,
            available_templates=available_templates,
            config=config,
        )

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError("La configuration YAML doit être une table de clés/valeurs.")
        return parsed

    @staticmethod
    def _string_list(value: Any, field_name: str, skill_name: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SkillLoadError(f"{field_name} de /{skill_name} doit être une liste de chaînes.")
        return [item.strip() for item in value if item.strip()]

    @staticmethod
    def _first_heading(markdown: str) -> str:
        for line in markdown.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    @staticmethod
    def _safe_file(
        skill_path: Path,
        relative_name: str,
        skill_name: str,
        *,
        required: bool = False,
    ) -> Path:
        candidate = skill_path / relative_name
        try:
            resolved = candidate.resolve(strict=required)
            resolved.relative_to(skill_path)
        except (OSError, ValueError):
            raise SkillLoadError(
                f"Le fichier {relative_name} de /{skill_name} sort du dossier du Skill ou est inaccessible."
            ) from None
        return resolved

    @staticmethod
    def _list_files_inside(directory: Path) -> list[Path]:
        """Énumère les fichiers du Skill sans suivre un lien vers l'extérieur."""
        root = directory.resolve()
        files = []
        for item in directory.rglob("*"):
            if item.name == ".gitkeep" or not item.is_file():
                continue
            try:
                resolved = item.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError):
                continue
            files.append(resolved)
        return sorted(files)

    @staticmethod
    def _module_from_file(path: Path, module_name: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise SkillLoadError(f"Impossible de créer un module Python pour {path.name}.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        return module

    def _load_agent(self, path: Path, config: dict, skill_name: str) -> Agent | None:
        try:
            agent_path = self._safe_file(path, "agent.py", skill_name)
        except SkillLoadError:
            raise
        if not agent_path.is_file():
            return None
        safe_name = re.sub(r"[^a-z0-9_]", "_", skill_name.casefold())
        try:
            module = self._module_from_file(agent_path, f"my_ai_harness_skill_{safe_name}_agent")
            candidates = [
                value for value in vars(module).values()
                if isinstance(value, type)
                and value is not Agent
                and issubclass(value, Agent)
                and value.__module__ == module.__name__
            ]
            desired = config.get("agent_class")
            if desired:
                candidates = [item for item in candidates if item.__name__ == desired]
            if len(candidates) != 1:
                raise SkillLoadError(
                    f"agent.py de /{skill_name} doit définir exactement un Agent compatible."
                )
            return candidates[0]()
        except SkillLoadError:
            raise
        except Exception as error:
            raise SkillLoadError(
                f"Impossible de charger l'agent du Skill /{skill_name} : {type(error).__name__}: {error}"
            ) from None
