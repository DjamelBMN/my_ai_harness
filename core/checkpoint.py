from __future__ import annotations

import copy
import json
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CheckpointMetadata:
    id: str
    name: str
    timestamp: float
    memory_snapshot: dict[str, Any] = field(default_factory=dict)
    plan_snapshot: list[dict[str, Any]] = field(default_factory=list)
    is_healthy: bool = True
    dead_end: bool = False
    hypothesis: str = ""


class CheckpointManager:
    """Gestionnaire de snapshots et retour en arrière (backtracking) via shadow git repository.
    
    N'impacte JAMAIS le dépôt git principal de l'utilisateur :
    Toutes les opérations utilisent '--git-dir=.neoharness/shadow.git --work-tree=<workspace>'.
    """

    def __init__(self, workspace: str | Path, shadow_dir: str | Path | None = None) -> None:
        self.workspace = Path(workspace).resolve()
        self.shadow_git = (
            Path(shadow_dir).resolve()
            if shadow_dir
            else self.workspace / ".neoharness" / "shadow.git"
        )
        self.metadata_file = self.shadow_git.parent / "checkpoints.json"
        self.checkpoints: dict[str, CheckpointMetadata] = {}
        self._ensure_shadow_repo()
        self._load_metadata()

    def _git_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        cmd = [
            "git",
            f"--git-dir={self.shadow_git}",
            f"--work-tree={self.workspace}",
            *args,
        ]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def _ensure_shadow_repo(self) -> None:
        self.shadow_git.parent.mkdir(parents=True, exist_ok=True)
        if not self.shadow_git.exists() or not (self.shadow_git / "HEAD").exists():
            subprocess.run(
                ["git", f"--git-dir={self.shadow_git}", "init", "--bare"],
                capture_output=True,
                check=False,
            )
            # Configuration minimale pour permettre les commits
            self._git_cmd("config", "user.name", "NeoHarness Shadow")
            self._git_cmd("config", "user.email", "shadow@neoharness.local")

    def _load_metadata(self) -> None:
        if self.metadata_file.exists():
            try:
                data = json.loads(self.metadata_file.read_text(encoding="utf-8"))
                for k, v in data.items():
                    self.checkpoints[k] = CheckpointMetadata(**v)
            except Exception:
                self.checkpoints = {}

    def _save_metadata(self) -> None:
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {k: asdict(v) for k, v in self.checkpoints.items()}
            self.metadata_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def create_checkpoint(
        self,
        name: str,
        memory_state: dict[str, Any] | None = None,
        plan_state: list[Any] | None = None,
        hypothesis: str = "",
    ) -> str:
        """Capture l'état complet du workspace et de la mémoire sans polluer le git utilisateur."""
        self._git_cmd("add", "-A")
        msg = f"checkpoint: {name}"
        commit_res = self._git_cmd("commit", "-m", msg, "--allow-empty")
        rev_parse = self._git_cmd("rev-parse", "HEAD")
        cid = rev_parse.stdout.strip()
        if not cid:
            cid = f"cp-{int(time.time()*1000)}"

        # Sérialisation propre du plan
        serialized_plan = []
        if plan_state:
            for step in plan_state:
                if hasattr(step, "to_dict"):
                    serialized_plan.append(step.to_dict())
                elif hasattr(step, "__dict__"):
                    serialized_plan.append(copy.deepcopy(step.__dict__))
                elif isinstance(step, dict):
                    serialized_plan.append(copy.deepcopy(step))

        meta = CheckpointMetadata(
            id=cid,
            name=name,
            timestamp=time.time(),
            memory_snapshot=copy.deepcopy(memory_state or {}),
            plan_snapshot=serialized_plan,
            hypothesis=hypothesis,
        )
        self.checkpoints[cid] = meta
        self._save_metadata()
        return cid

    def rollback(self, checkpoint_id: str) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
        """Restaure exactement l'état physique du workspace et retourne la mémoire restaurée."""
        if checkpoint_id not in self.checkpoints:
            # Essayer de vérifier si le commit existe dans git
            rev = self._git_cmd("rev-parse", checkpoint_id)
            if rev.returncode != 0:
                raise ValueError(f"Checkpoint introuvable : {checkpoint_id}")

        # Restauration physique complète (reset dur + nettoyage des fichiers non suivis)
        self._git_cmd("reset", "--hard", checkpoint_id)
        self._git_cmd("clean", "-fd", "-e", ".neoharness")

        meta = self.checkpoints.get(checkpoint_id)
        if meta:
            return True, meta.memory_snapshot, meta.plan_snapshot
        return True, {}, []

    def list_checkpoints(self) -> list[CheckpointMetadata]:
        return list(self.checkpoints.values())

    def diff_checkpoints(self, id1: str, id2: str) -> str:
        res = self._git_cmd("diff", id1, id2)
        return res.stdout

    def mark_dead_end(self, checkpoint_id: str, reason: str = "") -> None:
        if checkpoint_id in self.checkpoints:
            self.checkpoints[checkpoint_id].dead_end = True
            self.checkpoints[checkpoint_id].is_healthy = False
            self.checkpoints[checkpoint_id].hypothesis += f" [DEAD_END: {reason}]"
            self._save_metadata()


class DeadlockDetector:
    """Détecte les impasses lors de l'exécution agentique (stagnation, bégaiement, tests bloqués)."""

    def __init__(self, max_consecutive_errors: int = 3) -> None:
        self.max_consecutive_errors = max_consecutive_errors

    def is_deadlock(
        self,
        consecutive_tool_failures: int,
        progress_score_recent: float = 0.0,
        tests_failed_count: int = 0,
        repetition_detected: bool = False,
    ) -> tuple[bool, str]:
        if repetition_detected:
            return True, "Boucle répétitive détectée par le repetition guard"
        if consecutive_tool_failures >= self.max_consecutive_errors:
            return True, f"{consecutive_tool_failures} échecs d'outils consécutifs sans progrès"
        if tests_failed_count >= 5:
            return True, "Tests bloqués au rouge après 5 tentatives sans convergence"
        return False, ""
