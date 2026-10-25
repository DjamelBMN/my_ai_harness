# RÔLE DE CE FICHIER :
# Garde l'ancienne interface de commande inactive et fournit un seul lancement
# borné de tests Python, sans shell ni transmission des secrets d'API aux tests.

from __future__ import annotations

import subprocess
import re
import sys
from pathlib import Path
from typing import Any

from tools.process_utils import safe_subprocess_environment


def execute_command(command: str) -> str:
    """Compatibilité historique : une commande arbitraire n'est pas exécutée."""
    return (
        "[TERMINAL DÉSACTIVÉ] Commande non exécutée : "
        f"{command!r}. Utilise l'outil run_tests autorisé pour les tests Python."
    )


def _test_environment() -> dict[str, str]:
    """Transmet l'environnement nécessaire sans API keys ni secrets usuels."""
    return safe_subprocess_environment()


def run_test_suite(workspace_root: str | Path, timeout_seconds: int = 180) -> dict[str, Any]:
    """Lance unittest discover dans la racine autorisée; jamais via shell=True."""
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Workspace de tests inexistant : {root}")
    timeout = max(1, min(int(timeout_seconds), 600))
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        ".",
        "-t",
        ".",
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env=_test_environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "status": "timeout",
            "exit_code": None,
            "timeout_seconds": timeout,
            "command": "python -B -m unittest discover -s . -t . -v",
            "stdout": stdout[-8000:],
            "stderr": stderr[-8000:],
        }
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    test_match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    test_count = int(test_match.group(1)) if test_match else 0
    return {
        "status": (
            "failed" if result.returncode != 0
            else "passed" if test_count > 0
            else "no_tests"
        ),
        "exit_code": result.returncode,
        "test_count": test_count,
        "command": "python -B -m unittest discover -s . -t . -v",
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
        "output": output[-12_000:],
    }


def run_python_script(
    workspace_root: str | Path,
    script_path: str,
    arguments: list[str] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Exécute un seul script Python du workspace, sans shell et avec confirmation."""
    from tools.filesystem import WorkspaceFilesystem

    filesystem = WorkspaceFilesystem(workspace_root)
    script = filesystem.resolve(script_path)
    if script.suffix.casefold() != ".py" or not script.is_file():
        raise ValueError("run_python attend le chemin d'un fichier .py existant du workspace.")
    args = arguments or []
    if not isinstance(args, list) or any(
        not isinstance(item, str) or len(item) > 1000 for item in args
    ):
        raise ValueError("Les arguments Python doivent être une liste de chaînes courtes.")
    if len(args) > 20:
        raise ValueError("La limite est de 20 arguments pour un script Python.")
    timeout = max(1, min(int(timeout_seconds), 120))
    # Exécution headless : MPLBACKEND=Agg, plt.show() ne bloque jamais et chaque figure
    # Matplotlib est enregistrée en PNG dans <dossier du script>/output/.
    from tools.python_runtime import (
        build_python_env,
        new_manifest_path,
        output_dir_for,
        prepare_output_dir,
        read_figure_manifest,
        validate_png,
    )

    output_dir = output_dir_for(script)
    prepare_output_dir(output_dir)
    manifest_path = new_manifest_path()
    environment = build_python_env(
        output_dir=output_dir,
        manifest_path=manifest_path,
        extra_paths=[filesystem.root],
    )

    def _figures() -> list[dict[str, Any]]:
        reports = []
        for fig_abs in read_figure_manifest(manifest_path).get("figures", []):
            report = validate_png(fig_abs)
            try:
                report["path"] = Path(fig_abs).resolve().relative_to(filesystem.root).as_posix()
            except ValueError:
                continue
            reports.append(report)
        return reports
    try:
        result = subprocess.run(
            [sys.executable, "-B", str(script), *args],
            cwd=filesystem.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "status": "timeout",
            "exit_code": None,
            "timeout_seconds": timeout,
            "stdout": stdout[-8000:],
            "stderr": stderr[-8000:],
            "figures": _figures(),
        }
    figures = _figures()
    invalid = [f for f in figures if not f.get("valid")]
    return {
        "status": "passed" if result.returncode == 0 and not invalid else "failed",
        "exit_code": result.returncode,
        "script": script.relative_to(filesystem.root).as_posix(),
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-8000:],
        "figures": figures,
    }

