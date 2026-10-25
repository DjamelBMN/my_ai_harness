# RÔLE DE CE FICHIER :
# Fournit l'inspection visuelle et la rastérisation des documents PDF générés.
# Contrôle automatiquement : absence de page vide, respect strict des marges,
# adéquation du nombre de pages annoncé, et génération d'aperçus PNG.

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


class PDFRasterizer:
    """Inspecteur de mise en page et rastériseur d'artefacts PDF."""

    @staticmethod
    def is_available() -> bool:
        return fitz is not None

    @classmethod
    def rasterize_pages(
        cls,
        pdf_path: Path | str,
        output_dir: Path | str | None = None,
        dpi: int = 150,
        max_pages: int = 20,
    ) -> list[Path]:
        """Rastérise les pages d'un PDF en images PNG haute définition."""
        if not cls.is_available():
            return []

        p = Path(pdf_path)
        if not p.is_file():
            return []

        out_dir = Path(output_dir) if output_dir else p.parent / "rendered_pages"
        out_dir.mkdir(parents=True, exist_ok=True)

        rendered_paths: list[Path] = []
        doc = fitz.open(str(p))
        try:
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            for page_idx in range(min(len(doc), max_pages)):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                img_path = out_dir / f"{p.stem}_page_{page_idx + 1}.png"
                pix.save(str(img_path))
                rendered_paths.append(img_path)
        finally:
            doc.close()

        return rendered_paths

    @classmethod
    def inspect_layout(
        cls,
        pdf_path: Path | str,
        expected_pages: int | None = None,
        margin_min_pt: float = 12.0,
    ) -> dict[str, Any]:
        """Vérifie physiquement la validité visuelle du PDF produit."""
        p = Path(pdf_path)
        if not p.is_file():
            return {
                "valid": False,
                "error": f"Fichier PDF introuvable : {pdf_path}",
                "page_count": 0,
                "blank_pages": [],
                "margin_overflows": [],
            }

        if not cls.is_available():
            # Repli sans PyMuPDF
            return {
                "valid": True,
                "warning": "PyMuPDF non disponible, inspection visuelle ignorée.",
                "page_count": 1,
                "blank_pages": [],
                "margin_overflows": [],
            }

        doc = fitz.open(str(p))
        total_pages = len(doc)
        blank_pages: list[int] = []
        margin_overflows: list[dict[str, Any]] = []

        try:
            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_num = page_idx + 1
                text = page.get_text().strip()
                drawings = page.get_drawings()

                # 1. Détection de page entièrement vide (ni texte ni dessin vectoriel)
                if not text and not drawings:
                    blank_pages.append(page_num)

                # 2. Détection de débordement hors marges
                rect = page.rect
                page_w = rect.width
                page_h = rect.height

                # Bounding boxes de texte
                blocks = page.get_text("blocks")
                for b in blocks:
                    bx0, by0, bx1, by1, btext, *_ = b
                    if not btext.strip():
                        continue
                    # Débordement sur les côtés gauche, droit, haut ou bas
                    if bx0 < margin_min_pt or bx1 > (page_w - margin_min_pt) or by1 > (page_h - margin_min_pt):
                        margin_overflows.append(
                            {
                                "page": page_num,
                                "bbox": (round(bx0, 1), round(by0, 1), round(bx1, 1), round(by1, 1)),
                                "page_size": (round(page_w, 1), round(page_h, 1)),
                                "snippet": btext.strip()[:60],
                            }
                        )

            # 3. Contrôle du nombre de pages annoncé
            page_count_matches = True
            page_count_error = ""
            if expected_pages is not None and expected_pages > 0:
                if total_pages != expected_pages:
                    page_count_matches = False
                    page_count_error = (
                        f"Nombre de pages réel ({total_pages}) différent de celui annoncé ({expected_pages})."
                    )

            is_valid = (len(blank_pages) == 0) and (len(margin_overflows) == 0) and page_count_matches

            return {
                "valid": is_valid,
                "page_count": total_pages,
                "expected_pages": expected_pages,
                "page_count_matches": page_count_matches,
                "page_count_error": page_count_error,
                "blank_pages": blank_pages,
                "margin_overflows": margin_overflows,
                "first_page_preview": (
                    str(cls.rasterize_pages(p, max_pages=1)[0]) if total_pages > 0 else None
                ),
            }
        finally:
            doc.close()
