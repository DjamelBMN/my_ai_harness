# RÔLE DE CE FICHIER :
# Sépare la mémoire de mission, de session et de projet. La mémoire de projet n'est
# persistée qu'après une demande explicite et une autorisation d'écriture.

from __future__ import annotations

import json
import re
from typing import Any

from tools.registry import ToolCall, ToolRegistry


_SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|secret|password|passwd|token|authorization)\s*[:=]\s*\S+"
)


class MemoryManager:
    PROJECT_PATH = ".harness/project_memory.json"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools
        self.session: list[str] = []
        self.decisions: list[str] = []
        self.preferences: dict[str, str] = {}
        self.project: list[str] = self._load_project()

    def _load_project(self) -> list[str]:
        try:
            raw = self.tools.filesystem.read_file(self.PROJECT_PATH)
            data = json.loads(raw)
            notes = data.get("notes", []) if isinstance(data, dict) else []
            return [item for item in notes if isinstance(item, str)][-100:]
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    def _validate(self, text: str) -> str:
        value = text.strip()
        if not value:
            raise ValueError("La mémoire ne peut pas être vide.")
        if _SENSITIVE.search(value) or self.tools.filesystem.contains_secret_text(value):
            raise ValueError("Écriture refusée : le texte semble contenir un secret.")
        return value

    def remember(self, scope: str, text: str) -> str:
        value = self._validate(text)
        if scope == "session":
            self.session.append(value)
            self.session[:] = self.session[-100:]
            return "Note ajoutée à la mémoire de session (temporaire)."
        if scope == "decision":
            self.decisions.append(value)
            self.decisions[:] = self.decisions[-100:]
            return "Décision conservée pour cette session."
        if scope == "preference":
            key, separator, preference = value.partition("=")
            if not separator or not key.strip() or not preference.strip():
                raise ValueError("Utilise le format clé=valeur pour une préférence.")
            self.preferences[key.strip()] = preference.strip()
            return "Préférence conservée pour cette session."
        if scope == "project":
            self.project.append(value)
            self.project[:] = self.project[-100:]
            payload = json.dumps({"notes": self.project}, ensure_ascii=False, indent=2)
            exists = self.tools.filesystem.resolve(self.PROJECT_PATH).exists()
            execution = self.tools.execute(
                ToolCall(
                    name="write_file",
                    arguments={
                        "path": self.PROJECT_PATH,
                        "content": payload,
                        "overwrite": exists,
                    },
                )
            )
            if execution.status != "success":
                self.project.pop()
                return f"Mémoire projet non enregistrée : {execution.summary}"
            return "Note ajoutée à la mémoire du projet après autorisation."
        raise ValueError("Portée inconnue. Utilise session, project, decision ou preference.")

    def clear_session(self) -> None:
        self.session.clear()
        self.decisions.clear()
        self.preferences.clear()
