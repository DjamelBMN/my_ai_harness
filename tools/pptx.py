# RÔLE DE CE FICHIER :
# Génération et vérification physique de présentations PowerPoint (.pptx) via Pandoc.

from __future__ import annotations

import hashlib
import io
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree

from tools.docx import find_pandoc_binary
from tools.filesystem import WORKSPACE_ROOT, WorkspaceFilesystem


def verify_pptx_file(file_path: Path | str) -> dict[str, Any]:
    """Vérifie l'intégrité physique d'un fichier .pptx (archive ZIP valide avec structure OpenXML)."""
    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"Présentation PPTX introuvable : {file_path}")

    size = p.stat().st_size
    if size < 500:
        raise ValueError(f"Fichier PPTX corrompu ou trop petit ({size} octets).")

    with open(p, "rb") as f:
        data = f.read()
    if not data.startswith(b"PK\x03\x04"):
        raise ValueError("Le fichier généré n'est pas une archive ZIP/OpenXML PPTX valide.")

    sha256 = hashlib.sha256(data).hexdigest()
    slide_count = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        if "[Content_Types].xml" not in names:
            raise ValueError("Structure OpenXML invalide : [Content_Types].xml manquant.")
        slide_count = sum(1 for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))

    return {
        "valid": True,
        "size_bytes": size,
        "sha256": sha256,
        "slide_count": max(1, slide_count),
    }


def generate_pptx(
    content: str,
    output_path: str = "",
    *,
    title: str = "",
    workspace: str | Path = WORKSPACE_ROOT,
    project_root: str | Path | None = None,
    event_sink: Callable[[str, str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Génère une présentation PowerPoint (.pptx) via Pandoc à partir de texte Markdown."""
    if not content or not content.strip():
        raise ValueError("Le contenu Markdown de la présentation PPTX ne peut pas être vide.")

    pandoc_bin = find_pandoc_binary(project_root=project_root)
    if not pandoc_bin:
        raise RuntimeError("Binaire Pandoc introuvable. Installez Pandoc ou vérifiez runtime/pandoc/pandoc.exe.")

    fs = WorkspaceFilesystem(workspace)
    raw_out = (output_path or "").strip()
    if not raw_out:
        clean_title = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip().lower()).strip("_") if title else "presentation"
        raw_out = f"presentations/{clean_title or 'presentation'}.pptx"
    elif not raw_out.lower().endswith(".pptx"):
        raw_out += ".pptx"

    target = fs.resolve(raw_out)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Sauvegarde automatique du fichier compagnon .md pour édition 100% sans perte
    comp_md = target.with_suffix(".md")
    comp_md.write_text(content.strip(), encoding="utf-8")

    # Formatage du Markdown : titres de niveau 1 (#) ou traits d'union (---) créent les diapositives
    md_body = content.strip()
    if title and not re.search(r"^#\s+", md_body):
        md_body = f"% {title}\n% NeoHarness AI\n\n{md_body}"

    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as tmp_in:
        tmp_in.write(md_body)
        tmp_in_path = tmp_in.name

    try:
        cmd = [pandoc_bin, tmp_in_path, "-o", str(target), "-f", "markdown", "-t", "pptx"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=35)
        if res.returncode != 0:
            raise RuntimeError(f"Échec de Pandoc lors de la création du PPTX : {res.stderr[:600]}")

        verif = verify_pptx_file(target)
        rel_path = target.relative_to(fs.root).as_posix()

        artifact_dict = {
            "status": "success",
            "verified": True,
            "type": "pptx",
            "path": rel_path,
            "relative_path": rel_path,
            "size_bytes": verif["size_bytes"],
            "sha256": verif["sha256"],
            "slide_count": verif["slide_count"],
            "title": title or target.stem,
        }

        if event_sink:
            try:
                event_sink("ARTIFACT_READY", f"Présentation PowerPoint PPTX prête : {rel_path}", artifact_dict)
            except Exception:
                pass

        return artifact_dict
    finally:
        try:
            Path(tmp_in_path).unlink(missing_ok=True)
        except Exception:
            pass