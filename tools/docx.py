# RÔLE DE CE FICHIER :
# Génération de documents Word (.docx) professionnels via Pandoc et vérification physique stricte.
# Pipeline : contenu (Markdown) → Pandoc → DOCX → vérification physique → ARTIFACT_READY.
# Vérifications requises :
#   - fichier présent sur le disque ;
#   - taille > 0 ;
#   - signature ZIP 'PK' ;
#   - présence de [Content_Types].xml ;
#   - présence de word/document.xml.

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any, Callable

from core.artifact_intent import suggest_filename


class DocxVerificationError(ValueError):
    """Levée lorsqu'un fichier DOCX échoue aux contrôles physiques d'intégrité."""
    pass


def find_pandoc_binary(project_root: Path | str | None = None) -> str | None:
    """Localise le binaire Pandoc selon l'ordre de priorité spécifié :
    1. runtime/pandoc/pandoc.exe (dans le projet)
    2. Variable d'environnement PANDOC_PATH
    3. PATH système
    """
    root = Path(project_root or ".").resolve()

    # 1. runtime/pandoc/pandoc.exe local au projet
    local_candidates = [
        root / "runtime" / "pandoc" / "pandoc.exe",
        root / "runtime" / "pandoc" / "pandoc",
    ]
    for cand in local_candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)

    # 2. PANDOC_PATH
    env_pandoc = os.environ.get("PANDOC_PATH")
    if env_pandoc:
        p = Path(env_pandoc).resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)

    # 3. PATH système
    which_pandoc = shutil.which("pandoc")
    if which_pandoc:
        return which_pandoc

    return None


def verify_docx_file(file_path: Path | str) -> dict[str, Any]:
    """Contrôle physique strict de conformité et d'intégrité d'un fichier DOCX."""
    path = Path(file_path).resolve()
    if not path.is_file():
        raise DocxVerificationError(f"Le fichier DOCX n'existe pas sur le disque : {path}")

    size = path.stat().st_size
    if size <= 0:
        raise DocxVerificationError(f"Le fichier DOCX est vide (taille 0 octet) : {path}")

    raw_bytes = path.read_bytes()

    # Signature ZIP 'PK' (0x50, 0x4B)
    if not raw_bytes.startswith(b"PK"):
        raise DocxVerificationError(f"Signature ZIP 'PK' absente; le fichier n'est pas un archive DOCX valide : {path}")

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names:
                raise DocxVerificationError(
                    f"Fichier de manifest OpenXML obligatoire '[Content_Types].xml' manquant dans {path.name}."
                )
            if "word/document.xml" not in names:
                raise DocxVerificationError(
                    f"Fichier de contenu OpenXML obligatoire 'word/document.xml' manquant dans {path.name}."
                )
    except zipfile.BadZipFile as exc:
        raise DocxVerificationError(f"Archive ZIP corrompue pour {path.name} : {exc}") from exc

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return {
        "valid": True,
        "path": str(path),
        "size_bytes": size,
        "sha256": sha256,
        "manifest_present": True,
        "document_xml_present": True,
    }


def _emit_event(event_sink: Callable[..., Any] | None, event_name: str, **kwargs: Any) -> None:
    """Émet un événement vers le sink s'il est fourni."""
    if event_sink is not None:
        try:
            event_sink(event_name, kwargs)
        except TypeError:
            try:
                from core.event_bus import HarnessEvent
                event_sink(HarnessEvent(name=event_name, data=kwargs))
            except Exception:
                pass
        except Exception:
            pass


def generate_docx(
    content: str,
    output_path: str = "",
    title: str = "",
    workspace: Path | str = "workspace",
    event_sink: Callable[..., Any] | None = None,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Génère un document Word DOCX à partir de contenu Markdown via Pandoc.
    Vérifie physiquement le résultat et émet ARTIFACT_READY.
    """
    ws = Path(workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)

    # Détermination du nom de fichier adapté au contenu
    if not output_path or not output_path.lower().endswith(".docx"):
        clean_title = title or content[:80]
        filename = suggest_filename(clean_title, "docx", content=content, fallback="document")
        if output_path and not output_path.lower().endswith(".docx"):
            out_rel = str(PurePosixPath(output_path) / filename)
        else:
            out_rel = filename
    else:
        out_rel = output_path.replace("\\", "/")

    target_abs = (ws / out_rel).resolve()
    target_abs.parent.mkdir(parents=True, exist_ok=True)

    _emit_event(event_sink, "tool.started", tool="generate_docx", target=out_rel)

    pandoc_bin = find_pandoc_binary(project_root=project_root)
    if not pandoc_bin:
        # Repli de secours : générateur OpenXML standard si Pandoc n'est pas installé
        import html
        from io import BytesIO
        paragraphs = "".join(
            f'<w:p><w:r><w:t xml:space="preserve">{html.escape(line, quote=False)}</w:t></w:r></w:p>'
            for line in (content.splitlines() or [""])
        )
        doc_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>'
        types_xml = '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
        rels_xml = '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'

        with zipfile.ZipFile(target_abs, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", types_xml)
            archive.writestr("_rels/.rels", rels_xml)
            archive.writestr("word/document.xml", doc_xml)
    else:
        # Exécution de Pandoc : markdown -> docx
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tmp_md:
            tmp_md.write(content)
            tmp_md_path = Path(tmp_md.name)

        try:
            cmd = [
                pandoc_bin,
                str(tmp_md_path),
                "-f", "markdown",
                "-t", "docx",
                "-o", str(target_abs),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Échec Pandoc (code {proc.returncode}) : {proc.stderr or proc.stdout}"
                )
        finally:
            if tmp_md_path.is_file():
                try:
                    tmp_md_path.unlink()
                except OSError:
                    pass

    # Vérification physique obligatoire du DOCX généré
    verif = verify_docx_file(target_abs)

    result = {
        "status": "success",
        "path": str(target_abs),
        "relative_path": out_rel,
        "format": "docx",
        "title": title or target_abs.stem,
        "size_bytes": verif["size_bytes"],
        "sha256": verif["sha256"],
        "compiler": "pandoc" if pandoc_bin else "openxml_internal",
        "verified": True,
    }

    _emit_event(
        event_sink,
        "ARTIFACT_READY",
        path=out_rel,
        type="docx",
        title=result["title"],
        size_bytes=result["size_bytes"],
        sha256=result["sha256"],
    )

    return result

