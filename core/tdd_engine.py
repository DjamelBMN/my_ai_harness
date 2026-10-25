from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tools.filesystem import WorkspaceFilesystem


class TestTamperingError(RuntimeError):
    """Levée lorsqu'un agent tente de modifier un fichier de test pour faire passer une suite frauduleusement."""


@dataclass
class TDDState:
    test_file: str
    code_files: list[str] = field(default_factory=list)
    initial_test_hash: str = ""
    phase: str = "RED"  # RED -> GREEN -> REFACTOR -> REVIEW
    iterations: int = 0
    max_iterations: int = 5
    red_verified: bool = False
    green_verified: bool = False
    critic_approved: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)


class TDDEngine:
    """Moteur de cycle TDD fermé avec oracles déterministes et protection anti-triche."""

    def __init__(self, filesystem: WorkspaceFilesystem, max_iterations: int = 5) -> None:
        self.fs = filesystem
        self.max_iterations = max(1, max_iterations)
        self.test_hashes: dict[str, str] = {}
        self.active_cycles: dict[str, TDDState] = {}

    def _hash_file(self, rel_path: str) -> str:
        abs_p = self.fs.resolve(rel_path)
        if not abs_p.is_file():
            return ""
        return hashlib.sha256(abs_p.read_bytes()).hexdigest()

    def register_test_file(self, rel_path: str) -> str:
        """Enregistre le hash cryptographique immuable du fichier de test dès sa création."""
        h = self._hash_file(rel_path)
        if not h:
            raise FileNotFoundError(f"Fichier de test introuvable pour enregistrement : {rel_path}")
        self.test_hashes[rel_path] = h
        state = TDDState(test_file=rel_path, initial_test_hash=h, max_iterations=self.max_iterations)
        self.active_cycles[rel_path] = state
        return h

    def verify_test_integrity(self, rel_path: str) -> bool:
        """Vérifie que le test n'a pas été altéré par le codeur pour contourner l'échec."""
        if rel_path not in self.test_hashes:
            return True
        expected_hash = self.test_hashes[rel_path]
        current_hash = self._hash_file(rel_path)
        if current_hash != expected_hash:
            raise TestTamperingError(
                f"[SÉCURITÉ TDD] Altération frauduleuse du fichier de test détectée sur {rel_path} ! "
                f"Hash attendu : {expected_hash[:12]}..., hash observé : {current_hash[:12]}... "
                "Le codeur est interdit de modifier la suite de test pour forcer le succès."
            )
        return True

    def validate_red_phase(self, rel_path: str, run_test_fn: Callable[[], dict[str, Any]]) -> tuple[bool, str]:
        """Étape 1 : Le test DOIT échouer (RED). S'il passe immédiatement, il est soit trivial soit invalide."""
        self.register_test_file(rel_path)
        res = run_test_fn()
        passed = (res.get("status") == "success" or res.get("returncode") == 0 or res.get("passed") is True)
        state = self.active_cycles[rel_path]

        if passed:
            state.red_verified = False
            return False, "Le test passe déjà avant toute implémentation (RED invalide ou tâche déjà résolue)."

        state.red_verified = True
        state.phase = "GREEN"
        return True, "Phase RED confirmée : le test échoue bien avant implémentation."

    def validate_green_phase(self, rel_path: str, run_test_fn: Callable[[], dict[str, Any]]) -> tuple[bool, str]:
        """Étape 2 : Le code doit faire passer le test SANS modifier le fichier de test."""
        # 1. Vérification d'intégrité anti-triche
        self.verify_test_integrity(rel_path)

        state = self.active_cycles.get(rel_path)
        if not state:
            raise RuntimeError(f"Aucun cycle TDD actif pour {rel_path}")

        state.iterations += 1
        if state.iterations > state.max_iterations:
            return False, f"Limite d'itérations TDD atteinte ({state.iterations}/{state.max_iterations})."

        res = run_test_fn()
        passed = (res.get("status") == "success" or res.get("returncode") == 0 or res.get("passed") is True)

        if not passed:
            return False, f"Test encore en échec à l'itération {state.iterations}/{state.max_iterations}."

        state.green_verified = True
        state.phase = "REVIEW"
        return True, "Phase GREEN confirmée : les tests passent avec 0 erreur sans modification du test."
