# RÔLE DE CE FICHIER :
# Recherche réellement dans les fichiers d'un workspace local. La recherche Web
# reste distincte et n'est pas déclarée disponible sans backend configuré.

from __future__ import annotations

from pathlib import Path

from tools.filesystem import WORKSPACE_ROOT, WorkspaceFilesystem


def search(query: str, workspace: str | Path = WORKSPACE_ROOT) -> str:
    """Compatibilité historique, maintenant reliée à une vraie recherche locale."""
    matches = WorkspaceFilesystem(workspace).search_files(query)
    if not matches:
        return f"Aucune occurrence de {query!r} dans le workspace." 
    return "\n".join(
        f"{item['path']}:{item['line']}: {item['text']}" for item in matches
    )


def search_web(query: str) -> str:
    """Échoue honnêtement tant qu'aucun backend de recherche Web n'est configuré."""
    if not query.strip():
        raise ValueError("Une requête Web est requise.")
    raise RuntimeError(
        "Aucun backend de recherche Web n'est configuré; aucune source distante "
        "n'a été consultée."
    )

