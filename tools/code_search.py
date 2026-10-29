from __future__ import annotations

import ast
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


def _format_ast_arg(arg: ast.arg) -> str:
    if arg.annotation is not None:
        try:
            return f"{arg.arg}: {ast.unparse(arg.annotation)}"
        except Exception:
            return arg.arg
    return arg.arg


def _extract_python_ast_outline(source: str, rel_file: str) -> dict[str, Any]:
    """Extrait la carte structurelle AST (classes, fonctions, signatures, appels, imports) d'un fichier Python."""
    tree = ast.parse(source, filename=rel_file)
    imports: list[str] = []
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            methods: list[dict[str, Any]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args_str = ", ".join(_format_ast_arg(a) for a in item.args.args)
                    methods.append({
                        "name": item.name,
                        "line": item.lineno,
                        "end_line": getattr(item, "end_lineno", item.lineno),
                        "signature": f"({args_str})",
                    })
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "bases": bases,
                "methods": methods,
                "doc": (ast.get_docstring(node) or "").splitlines()[0][:120] if ast.get_docstring(node) else "",
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args_str = ", ".join(_format_ast_arg(a) for a in node.args.args)
            calls: list[str] = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    if isinstance(sub.func, ast.Name) and sub.func.id not in calls:
                        calls.append(sub.func.id)
                    elif isinstance(sub.func, ast.Attribute) and sub.func.attr not in calls:
                        calls.append(sub.func.attr)
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
                "signature": f"({args_str})",
                "calls": calls[:15],
                "doc": (ast.get_docstring(node) or "").splitlines()[0][:120] if ast.get_docstring(node) else "",
            })

    return {
        "file": rel_file,
        "imports": imports[:25],
        "classes": classes,
        "functions": functions,
    }


def code_ast_map(
    path: str = ".",
    symbol_query: str = "",
    max_files: int = 40,
    filesystem: WorkspaceFilesystem | None = None,
) -> dict[str, Any]:
    """Construit la cartographie structurelle AST du code (classes, fonctions, signatures, dépendances)
    et localise les définitions et appels d'un symbole si 'symbol_query' est fourni."""
    root = filesystem.root if filesystem is not None else Path(".").resolve()
    target = (root / path).resolve() if filesystem is None else (root if path in {".", "", "./"} else filesystem.resolve(path))
    if not target.exists():
        raise FileNotFoundError(f"Chemin introuvable pour l'analyse AST : {path}")

    py_files: list[Path] = [target] if target.is_file() else list(target.rglob("*.py"))
    needle = (symbol_query or "").strip().casefold()
    modules_map: list[dict[str, Any]] = []
    definitions: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []

    for item in py_files:
        parts = set(item.parts)
        if any(ign in parts for ign in IGNORED_PATTERNS):
            continue
        try:
            src = item.read_text(encoding="utf-8", errors="replace")
            rel = str(item.relative_to(root)).replace("\\", "/")
            outline = _extract_python_ast_outline(src, rel)
        except Exception:
            continue

        if needle:
            for cls in outline["classes"]:
                if needle in cls["name"].casefold():
                    definitions.append({"kind": "class", "name": cls["name"], "file": rel, "line": cls["line"]})
                for m in cls["methods"]:
                    if needle in m["name"].casefold():
                        definitions.append({"kind": "method", "name": f"{cls['name']}.{m['name']}", "file": rel, "line": m["line"], "signature": m["signature"]})
            for fn in outline["functions"]:
                if needle in fn["name"].casefold():
                    definitions.append({"kind": "function", "name": fn["name"], "file": rel, "line": fn["line"], "signature": fn["signature"]})
            for idx, ln in enumerate(src.splitlines(), start=1):
                if needle in ln.casefold() and len(references) < 40:
                    references.append({"file": rel, "line": idx, "snippet": ln.strip()[:160]})

        if len(modules_map) < max_files:
            modules_map.append(outline)
        elif not needle:
            break

    return {
        "status": "success",
        "verified": True,
        "path": path,
        "symbol_query": symbol_query,
        "files_analyzed": len(modules_map),
        "definitions": definitions,
        "references": references[:30],
        "modules": modules_map,
    }
