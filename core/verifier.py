# RÔLE DE CE FICHIER :
# Vérifie les critères d'une mission à partir des résultats réels des outils et
# du workspace, jamais à partir de la seule affirmation du modèle.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.task_state import TaskState
from tools.filesystem import WorkspaceFilesystem


class Verifier:
    def verify(self, state: TaskState, filesystem: WorkspaceFilesystem) -> dict[str, Any]:
        request = state.user_request.casefold()
        decision = state.intent_decision or {}
        def flatten_tool_results(items):
            flattened = []
            for item in items:
                flattened.append(item)
                if item.get("tool") == "delegate_to_agent":
                    nested = item.get("data", {}).get("tool_results", [])
                    if isinstance(nested, list):
                        flattened.extend(flatten_tool_results(nested))
            return flattened

        results = flatten_tool_results(state.tool_results)
        successful = [item for item in results if item.get("status") == "success"]
        checks: list[dict[str, Any]] = []
        must_modify = bool(decision.get("requires_modification")) or any(
            phrase in request
            for phrase in (
                "corrige", "modifie", "crée un fichier", "écris dans", "ajoute",
                "implémente", "implement", "fix ", "refactor", "répare", "write to",
                "edit ", "create file", "update the code", "supprime", "delete ",
                "déplace", "move ", "renomme",
            )
        )
        mentions_local_target = any(
            extension in request
            for extension in (".pdf", ".docx", ".xlsx", ".pptx", ".py", ".md", ".json")
        )
        mentions_local_target = mentions_local_target or any(
            word in request for word in (" fichier", " document", " projet", "workspace", " codebase")
        )
        must_read = (
            bool(decision.get("requires_file_read"))
            or state.intent == "file_analysis"
            or (state.intent == "coding" and (must_modify or mentions_local_target))
            or (state.intent == "review" and mentions_local_target)
        )
        must_test = (
            bool(decision.get("requires_tests"))
            or state.intent == "testing"
            or (state.intent == "coding" and must_modify)
            or any(
            phrase in request
            for phrase in ("run tests", "run test", "régression", "tests unitaires", "exécute les tests")
            )
        )

        if must_read:
            read_results = [
                item for item in successful
                if item.get("tool") in {"read_file", "read_document"}
            ]
            observed = bool(read_results)
            checks.append(
                {
                    "check": "file_was_read",
                    "status": "passed" if observed else "failed",
                    "evidence": (
                        "Contenu extrait par " + ", ".join(sorted({item['tool'] for item in read_results}))
                        if observed else "Aucun fichier n'a été lu avec succès."
                    ),
                }
            )

        if must_test:
            test_runs = [
                (index, item.get("data", {}))
                for index, item in enumerate(results)
                if item.get("tool") == "run_tests" and item.get("status") == "success"
            ]
            change_tools = {"write_file", "patch_file", "delete_file", "move_file", "run_python"}
            change_indices = [
                index for index, item in enumerate(results)
                if item.get("tool") in change_tools and item.get("status") == "success"
            ]
            last_change = max(change_indices, default=-1)
            passed = any(
                (index > last_change if must_modify else True)
                and result.get("status") == "passed"
                and result.get("exit_code") == 0
                and result.get("test_count", 0) > 0
                for index, result in test_runs
            )
            checks.append(
                {
                    "check": "tests_executed_and_passed",
                    "status": "passed" if passed else "failed",
                    "evidence": (
                        "Une suite non vide a réussi après la dernière modification."
                        if passed else
                        "Aucune suite non vide n'a réussi après la dernière modification."
                    ),
                }
            )
            is_bug_fix = any(
                marker in request for marker in ("corrige", "répare", "fix ", "bug")
            ) and must_modify
            if is_bug_fix:
                first_change = min(change_indices, default=len(results))
                reproduced = any(
                    index < first_change
                    and result.get("status") == "failed"
                    and result.get("exit_code") not in {0, None}
                    and result.get("test_count", 0) > 0
                    for index, result in test_runs
                )
                checks.append(
                    {
                        "check": "bug_reproduced_before_change",
                        "status": "passed" if reproduced else "failed",
                        "evidence": (
                            "Une suite non vide échouait avant la première modification."
                            if reproduced else
                            "Aucun échec de test non vide n'a été observé avant la modification."
                        ),
                    }
                )

        if must_modify:
            writes = [
                item for item in successful
                if item.get("tool") in {"write_file", "patch_file"}
            ]
            verified_writes = []
            for item in writes:
                path = item.get("data", {}).get("path")
                expected_hash = item.get("data", {}).get("sha256")
                if not path or not expected_hash:
                    continue
                try:
                    actual_hash = hashlib.sha256(filesystem.read_bytes(path)).hexdigest()
                except (OSError, ValueError):
                    continue
                if actual_hash == expected_hash:
                    verified_writes.append(path)
            verified_deletions = []
            for item in successful:
                if item.get("tool") != "delete_file":
                    continue
                path = item.get("data", {}).get("path")
                if isinstance(path, str):
                    try:
                        exists = filesystem.resolve(path).exists()
                    except (OSError, ValueError, PermissionError):
                        exists = True
                    if not exists:
                        verified_deletions.append(path)
            verified_moves = []
            for item in successful:
                if item.get("tool") != "move_file":
                    continue
                data = item.get("data", {})
                source, destination = data.get("source"), data.get("destination")
                if not isinstance(source, str) or not isinstance(destination, str):
                    continue
                try:
                    source_exists = filesystem.resolve(source).exists()
                    destination_exists = filesystem.resolve(destination).is_file()
                except (OSError, ValueError, PermissionError):
                    continue
                if not source_exists and destination_exists:
                    verified_moves.append(f"{source} → {destination}")
            verified_changes = verified_writes + verified_deletions + verified_moves
            checks.append(
                {
                    "check": "requested_change_exists",
                    "status": "passed" if verified_changes else "failed",
                    "evidence": (
                        "Changement relu ou état de fichier vérifié : " + ", ".join(verified_changes)
                        if verified_changes
                        else "Aucune écriture approuvée n'a été relue et comparée."
                    ),
                }
            )

        if state.requires_web_search:
            verified_sources = [
                source for source in state.sources
                if isinstance(source.get("url"), str)
                and source["url"].startswith("https://")
            ]
            checks.append(
                {
                    "check": "web_sources_observed",
                    "status": "passed" if verified_sources else "failed",
                    "evidence": (
                        f"{len(verified_sources)} source(s) remontée(s) par l'outil Web du provider."
                        if verified_sources
                        else "Aucune source Web n'a été effectivement consultée."
                    ),
                }
            )

        if not checks:
            report = {
                "status": "not_required",
                "checks": [],
                "summary": "Aucun contrôle fichier/test spécifique n'était demandé.",
            }
        else:
            passed = all(check["status"] == "passed" for check in checks)
            report = {
                "status": "passed" if passed else "failed",
                "checks": checks,
                "summary": (
                    "Tous les critères déterministes sont vérifiés."
                    if passed
                    else "Un ou plusieurs critères demandés n'ont pas été vérifiés."
                ),
            }
        state.verification_results.append(report)
        state.observations.append({"kind": "verification", **report})
        return report

