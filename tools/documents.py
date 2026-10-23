# RÔLE DE CE FICHIER :
# Extrait et identifie le texte des formats documentaires autorisés. ToolRegistry
# ne rapporte une lecture réussie qu'après extraction effective du contenu.

from __future__ import annotations

import csv
import html
import io
import json
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from tools.filesystem import WorkspaceFilesystem

TEXT_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".html", ".htm",
    ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".xml", ".toml",
}
MAX_EXTRACTED_CHARS = 120_000
MAX_ARCHIVE_MEMBERS = 5_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 300


def _validate_archive(archive: zipfile.ZipFile) -> None:
    """Refuse les archives bureautiques dont l'extraction consommerait trop."""
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ValueError("Archive bureautique refusée : trop d'entrées.")
    if sum(member.file_size for member in members) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ValueError("Archive bureautique refusée : taille décompressée trop grande.")


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag.lower() in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def _extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _validate_archive(archive)
        xml_data = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml_data)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_xlsx(data: bytes) -> tuple[str, dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise RuntimeError("La lecture XLSX nécessite openpyxl.") from None
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _validate_archive(archive)
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheets = {}
    lines = []
    try:
        for sheet in workbook.worksheets:
            rows = []
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index >= 1000:
                    rows.append(["[lignes suivantes tronquées]"])
                    break
                values = ["" if value is None else str(value) for value in row]
                if any(values):
                    rows.append(values)
                    lines.append(f"[{sheet.title}] " + " | ".join(values))
            sheets[sheet.title] = rows
    finally:
        workbook.close()
    return "\n".join(lines), {"sheets": list(sheets), "rows": sheets}


def _extract_pptx(data: bytes) -> tuple[str, dict[str, Any]]:
    ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    text_ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    slides: list[tuple[int, str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        _validate_archive(archive)
        for name in archive.namelist():
            match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", name)
            if not match:
                continue
            root = ElementTree.fromstring(archive.read(name))
            chunks = [node.text or "" for node in root.iter(f"{text_ns}t")]
            slides.append((int(match.group(1)), " ".join(chunks).strip()))
    slides.sort()
    text = "\n".join(f"[Slide {index}] {content}" for index, content in slides if content)
    return text, {"slide_count": len(slides)}


def _extract_pdf(data: bytes) -> tuple[str, dict[str, Any]]:
    try:
        import fitz
    except ImportError:
        fitz = None
    if fitz is not None:
        document = fitz.open(stream=data, filetype="pdf")
        try:
            if document.page_count > MAX_PDF_PAGES:
                raise ValueError(
                    f"PDF trop long ({document.page_count} pages; limite {MAX_PDF_PAGES})."
                )
            page_text = [page.get_text("text") for page in document]
            text = "\n".join(
                f"[Page {index + 1}] {value}"
                for index, value in enumerate(page_text)
                if value.strip()
            ).strip()
            page_count = document.page_count
            if text:
                return text, {"pages": page_count, "extraction": "embedded_text"}

            # OCR is attempted only for an image-only/scanned PDF and only when
            # both Tesseract and its Python adapter are installed.
            try:
                import pytesseract
                from PIL import Image

                pytesseract.get_tesseract_version()
            except Exception:
                raise RuntimeError(
                    "Le PDF ne contient pas de texte extractible et aucun moteur OCR "
                    "Tesseract fonctionnel n'est disponible. Le contenu n'a pas été lu."
                ) from None

            ocr_pages = min(page_count, 10)
            extracted = []
            for index in range(ocr_pages):
                pixmap = document[index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                extracted.append(
                    f"[Page {index + 1}, OCR] "
                    + pytesseract.image_to_string(image, timeout=30)
                )
            marker = ""
            if page_count > ocr_pages:
                marker = f"\n[OCR limité aux {ocr_pages} premières pages sur {page_count}]"
            text = "\n".join(extracted).strip()
            if not text:
                raise RuntimeError("OCR exécuté, mais aucun texte lisible n'a été extrait.")
            return text + marker, {
                "pages": page_count,
                "ocr_pages": ocr_pages,
                "extraction": "ocr",
            }
        finally:
            document.close()

    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("La lecture PDF nécessite PyMuPDF ou pypdf.") from None
    reader = PdfReader(io.BytesIO(data))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(
            f"PDF trop long ({len(reader.pages)} pages; limite {MAX_PDF_PAGES})."
        )
    page_text = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(
        f"[Page {index + 1}] {value}"
        for index, value in enumerate(page_text)
        if value.strip()
    ).strip()
    if not text:
        raise RuntimeError(
            "Le PDF ne contient pas de texte extractible et aucun moteur OCR n'est disponible."
        )
    return text, {"pages": len(reader.pages), "extraction": "embedded_text"}


def read_document(
    relative_path: str,
    *,
    filesystem: WorkspaceFilesystem | None = None,
    max_chars: int = MAX_EXTRACTED_CHARS,
) -> dict[str, Any]:
    """Extrait réellement un document et retourne le format et les métadonnées."""
    fs = filesystem or WorkspaceFilesystem()
    path = fs.resolve(relative_path)
    data = fs.read_bytes(relative_path)
    extension = path.suffix.lower()
    metadata: dict[str, Any] = {}

    if extension in TEXT_EXTENSIONS:
        text = _decode_text(data)
        if extension in {".json"}:
            # Vérifie que le contenu annoncé comme JSON est valide.
            json.loads(text)
        elif extension == ".csv":
            rows = list(csv.reader(io.StringIO(text)))
            text = "\n".join(" | ".join(row) for row in rows)
            metadata["rows"] = len(rows)
        elif extension in {".html", ".htm"}:
            parser = _VisibleText()
            parser.feed(text)
            text = html.unescape("".join(parser.parts))
        metadata["extraction"] = "text"
    elif extension == ".pdf":
        text, metadata = _extract_pdf(data)
    elif extension == ".docx":
        text = _extract_docx(data)
        metadata["extraction"] = "docx_xml"
    elif extension == ".xlsx":
        text, metadata = _extract_xlsx(data)
        metadata["extraction"] = "xlsx"
    elif extension == ".pptx":
        text, metadata = _extract_pptx(data)
        metadata["extraction"] = "pptx_xml"
    else:
        raise ValueError(f"Format non pris en charge : {extension or '(sans extension)'}.")

    if not text.strip():
        raise RuntimeError(f"Aucun texte n'a pu être extrait de {relative_path}.")
    text = fs.redact_secrets(text)
    original_length = len(text)
    truncated = original_length > max_chars
    if truncated:
        text = text[:max_chars] + "\n[extrait tronqué; contenu complet non transmis]"
    return {
        "path": path.relative_to(fs.root).as_posix(),
        "format": extension.lstrip("."),
        "text": text,
        "characters_extracted": original_length,
        "truncated": truncated,
        "metadata": metadata,
    }

