from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.filesystem import WorkspaceFilesystem


def view_file(
    path: str,
    start_line: int = 1,
    end_line: int | None = None,
    max_lines: int = 200,
    filesystem: WorkspaceFilesystem | None = None,
) -> dict[str, Any]:
    """Visualiseur de fichier fenêtré avec numérotation de lignes (borne max 200 lignes)."""
    if filesystem is not None:
        target_path = filesystem.resolve(path)
    else:
        target_path = Path(path).resolve()

    if not target_path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    all_lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
    total_file_lines = len(all_lines)

    start = max(1, start_line)
    if end_line is None:
        end = min(total_file_lines, start + max_lines - 1)
    else:
        end = min(total_file_lines, end_line)

    if (end - start + 1) > max_lines:
        end = start + max_lines - 1

    selected_slice = all_lines[start - 1 : end]
    formatted_lines = [f"{i:04d}: {line}" for i, line in enumerate(selected_slice, start=start)]
    content_view = "\n".join(formatted_lines)

    return {
        "status": "success",
        "path": path,
        "start_line": start,
        "end_line": end,
        "total_lines": total_file_lines,
        "lines_returned": len(selected_slice),
        "content": content_view,
    }
