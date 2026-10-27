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



def truncate_output(text: str, head_lines: int = 50, tail_lines: int = 50) -> str:
    """Tronque intelligemment une sortie volumineuse : tête (50) + marqueur + queue (50)."""
    if not text:
        return ""
    lines = text.splitlines()
    total = len(lines)
    if total <= head_lines + tail_lines:
        return text
    truncated_count = total - (head_lines + tail_lines)
    head_part = "\n".join(lines[:head_lines])
    tail_part = "\n".join(lines[-tail_lines:])
    return f"{head_part}\n\n... [{truncated_count} lignes tronquées pour préserver le contexte] ...\n\n{tail_part}"


def execute_bounded_command(
    command_str: str,
    cwd: str | Path | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    """Exécuteur de commande borné avec timeout strict (30s) et tronquage intelligent tête+queue."""
    timeout = max(1, min(int(timeout_seconds), 120))
    try:
        res = subprocess.run(
            command_str,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=True,
            check=False,
        )
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "exit_code": res.returncode,
            "stdout": truncate_output(res.stdout),
            "stderr": truncate_output(res.stderr),
        }
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "status": "timeout",
            "exit_code": -1,
            "stdout": truncate_output(stdout),
            "stderr": truncate_output(stderr),
            "error": f"Commande interrompue après {timeout}s (timeout strict dépassé).",
        }


def terminal_start(
    session_id: str = "default",
    shell: str = "powershell",
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Démarre ou récupère une session de terminal interactif persistant Windows."""
    from tools.terminal_session import get_terminal_manager

    return get_terminal_manager().start_session(session_id=session_id, shell=shell, cwd=cwd)


def terminal_send(
    command: str,
    session_id: str = "default",
    wait_ms: int = 1200,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Envoie une commande ou réponse interactive dans le terminal persistant et lit stdout/stderr."""
    from tools.terminal_session import get_terminal_manager

    effective_cwd = Path(cwd).resolve() if cwd else None
    cmd_str = (command or "").strip()
    # Si le terminal est lancé depuis workspace/ mais que la commande cible tests/ ou main.py à la racine du projet,
    # se placer automatiquement à la racine du projet pour que la commande trouve les fichiers.
    if (
        effective_cwd is not None
        and effective_cwd.name.lower() == "workspace"
        and any(tok in cmd_str for tok in ("tests/", "tests\\", "main.py", "unittest"))
        and (effective_cwd.parent / "tests").is_dir()
    ):
        effective_cwd = effective_cwd.parent
        cmd_str = f"Set-Location -LiteralPath '{effective_cwd}'; {cmd_str}"

    # Adapter automatiquement l'attente si la commande lance des tests
    effective_wait = max(int(wait_ms or 1200), 3500 if "unittest" in cmd_str else 800)
    return get_terminal_manager().send_input(
        command=cmd_str,
        session_id=session_id,
        wait_ms=effective_wait,
        cwd=effective_cwd,
    )


def terminal_read(session_id: str = "default", wait_ms: int = 300) -> dict[str, Any]:
    """Lit les nouvelles sorties stdout/stderr du terminal persistant (ex: serveur npm run dev)."""
    from tools.terminal_session import get_terminal_manager

    return get_terminal_manager().read_output(session_id=session_id, wait_ms=wait_ms)


def terminal_stop(session_id: str = "default") -> dict[str, Any]:
    """Arrête proprement une session de terminal persistant."""
    from tools.terminal_session import get_terminal_manager

    return get_terminal_manager().stop_session(session_id=session_id)


def terminal_list() -> dict[str, Any]:
    """Liste toutes les sessions de terminal persistantes actives."""
    from tools.terminal_session import get_terminal_manager

    return get_terminal_manager().list_sessions()