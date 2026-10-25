"""Observable Artifact Verifier for NeoHarness AI.

Strict verification of real observable outputs (exit codes, binary headers,
DOM structures, XML trees, data tables). Never considers source code presence
alone as proof of execution or compilation.
"""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from core.artifacts.models import Artifact, ArtifactStatus, ArtifactType
from tools.filesystem import WorkspaceFilesystem


class ObservableArtifactVerifier:
    """Vérificateur d'artefacts basé exclusivement sur des résultats observables réels."""

    @staticmethod
    def verify(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        """Exécute une vérification stricte et retourne le bilan de vérification observable."""
        typ = artifact.type

        if typ == ArtifactType.PYTHON:
            return ObservableArtifactVerifier._verify_python(artifact, filesystem)
        elif typ in {ArtifactType.PDF, ArtifactType.LATEX}:
            return ObservableArtifactVerifier._verify_pdf_latex(artifact, filesystem)
        elif typ == ArtifactType.HTML:
            return ObservableArtifactVerifier._verify_html(artifact, filesystem)
        elif typ == ArtifactType.SVG:
            return ObservableArtifactVerifier._verify_svg(artifact, filesystem)
        elif typ == ArtifactType.MERMAID:
            return ObservableArtifactVerifier._verify_mermaid(artifact, filesystem)
        elif typ == ArtifactType.JSON:
            return ObservableArtifactVerifier._verify_json(artifact, filesystem)
        elif typ == ArtifactType.CSV:
            return ObservableArtifactVerifier._verify_csv(artifact, filesystem)
        elif typ == ArtifactType.IMAGE:
            return ObservableArtifactVerifier._verify_image(artifact, filesystem)
        else:
            return ObservableArtifactVerifier._verify_generic_file(artifact, filesystem)

    @staticmethod
    def _verify_python(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        if artifact.execution is None:
            return {
                "verified": False,
                "engine": "Python Observable Verifier",
                "error": "Aucune exécution enregistrée pour ce script.",
            }

        exit_code = artifact.execution.exit_code
        if exit_code != 0:
            return {
                "verified": False,
                "engine": "Python Observable Verifier",
                "exit_code": exit_code,
                "error": artifact.execution.stderr or f"Code de retour {exit_code}",
            }

        # Vérifier que les fichiers déclarés comme générés existent réellement et ne sont pas vides
        verified_outputs = []
        for out_rel in artifact.output_paths:
            try:
                resolved = filesystem.resolve(out_rel)
                if resolved.is_file() and resolved.stat().st_size > 0:
                    verified_outputs.append({
                        "path": out_rel,
                        "size_bytes": resolved.stat().st_size,
                    })
            except Exception:
                pass

        # Figures Matplotlib : chaque PNG déclaré doit exister et être structurellement valide
        from tools.python_runtime import validate_png

        figure_reports = []
        for fig_rel in artifact.metadata.get("figures", []) or []:
            try:
                report = validate_png(filesystem.resolve(fig_rel))
            except Exception as exc:
                report = {"valid": False, "error": str(exc)}
            report["path"] = fig_rel
            figure_reports.append(report)
            if not report.get("valid"):
                return {
                    "verified": False,
                    "engine": "Python Observable Verifier",
                    "exit_code": 0,
                    "error": f"Figure PNG invalide {fig_rel} : {report.get('error')}",
                    "figures": figure_reports,
                }

        return {
            "verified": True,
            "engine": "Python Observable Verifier",
            "figures": figure_reports,
            "exit_code": 0,
            "duration_ms": artifact.execution.duration_ms,
            "stdout_length": len(artifact.execution.stdout),
            "verified_outputs_count": len(verified_outputs),
            "verified_outputs": verified_outputs,
        }

    @staticmethod
    def _verify_pdf_latex(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        # Le PDF cible peut être dans output_paths ou être le primary_path si c'est un PDF direct
        target_pdf = None
        for p in [artifact.primary_path] + artifact.output_paths:
            if str(p).lower().endswith(".pdf"):
                target_pdf = p
                break

        if not target_pdf:
            return {
                "verified": False,
                "engine": "PDF/LaTeX Observable Verifier",
                "error": "Aucun fichier PDF produit par la compilation.",
            }

        try:
            resolved = filesystem.resolve(target_pdf)
            if not resolved.is_file():
                return {
                    "verified": False,
                    "engine": "PDF/LaTeX Observable Verifier",
                    "error": f"Fichier PDF introuvable sur disque : {target_pdf}",
                }
            size = resolved.stat().st_size
            if size == 0:
                return {
                    "verified": False,
                    "engine": "PDF/LaTeX Observable Verifier",
                    "error": f"Fichier PDF vide (0 octet) : {target_pdf}",
                }

            raw = filesystem.read_bytes(target_pdf)
            if not raw.startswith(b"%PDF-"):
                return {
                    "verified": False,
                    "engine": "PDF/LaTeX Observable Verifier",
                    "error": "En-tête PDF binaire manquant ou invalide (%PDF- attendu).",
                }
            if b"%%EOF" not in raw[-2048:]:
                return {
                    "verified": False,
                    "engine": "PDF/LaTeX Observable Verifier",
                    "error": "Remorque PDF binaire manquante (%%EOF attendu dans les derniers 2 Ko).",
                }

            page_count = len(re.findall(rb"/Type\s*/Page\b", raw))
            return {
                "verified": True,
                "engine": "PDF/LaTeX Observable Verifier",
                "pdf_path": target_pdf,
                "size_bytes": size,
                "page_count": max(1, page_count),
                "binary_header_ok": True,
                "binary_eof_ok": True,
            }
        except Exception as exc:
            return {
                "verified": False,
                "engine": "PDF/LaTeX Observable Verifier",
                "error": f"Erreur de validation binaire PDF : {exc}",
            }

    @staticmethod
    def _verify_html(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            content = filesystem.read_file(artifact.primary_path)
            if not content.strip():
                return {"verified": False, "engine": "HTML Observable Verifier", "error": "Fichier HTML vide."}

            lower = content.casefold()
            has_html_tag = "<html" in lower or "<!doctype" in lower or "<div" in lower or "<main" in lower
            if not has_html_tag:
                return {"verified": False, "engine": "HTML Observable Verifier", "error": "Structure HTML manquante."}

            # Vérifier l'équilibre des balises de script
            script_open = len(re.findall(r"<script\b", lower))
            script_close = len(re.findall(r"</script>", lower))
            if script_open != script_close:
                return {
                    "verified": False,
                    "engine": "HTML Observable Verifier",
                    "error": f"Balises <script> asymétriques ({script_open} ouvertes, {script_close} fermées).",
                }

            return {
                "verified": True,
                "engine": "HTML Observable Verifier",
                "size_bytes": len(content.encode("utf-8")),
                "scripts_count": script_open,
                "has_scripts": script_open > 0,
            }
        except Exception as exc:
            return {"verified": False, "engine": "HTML Observable Verifier", "error": str(exc)}

    @staticmethod
    def _verify_svg(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            content = filesystem.read_file(artifact.primary_path)
            root = ET.fromstring(content)
            tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag.lower() != "svg":
                return {
                    "verified": False,
                    "engine": "SVG Observable Verifier",
                    "error": f"Balise racine non-SVG : <{root.tag}>",
                }

            viewbox = root.attrib.get("viewBox", "")
            elements_count = len(list(root.iter()))
            return {
                "verified": True,
                "engine": "SVG Observable Verifier",
                "root_tag": "svg",
                "viewBox": viewbox,
                "elements_count": elements_count,
            }
        except Exception as exc:
            return {"verified": False, "engine": "SVG Observable Verifier", "error": f"XML invalide : {exc}"}

    @staticmethod
    def _verify_mermaid(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            content = filesystem.read_file(artifact.primary_path).strip()
            if not content:
                return {"verified": False, "engine": "Mermaid Observable Verifier", "error": "Diagramme Mermaid vide."}

            first_line = content.splitlines()[0].strip().lower()
            valid_prefixes = (
                "graph", "flowchart", "sequencediagram", "classdiagram", "statediagram",
                "erdiagram", "journey", "gantt", "pie", "quadrantchart", "gitgraph", "mindmap"
            )
            has_prefix = any(first_line.startswith(p) for p in valid_prefixes)
            if not has_prefix:
                return {
                    "verified": False,
                    "engine": "Mermaid Observable Verifier",
                    "error": f"Type de diagramme non reconnu en première ligne : '{first_line}'",
                }

            # Vérifier l'équilibre des parenthèses et crochets
            open_sq, close_sq = content.count("["), content.count("]")
            open_par, close_par = content.count("("), content.count(")")
            if open_sq != close_sq or open_par != close_par:
                return {
                    "verified": False,
                    "engine": "Mermaid Observable Verifier",
                    "error": f"Délimiteurs de nœuds asymétriques ([{open_sq}/{close_sq}], ({open_par}/{close_par})).",
                }

            return {
                "verified": True,
                "engine": "Mermaid Observable Verifier",
                "diagram_type": first_line.split()[0],
                "lines_count": len(content.splitlines()),
            }
        except Exception as exc:
            return {"verified": False, "engine": "Mermaid Observable Verifier", "error": str(exc)}

    @staticmethod
    def _verify_json(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            content = filesystem.read_file(artifact.primary_path)
            parsed = json.loads(content)
            is_arr = isinstance(parsed, list)
            items_count = len(parsed) if is_arr else len(parsed.keys())
            return {
                "verified": True,
                "engine": "JSON Observable Verifier",
                "root_type": "array" if is_arr else "object",
                "items_count": items_count,
            }
        except Exception as exc:
            return {"verified": False, "engine": "JSON Observable Verifier", "error": f"JSON invalide : {exc}"}

    @staticmethod
    def _verify_csv(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            content = filesystem.read_file(artifact.primary_path)
            lines = [l for l in content.splitlines() if l.strip()]
            if not lines:
                return {"verified": False, "engine": "CSV Observable Verifier", "error": "Fichier CSV vide."}

            first = lines[0]
            delim = ","
            if first.count(";") > first.count(","):
                delim = ";"
            elif first.count("\t") > first.count(","):
                delim = "\t"

            cols = len([c for c in first.split(delim)])
            return {
                "verified": True,
                "engine": "CSV Observable Verifier",
                "delimiter": delim,
                "rows_count": len(lines) - 1,
                "columns_count": cols,
            }
        except Exception as exc:
            return {"verified": False, "engine": "CSV Observable Verifier", "error": f"CSV invalide : {exc}"}

    @staticmethod
    def _verify_image(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            resolved = filesystem.resolve(artifact.primary_path)
            size = resolved.stat().st_size
            if size == 0:
                return {"verified": False, "engine": "Image Observable Verifier", "error": "Image vide (0 octet)."}

            # Vérifier les signatures binaires courantes (PNG, JPEG, GIF, BMP, WebP)
            raw = filesystem.read_bytes(artifact.primary_path)
            fmt = "unknown"
            if raw.startswith(b"\x89PNG\r\n\x1a\n"):
                fmt = "PNG"
            elif raw.startswith(b"\xff\xd8\xff"):
                fmt = "JPEG"
            elif raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a"):
                fmt = "GIF"
            elif raw.startswith(b"BM"):
                fmt = "BMP"
            elif len(raw) >= 12 and raw[0:4] == b"RIFF" and raw[8:12] == b"WEBP":
                fmt = "WEBP"

            return {
                "verified": fmt != "unknown",
                "engine": "Image Observable Verifier",
                "format": fmt,
                "size_bytes": size,
            }
        except Exception as exc:
            return {"verified": False, "engine": "Image Observable Verifier", "error": str(exc)}

    @staticmethod
    def _verify_generic_file(artifact: Artifact, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        try:
            resolved = filesystem.resolve(artifact.primary_path)
            return {
                "verified": resolved.is_file(),
                "engine": "Generic Observable Verifier",
                "size_bytes": resolved.stat().st_size if resolved.is_file() else 0,
            }
        except Exception as exc:
            return {"verified": False, "engine": "Generic Observable Verifier", "error": str(exc)}

