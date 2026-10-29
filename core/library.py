# RÔLE DE CE FICHIER :
# Bibliothèque intelligente (Agent Library) de NeoHarness AI :
# Espace central et persistant de connaissance, de documents et de mémoire de l'agent.
# Gère les documents (PDF, Word, LaTeX, HTML), notes éditoriales, ressources de code,
# et assure le lien bidirectionnel avec la mémoire persistante de l'agent.

from __future__ import annotations

import json
import mimetypes
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory import MemoryManager


@dataclass
class LibraryItem:
    id: str
    title: str
    category: str  # "Documents" | "Notes" | "Ressources" | "Mémoire"
    type: str      # "pdf" | "docx" | "tex" | "html" | "note" | "python" | "json" | "svg" | "rule" | "autre"
    path: str | None = None
    summary: str = ""
    content: str = ""
    tags: list[str] = field(default_factory=list)
    size_bytes: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    linked_memory_id: str | None = None
    pinned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LibraryManager:
    """Gestionnaire centralisé de la Bibliothèque intelligente NeoHarness."""

    RELATIVE_STORAGE_PATH = ".harness/library.json"

    def __init__(self, workspace_path: Path | str, memory_manager: "MemoryManager | None" = None) -> None:
        self.workspace_path = Path(workspace_path)
        self.storage_path = self.workspace_path / self.RELATIVE_STORAGE_PATH
        self.memory_manager = memory_manager
        self._lock = Lock()
        self._items: dict[str, LibraryItem] = {}
        self._load()
        self.sync_with_workspace()

    def _load(self) -> None:
        if not self.storage_path.is_file():
            self._items = {}
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for d in raw:
                    if isinstance(d, dict) and "id" in d and "title" in d:
                        item = LibraryItem(**{k: v for k, v in d.items() if k in LibraryItem.__dataclass_fields__})
                        self._items[item.id] = item
        except Exception:
            self._items = {}

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [item.to_dict() for item in self._items.values()]
            # Trier : épinglés d'abord, puis par date de mise à jour décroissante
            payload.sort(key=lambda x: (not x.get("pinned", False), x.get("updated_at", "")), reverse=True)
            self.storage_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def sync_with_workspace(self) -> list[dict[str, Any]]:
        """Indexe automatiquement les fichiers existants dans le workspace."""
        with self._lock:
            existing_paths = {item.path for item in self._items.values() if item.path}
            
            # Formats reconnus
            extensions = {
                ".pdf": ("Documents", "pdf"),
                ".docx": ("Documents", "docx"),
                ".tex": ("Documents", "tex"),
                ".html": ("Documents", "html"),
                ".htm": ("Documents", "html"),
                ".md": ("Notes", "note"),
                ".py": ("Ressources", "python"),
                ".json": ("Ressources", "json"),
                ".svg": ("Ressources", "svg"),
                ".csv": ("Ressources", "data"),
            }

            if self.workspace_path.is_dir():
                for p in self.workspace_path.iterdir():
                    if p.is_file() and not p.name.startswith("."):
                        ext = p.suffix.lower()
                        if ext in extensions and p.name not in existing_paths:
                            cat, typ = extensions[ext]
                            stat = p.stat()
                            item_id = f"lib-{uuid.uuid4().hex[:8]}"
                            title = p.stem.replace("_", " ").capitalize()
                            
                            snippet = ""
                            if ext in {".md", ".tex", ".py", ".json", ".csv"}:
                                try:
                                    snippet = p.read_text(encoding="utf-8", errors="replace")[:1000]
                                except Exception:
                                    pass

                            summary = f"Fichier {typ.upper()} dans l'espace de travail"
                            if ext == ".docx":
                                summary = "Document Word vérifié"
                            elif ext == ".pdf":
                                summary = "Document PDF compilé"

                            tags = [typ]
                            if "exercice" in p.name.lower():
                                tags.append("exercice")
                            if "bac" in p.name.lower():
                                tags.append("bac")

                            item = LibraryItem(
                                id=item_id,
                                title=title,
                                category=cat,
                                type=typ,
                                path=p.name,
                                summary=summary,
                                content=snippet,
                                tags=tags,
                                size_bytes=stat.st_size,
                                created_at=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat(),
                                updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                            )
                            self._items[item.id] = item

            self._save()
            return [it.to_dict() for it in self._items.values()]

    def list_items(
        self,
        *,
        category: str | None = None,
        tag: str | None = None,
        query: str = "",
    ) -> list[dict[str, Any]]:
        with self._lock:
            results = list(self._items.values())

        cat_filter = (category or "").strip().casefold()
        if cat_filter and cat_filter != "tous":
            results = [r for r in results if r.category.casefold() == cat_filter]

        tag_filter = (tag or "").strip().casefold()
        if tag_filter:
            results = [r for r in results if any(tag_filter in t.casefold() for t in r.tags)]

        needle = query.strip().casefold()
        if needle:
            from core.memory import MemoryManager

            scored_results: list[tuple[float, LibraryItem]] = []
            for r in results:
                hay = f"{r.title} {r.summary or ''} {r.path or ''} {' '.join(r.tags)} {(r.content or '')[:600]}".casefold()
                if needle in hay:
                    scored_results.append((1.0, r))
                else:
                    sim = MemoryManager.hybrid_semantic_score(needle, hay)
                    if sim >= 0.22:
                        scored_results.append((sim, r))
            scored_results.sort(key=lambda item: (item[1].pinned, item[0], item[1].updated_at), reverse=True)
            return [r.to_dict() for _, r in scored_results]

        results.sort(key=lambda x: (not x.pinned, x.updated_at), reverse=True)
        return [r.to_dict() for r in results]

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        with self._lock:
            it = self._items.get(item_id)
            return it.to_dict() if it else None

    def add_item(
        self,
        title: str,
        category: str = "Notes",
        item_type: str = "note",
        *,
        path: str | None = None,
        summary: str = "",
        content: str = "",
        tags: list[str] | None = None,
        linked_memory_id: str | None = None,
        pinned: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            clean_title = (title or "").strip()
            if not clean_title:
                clean_title = "Ressource sans titre"

            item_id = f"lib-{uuid.uuid4().hex[:8]}"
            size = len(content.encode("utf-8")) if content else 0
            if path:
                target_p = self.workspace_path / path
                if target_p.is_file():
                    size = target_p.stat().st_size

            item = LibraryItem(
                id=item_id,
                title=clean_title,
                category=category,
                type=item_type,
                path=path,
                summary=summary or f"{category} ajouté à la bibliothèque",
                content=content,
                tags=tags or [],
                size_bytes=size,
                linked_memory_id=linked_memory_id,
                pinned=pinned,
            )
            self._items[item_id] = item
            self._save()
            return item.to_dict()

    def update_item(
        self,
        item_id: str,
        *,
        title: str | None = None,
        category: str | None = None,
        summary: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        pinned: bool | None = None,
        linked_memory_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if item_id not in self._items:
                raise KeyError(f"Élément de bibliothèque introuvable : {item_id}")
            it = self._items[item_id]
            if title is not None and title.strip():
                it.title = title.strip()
            if category is not None and category.strip():
                it.category = category.strip()
            if summary is not None:
                it.summary = summary.strip()
            if content is not None:
                it.content = content
                if not it.path:
                    it.size_bytes = len(content.encode("utf-8"))
            if tags is not None:
                it.tags = tags
            if pinned is not None:
                it.pinned = bool(pinned)
            if linked_memory_id is not None:
                it.linked_memory_id = linked_memory_id
            it.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return it.to_dict()

    def delete_item(self, item_id: str) -> bool:
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                self._save()
                return True
            return False

    def toggle_pin(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            if item_id not in self._items:
                raise KeyError(f"Élément introuvable : {item_id}")
            it = self._items[item_id]
            it.pinned = not it.pinned
            it.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()
            return it.to_dict()

