# RÔLE DE CE FICHIER :
# Modèles de données centraux de l'Universal Artifact Engine de NeoHarness AI.
# Définit la structure unifiée, typée et sérialisable de tout artefact généré,
# compilé, exécuté ou visualisé dans l'environnement agentique.

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactType(str, Enum):
    """Types d'artefacts pris en charge de manière réelle par l'Universal Artifact Engine."""
    HTML = "html"
    PDF = "pdf"
    LATEX = "latex"
    PYTHON = "python"
    MARKDOWN = "markdown"
    SVG = "svg"
    MERMAID = "mermaid"
    JSON = "json"
    CSV = "csv"
    IMAGE = "image"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension_or_name(cls, path_or_ext: str) -> ArtifactType:
        ext = Path(path_or_ext).suffix.lower()
        if not ext and path_or_ext.startswith("."):
            ext = path_or_ext.lower()
        mapping = {
            ".html": cls.HTML,
            ".htm": cls.HTML,
            ".pdf": cls.PDF,
            ".tex": cls.LATEX,
            ".py": cls.PYTHON,
            ".md": cls.MARKDOWN,
            ".markdown": cls.MARKDOWN,
            ".svg": cls.SVG,
            ".mmd": cls.MERMAID,
            ".mermaid": cls.MERMAID,
            ".json": cls.JSON,
            ".csv": cls.CSV,
            ".tsv": cls.CSV,
            ".png": cls.IMAGE,
            ".jpg": cls.IMAGE,
            ".jpeg": cls.IMAGE,
            ".webp": cls.IMAGE,
            ".gif": cls.IMAGE,
            ".bmp": cls.IMAGE,
            ".ico": cls.IMAGE,
        }
        return mapping.get(ext, cls.UNKNOWN)


class ArtifactStatus(str, Enum):
    """Cycle de vie réel d'un artefact."""
    PENDING = "pending"
    COMPILING = "compiling"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    READY = "ready"
    ERROR = "error"
    REPAIRED = "repaired"


@dataclass
class ArtifactExecution:
    """Métadonnées d'exécution ou de compilation d'un artefact."""
    command: str = ""
    timeout_seconds: int = 60
    exit_code: int | None = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    environment_summary: str = ""
    log: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ArtifactVersion:
    """Instantané d'une version dans l'historique d'un artefact."""
    version_id: int
    timestamp: str
    source_hash: str
    source_content_snippet: str
    status: str
    error: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Artifact:
    """Entité universelle d'artefact de NeoHarness AI."""
    id: str
    title: str
    type: ArtifactType
    status: ArtifactStatus
    primary_path: str
    source_paths: list[str] = field(default_factory=list)
    output_paths: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    execution: ArtifactExecution | None = None
    verification: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    auto_repaired: bool = False
    repair_notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_url: str = ""
    preview_url: str = ""
    versions: list[ArtifactVersion] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_version(self, source_content: str, summary: str = "") -> ArtifactVersion:
        version_num = len(self.versions) + 1
        h = hashlib.sha256(source_content.encode("utf-8", errors="replace")).hexdigest()[:16]
        snippet = source_content[:500] if len(source_content) > 500 else source_content
        ver = ArtifactVersion(
            version_id=version_num,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_hash=h,
            source_content_snippet=snippet,
            status=self.status.value,
            error=self.error,
            summary=summary or f"Version #{version_num}",
        )
        self.versions.append(ver)
        self.updated_at = ver.timestamp
        return ver

    def to_dict(self) -> dict[str, Any]:
        """Convertit l'artefact en dictionnaire complet pour l'UI, les événements SSE et l'API."""
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "status": self.status.value,
            "path": self.primary_path,
            "primary_path": self.primary_path,
            "source_paths": list(self.source_paths),
            "output_paths": list(self.output_paths),
            "dependencies": list(self.dependencies),
            "execution": self.execution.to_dict() if self.execution else None,
            "verification": dict(self.verification),
            "error": self.error,
            "auto_repaired": self.auto_repaired,
            "repair_notes": list(self.repair_notes),
            "metadata": dict(self.metadata),
            "raw_url": self.raw_url,
            "preview_url": self.preview_url,
            "versions_count": len(self.versions),
            "versions": [v.to_dict() for v in self.versions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "timestamp": self.updated_at,
        }
        # Aplatir les champs usuels pour compatibilité totale avec le frontend existant
        if "size_bytes" in self.metadata:
            data["size_bytes"] = self.metadata["size_bytes"]
            data["bytes"] = self.metadata["size_bytes"]
        if "page_count" in self.metadata:
            data["page_count"] = self.metadata["page_count"]
            data["pages"] = self.metadata["page_count"]
        if "source_tex" in self.metadata:
            data["source_tex"] = self.metadata["source_tex"]
            data["source_path"] = self.metadata["source_tex"]
        if "compiler" in self.metadata:
            data["compiler"] = self.metadata["compiler"]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Artifact:
        exec_data = data.get("execution")
        exec_obj = ArtifactExecution(**exec_data) if isinstance(exec_data, dict) else None
        vers_data = data.get("versions", [])
        vers_list = [
            ArtifactVersion(**v) if isinstance(v, dict) else v
            for v in vers_data
        ]
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            type=ArtifactType(data.get("type", "unknown")),
            status=ArtifactStatus(data.get("status", "pending")),
            primary_path=data.get("primary_path") or data.get("path") or "",
            source_paths=list(data.get("source_paths") or []),
            output_paths=list(data.get("output_paths") or []),
            dependencies=list(data.get("dependencies") or []),
            execution=exec_obj,
            verification=dict(data.get("verification") or {}),
            error=data.get("error"),
            auto_repaired=bool(data.get("auto_repaired", False)),
            repair_notes=list(data.get("repair_notes") or []),
            metadata=dict(data.get("metadata") or {}),
            raw_url=data.get("raw_url", ""),
            preview_url=data.get("preview_url", ""),
            versions=vers_list,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

