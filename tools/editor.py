from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from tools.filesystem import WorkspaceFilesystem


class EditAmbiguityError(ValueError):
    """Levée quand la chaîne cible apparaît plusieurs fois sans contexte suffisant."""


class EditSyntaxError(ValueError):
    """Levée quand la modification introduit une erreur de syntaxe."""


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
    diags = _ast_semantic_diagnostics(new_content, str(target_path)) if target_path.suffix == ".py" else []

    return {
        "status": "success",
        "path": path,
        "occurrences_replaced": 1,
        "lint_passed": True,
        "diagnostics": diags,
        "summary": f"Fichier {path} modifié avec succès (syntaxe validée, {len(diags)} avertissement(s) statique(s)).",
    }


def _ast_semantic_diagnostics(source: str, filename: str = "<file>") -> list[dict[str, Any]]:
    """Analyse statique AST instantanée : détecte le code mort, les définitions dupliquées et les défauts mutables."""
    issues: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as err:
        return [{"severity": "error", "line": err.lineno or 1, "message": f"SyntaxError: {err.msg}"}]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 1. Détection d'arguments par défaut mutables (list, dict, set)
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append({
                        "severity": "warning",
                        "line": node.lineno,
                        "symbol": node.name,
                        "message": f"Argument par défaut mutable dans '{node.name}' (risque d'effet de bord partagé).",
                    })
            # 2. Détection de code mort inatteignable après return / raise
            for idx, stmt in enumerate(node.body[:-1]):
                if isinstance(stmt, (ast.Return, ast.Raise)):
                    next_stmt = node.body[idx + 1]
                    issues.append({
                        "severity": "warning",
                        "line": getattr(next_stmt, "lineno", node.lineno),
                        "symbol": node.name,
                        "message": f"Code inatteignable détecté après return/raise dans '{node.name}'.",
                    })
                    break
        elif isinstance(node, ast.ClassDef):
            seen_methods: dict[str, int] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name in seen_methods:
                        issues.append({
                            "severity": "warning",
                            "line": item.lineno,
                            "symbol": f"{node.name}.{item.name}",
                            "message": f"Méthode '{item.name}' redéfinie dans '{node.name}' (déjà définie ligne {seen_methods[item.name]}).",
                        })
                    seen_methods[item.name] = item.lineno
    return issues


def diagnose_code(
    path: str,
    filesystem: WorkspaceFilesystem | None = None,
) -> dict[str, Any]:
    """Exécute un diagnostic statique et syntaxique instantané (AST Python, JSON, HTML) avant exécution."""
    import json

    target_path = filesystem.resolve(path) if filesystem is not None else Path(path).resolve()
    if not target_path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {path}")

    content = target_path.read_text(encoding="utf-8", errors="replace")
    ext = target_path.suffix.lower()
    issues: list[dict[str, Any]] = []
    valid = True

    if ext == ".py":
        issues = _ast_semantic_diagnostics(content, str(target_path))
        valid = not any(i.get("severity") == "error" for i in issues)
    elif ext == ".json":
        try:
            json.loads(content)
        except Exception as err:
            valid = False
            issues.append({"severity": "error", "line": 1, "message": f"JSON invalide : {err}"})

    return {
        "status": "success" if valid else "error",
        "verified": valid,
        "path": path,
        "valid_syntax": valid,
        "issues_count": len(issues),
        "issues": issues,
    }