from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from tools.filesystem import WorkspaceFilesystem

IGNORED_PATTERNS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".neoharness",
    "*.pyc",
    "*.egg-info",
    "dist",
    "build",
}


def search_code(
    pattern: str,
    path: str = ".",
    file_glob: str | None = None,
    max_results: int = 30,
    filesystem: WorkspaceFilesystem | None = None,
) -> dict[str, Any]:
    """Recherche ciblée de code par expression régulière avec exclusion des répertoires parasites."""
    if not pattern:
        raise ValueError("Le pattern de recherche ne peut pas être vide.")

    root = filesystem.root if filesystem is not None else Path(".").resolve()
    if filesystem is not None:
        target_root = root if path in {".", "", "./"} else filesystem.resolve(path)
    else:
        target_root = (root / path).resolve()

    if not target_root.exists():
        raise FileNotFoundError(f"Répertoire de recherche introuvable : {path}")

    try:
        regex = re.compile(pattern)
    except re.error as err:
        raise ValueError(f"Pattern regex invalide '{pattern}' : {err}") from err

    results: list[dict[str, Any]] = []

    for item in target_root.rglob("*"):
        # Vérification d'exclusion des répertoires et fichiers parasites
        parts = set(item.parts)
        if any(ign in parts for ign in IGNORED_PATTERNS):
            continue
        if any(fnmatch.fnmatch(item.name, ign) for ign in IGNORED_PATTERNS):
            continue

        if not item.is_file():
            continue

        if file_glob and not fnmatch.fnmatch(item.name, file_glob):
            continue

        try:
            lines = item.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue

        rel_file = str(item.relative_to(root)).replace("\\", "/")
        for line_num, line in enumerate(lines, start=1):
            if regex.search(line):
                results.append({
                    "file": rel_file,
                    "line": line_num,
                    "match": line.strip()[:200],
                })
                if len(results) >= max_results:
                    break

        if len(results) >= max_results:
            break

    return {
        "status": "success",
        "pattern": pattern,
        "results_count": len(results),
        "results": results,
    }
