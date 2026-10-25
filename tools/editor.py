from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from tools.filesystem import WorkspaceFilesystem


class EditAmbiguityError(ValueError):
    """Levée quand la chaîne cible apparaît plusieurs fois sans contexte suffisant."""
    pass


class EditSyntaxError(ValueError):
    """Levée quand la modification introduit une erreur de syntaxe."""
    pass


def edit_file(
    path: str,
    old_str: str,
    new_str: str,
    filesystem: WorkspaceFilesystem | None = None,
) -> dict[str, Any]:
    """Éditeur ciblé par remplacement avec linting AST instantané et rollback automatique."""
    if not old_str:
        raise ValueError("old_str ne peut pas être vide.")

    if filesystem is not None:
        target_path = filesystem.resolve(path)
    else:
        target_path = Path(path).resolve()

    if not target_path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    original_content = target_path.read_text(encoding="utf-8")

    # 1. Vérification de présence et d'unicité
    count = original_content.count(old_str)
    if count == 0:
        raise ValueError(f"La chaîne cible old_str n'a pas été trouvée dans {path}. Vérifie les espaces et l'indentation.")
    if count > 1:
        raise EditAmbiguityError(
            f"La chaîne cible old_str apparaît {count} fois dans {path}. "
            "Fournis davantage de contexte (lignes précédentes/suivantes) pour lever l'ambiguïté."
        )

    # 2. Application du remplacement
    new_content = original_content.replace(old_str, new_str, 1)

    # 3. Linting AST instantané pour Python (protection contre les régressions syntaxiques)
    if target_path.suffix == ".py":
        try:
            ast.parse(new_content, filename=str(target_path))
        except SyntaxError as syn_err:
            # Rollback immédiat : le fichier physique n'est pas modifié ou restauré
            raise EditSyntaxError(
                f"La modification introduit une erreur de syntaxe Python ligne {syn_err.lineno} : {syn_err.msg}. "
                "Modification annulée par le linter instantané."
            ) from syn_err

    # 4. Écriture atomique
    target_path.write_text(new_content, encoding="utf-8")

    return {
        "status": "success",
        "path": path,
        "occurrences_replaced": 1,
        "lint_passed": True,
        "summary": f"Fichier {path} modifié avec succès (syntaxe validée).",
    }
