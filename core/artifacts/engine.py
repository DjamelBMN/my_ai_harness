# RÔLE DE CE FICHIER :
# Moteur universel d'artefacts (Universal Artifact Engine) de NeoHarness AI.
# Orchestre le cycle de vie complet : détection, matérialisation, compilation,
# exécution réelle, vérification stricte, auto-réparation et diffusion SSE des artefacts.

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from core.artifacts.verifier import ObservableArtifactVerifier
from core.artifacts.handlers import (
    BaseArtifactHandler,
    CsvArtifactHandler,
    HtmlArtifactHandler,
    ImageArtifactHandler,
    JsonArtifactHandler,
    LatexArtifactHandler,
    MarkdownArtifactHandler,
    MermaidArtifactHandler,
    PdfArtifactHandler,
    PythonArtifactHandler,
    SvgArtifactHandler,
)
from core.artifacts.models import (
    Artifact,
    ArtifactStatus,
    ArtifactType,
    ArtifactVersion,
)
from tools.filesystem import WorkspaceFilesystem


class UniversalArtifactEngine:
    """Moteur central d'artefacts agentiques pour NeoHarness AI."""

    def __init__(self, event_bus: Any = None) -> None:
        self.event_bus = event_bus
        self.handlers: list[BaseArtifactHandler] = []
        self._history: dict[str, list[ArtifactVersion]] = {}
        self._artifact_cache: dict[str, Artifact] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Enregistre les 10 gestionnaires natifs dans l'ordre de priorité."""
        self.handlers = [
            HtmlArtifactHandler(),
            LatexArtifactHandler(),
            PythonArtifactHandler(),
            SvgArtifactHandler(),
            MermaidArtifactHandler(),
            JsonArtifactHandler(),
            CsvArtifactHandler(),
            MarkdownArtifactHandler(),
            ImageArtifactHandler(),
            PdfArtifactHandler(),
        ]

    def register_handler(self, handler: BaseArtifactHandler, index: int | None = None) -> None:
        """Permet l'extension dynamique du moteur avec de nouveaux formats sans toucher au cœur."""
        if index is not None:
            self.handlers.insert(index, handler)
        else:
            self.handlers.append(handler)

    def find_handler(self, path: str, content: str | None = None) -> BaseArtifactHandler | None:
        """Recherche le premier gestionnaire compatible pour un fichier ou contenu donné."""
        for handler in self.handlers:
            try:
                if handler.handles(path, content=content):
                    return handler
            except Exception:
                continue
        return None

    def process_file(
        self,
        relative_path: str,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 60,
    ) -> Artifact:
        """Traite (compile, valide ou exécute) un fichier réel du workspace et met à jour l'artefact."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        handler = self.find_handler(clean_rel)
        art_type = ArtifactType.from_extension_or_name(clean_rel)

        existing_versions = self._history.get(clean_rel, [])
        artifact = Artifact(
            id=f"art-{hashlib.sha256(clean_rel.encode()).hexdigest()[:8]}",
            title=Path(clean_rel).name,
            type=art_type,
            status=ArtifactStatus.PENDING,
            primary_path=clean_rel,
            source_paths=[clean_rel],
            versions=list(existing_versions),
        )

        # Émission SSE début de traitement
        if self.event_bus:
            self.event_bus.emit_normalized(
                event="TOOL_CALL",
                raw_event="artifact.process.started",
                tool="artifact_engine",
                summary=f"Traitement de l'artefact {art_type.value.upper()} : {clean_rel}",
                status="running",
                details={"path": clean_rel, "type": art_type.value},
            )

        if handler is None:
            artifact.status = ArtifactStatus.READY
            try:
                raw_bytes = filesystem.read_bytes(clean_rel)
                artifact.metadata = {"size_bytes": len(raw_bytes)}
                artifact.raw_url = f"/api/files/raw?path={clean_rel}"
                artifact.preview_url = f"/api/files/raw?path={clean_rel}"
            except Exception as e:
                artifact.status = ArtifactStatus.ERROR
                artifact.error = str(e)
            return artifact

        # Exécution réelle via le handler spécialisé
        processed = handler.process(
            artifact,
            filesystem,
            auto_repair=auto_repair,
            llm_provider=llm_provider,
            timeout_seconds=timeout_seconds,
        )

        # Vérification observable stricte des résultats réels (fichiers, codes retour, binaire)
        v_res = ObservableArtifactVerifier.verify(processed, filesystem)
        if not v_res.get("verified", False) and processed.status in {ArtifactStatus.READY, ArtifactStatus.REPAIRED}:
            processed.status = ArtifactStatus.ERROR
            processed.error = v_res.get("error", "Échec de la vérification observable du résultat produit.")
        processed.verification = v_res

        # Enregistrement dans l'historique des versions
        try:
            current_content = filesystem.read_file(clean_rel)
            ver = processed.record_version(current_content, summary=f"Mise à jour ({processed.status.value})")
            if clean_rel not in self._history:
                self._history[clean_rel] = []
            self._history[clean_rel].append(ver)
        except Exception:
            pass

        self._artifact_cache[clean_rel] = processed

        # Émission SSE fin de traitement
        if self.event_bus:
            if processed.status in {ArtifactStatus.READY, ArtifactStatus.REPAIRED}:
                self.event_bus.emit_normalized(
                    event="TOOL_RESULT",
                    raw_event="artifact.process.completed",
                    tool="artifact_engine",
                    summary=(
                        f"Artefact {processed.type.value.upper()} prêt : {clean_rel}"
                        + (" [réparé]" if processed.auto_repaired else "")
                    ),
                    status="completed",
                    details=processed.to_dict(),
                )
                self.event_bus.emit_normalized(
                    event="ARTIFACT_READY",
                    raw_event="artifact.ready",
                    summary=f"Artefact prêt pour visualisation : {clean_rel}",
                    status="completed",
                    details=processed.to_dict(),
                )
            else:
                self.event_bus.emit_normalized(
                    event="ERROR",
                    raw_event="artifact.process.error",
                    tool="artifact_engine",
                    summary=f"Erreur sur l'artefact {clean_rel} : {processed.error}",
                    status="error",
                    error=processed.error or "Échec de traitement de l'artefact",
                    details=processed.to_dict(),
                )

        return processed

    def execute_artifact(
        self,
        relative_path: str,
        filesystem: WorkspaceFilesystem,
        *,
        arguments: list[str] | None = None,
        timeout_seconds: int = 60,
    ) -> Artifact:
        """Exécute spécifiquement un artefact exécutable (ex: Python) et collecte ses sorties."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        art = self.process_file(
            clean_rel,
            filesystem,
            auto_repair=False,
            timeout_seconds=timeout_seconds,
        )
        return art

    def extract_and_materialize_blocks(
        self,
        prompt: str,
        answer_text: str,
        filesystem: WorkspaceFilesystem,
        *,
        can_write: bool = True,
    ) -> list[str]:
        """Extrait réellement tous les blocs de code produits par le modèle et les enregistre dans le workspace."""
        if not can_write or not answer_text:
            return []

        created_paths: list[str] = []
        prompt_lower = prompt.casefold()

        # Itération sur l'ensemble des blocs de code Markdown trouvés
        code_blocks = list(re.finditer(r"```([a-zA-Z0-9_-]*)\s*\r?\n([\s\S]*?)```", answer_text))

        for m in code_blocks:
            lang = m.group(1).lower().strip()
            code = m.group(2).strip()
            if not code:
                continue

            # 1. HTML / Web
            if (lang in ("html", "htm") or "<html" in code.casefold() or "<!doctype" in code.casefold()) and any(
                kw in prompt_lower for kw in ("html", "page web", "interface", "dashboard", "site", "web")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.html?)\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "index.html"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

            # 2. Python
            if (lang in ("python", "py") or "import " in code or "def " in code or "print(" in code or "plt." in code) and any(
                kw in prompt_lower for kw in ("python", "script", "programme", "graphique", "courbe", "simulation", "tracé", "calcul")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.py)\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "script.py"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

            # 3. Mermaid
            if (lang in ("mermaid", "mmd") or any(code.strip().lower().startswith(p) for p in MermaidArtifactHandler.VALID_DIAGRAM_PREFIXES)) and any(
                kw in prompt_lower for kw in ("mermaid", "diagramme", "organigramme", "flowchart", "sequence", "uml")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.(?:mmd|mermaid))\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "diagram.mmd"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

            # 4. SVG
            if (lang == "svg" or "<svg" in code.casefold()) and any(
                kw in prompt_lower for kw in ("svg", "vecteur", "icone", "logo", "dessin")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.svg)\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "graphic.svg"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

            # 5. JSON
            if (lang == "json" or (code.startswith("{") and code.endswith("}"))) and any(
                kw in prompt_lower for kw in ("json", "données", "schema", "config")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.json)\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "data.json"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

            # 6. CSV
            if (lang in ("csv", "tsv") or ("," in code and "\n" in code)) and any(
                kw in prompt_lower for kw in ("csv", "tableur", "tableau", "données")
            ):
                m_name = re.search(r"\b([a-zA-Z0-9_-]+\.csv)\b", prompt, re.IGNORECASE)
                rel = m_name.group(1) if m_name else "data.csv"
                if rel not in created_paths:
                    filesystem.write_file(rel, code, overwrite=True)
                    created_paths.append(rel)
                continue

        return created_paths

    def get_history(self, relative_path: str) -> list[ArtifactVersion]:
        """Retourne l'historique complet des versions pour un artefact."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        return list(self._history.get(clean_rel, []))

    def rollback(self, relative_path: str, version_id: int, filesystem: WorkspaceFilesystem) -> Artifact:
        """Restaure une version antérieure d'un artefact."""
        clean_rel = relative_path.replace("\\", "/").lstrip("/")
        versions = self._history.get(clean_rel, [])
        target = next((v for v in versions if v.version_id == version_id), None)
        if not target:
            raise ValueError(f"Version #{version_id} introuvable pour {clean_rel}.")

        filesystem.write_file(clean_rel, target.source_content_snippet, overwrite=True)
        return self.process_file(clean_rel, filesystem, auto_repair=False)
