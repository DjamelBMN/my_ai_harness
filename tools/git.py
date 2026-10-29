# RÔLE DE CE FICHIER :
# Prépare les opérations Git demandées. GitWorkspace est utilisé par ToolRegistry
# avec limites de workspace et confirmations ; les anciennes fonctions simples
# restent des réponses simulées pour préserver leur contrat historique.

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.process_utils import safe_subprocess_environment


class GitWorkspace:
    """Git sans shell; commandes d'écriture appelées uniquement via ToolRegistry."""

    def __init__(self, workspace_root: str | Path, timeout_seconds: int = 30) -> None:
        self.root = Path(workspace_root).resolve()
        self.timeout_seconds = max(1, min(timeout_seconds, 120))

    def _run(self, *arguments: str) -> dict[str, Any]:
        executable = shutil.which("git")
        if executable is None:
            raise RuntimeError("Git n'est pas installé ou git.exe est absent du PATH.")
        if not self.root.is_dir():
            raise NotADirectoryError("La racine du workspace Git n'existe pas.")
        environment = safe_subprocess_environment()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            result = subprocess.run(
                [executable, *arguments],
                cwd=self.root,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError("La commande Git a dépassé sa limite de temps.") from None
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        if result.returncode:
            raise RuntimeError(f"Git a échoué (code {result.returncode}) : {output[:2000]}")
        return {"exit_code": result.returncode, "output": output}

    def _verify_repository_boundary(self) -> None:
        result = self._run("rev-parse", "--show-toplevel")
        repository_root = Path(result["output"].splitlines()[0]).resolve()
        if repository_root != self.root:
            raise PermissionError(
                "Le dépôt Git remonte au-dessus du workspace autorisé; opération refusée."
            )

    def status(self) -> dict[str, Any]:
        self._verify_repository_boundary()
        result = self._run("status", "--short", "--branch")
        return {"repository": str(self.root), **result}

    def current_branch(self) -> dict[str, Any]:
        self._verify_repository_boundary()
        result = self._run("branch", "--show-current")
        return {"branch": result["output"]}

    def create_branch(self, name: str) -> dict[str, Any]:
        self._verify_repository_boundary()
        self._run("check-ref-format", "--branch", name)
        result = self._run("switch", "--create", name)
        return {"branch": name, "output": result["output"]}

    def commit_staged(self, message: str) -> dict[str, Any]:
        if not message.strip():
            raise ValueError("Le message de commit ne peut pas être vide.")
        self._verify_repository_boundary()
        result = self._run("commit", "-m", message)
        return {"output": result["output"]}

    def merge(self, branch_name: str) -> dict[str, Any]:
        self._verify_repository_boundary()
        self._run("check-ref-format", "--branch", branch_name)
        result = self._run("merge", "--no-edit", "--", branch_name)
        return {"branch": branch_name, "output": result["output"]}

    def list_worktrees(self) -> dict[str, Any]:
        """Liste les worktrees Git isolés actifs pour le développement parallèle."""
        self._verify_repository_boundary()
        result = self._run("worktree", "list", "--porcelain")
        return {"repository": str(self.root), "output": result["output"]}

    def create_worktree(self, name: str, branch: str = "") -> dict[str, Any]:
        """Crée un espace de travail Git isolé (.harness/worktrees/<name>) pour un agent parallèle."""
        self._verify_repository_boundary()
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_")[:40]
        if not safe_name:
            raise ValueError("Nom de worktree invalide.")
        wt_path = self.root / ".harness" / "worktrees" / safe_name
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        branch_name = branch.strip() or f"wt/{safe_name}"
        self._run("check-ref-format", "--branch", branch_name)
        result = self._run("worktree", "add", "-B", branch_name, str(wt_path))
        return {"worktree_path": str(wt_path), "branch": branch_name, "output": result["output"]}

def status() -> str:
    return "[GIT SIMULATION] status : aucun dépôt Git interrogé."


def branch(name: str = "") -> str:
    return f"[GIT SIMULATION] branche demandée : {name or '(courante)'} ; aucune action."


def commit(message: str) -> str:
    return f"[GIT SIMULATION] commit demandé : {message!r} ; aucun commit créé."


def merge(branch_name: str) -> str:
    return f"[GIT SIMULATION] fusion demandée : {branch_name!r} ; aucune fusion effectuée."
