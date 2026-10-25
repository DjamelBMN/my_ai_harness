# RÔLE DE CE FICHIER :
# Vérifie les critères d'une mission à partir des résultats réels des outils et
# du workspace, jamais à partir de la seule affirmation du modèle.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from core.task_state import TaskState
from tools.filesystem import WorkspaceFilesystem
from core.artifact_intent import classify_origin, detect_artifact_request, evaluate_artifacts


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
                and source["url"].startswith(("https://", "http://"))
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

        must_download = bool(decision.get("requires_download")) or any(
            marker in request
            for marker in (
                "télécharge", "telecharge", "télécharger", "telecharger",
                "télécharge-le", "télécharge le", "récupère", "recupere",
                "téléchargement", "télécharge ce", "download",
            )
        )

        if must_download:
            # RÈGLE D'INTÉGRITÉ ABSOLUE DES ARTEFACTS :
            # 1. Vérification contre toute tentative de substitution locale
            change_tools = {"write_file", "patch_file", "compile_latex"}
            agent_fabricated = [
                item for item in successful
                if item.get("tool") in change_tools
            ]
            has_forbidden_substitution = False
            substitution_details = []
            if agent_fabricated:
                for item in agent_fabricated:
                    t_name = item.get("tool")
                    args = item.get("data", {}) or {}
                    p = args.get("path") or args.get("tex_path") or args.get("output_path") or ""
                    # Si l'agent écrit un document simulant le sujet/la ressource externe demandée
                    if any(ext in str(p).lower() for ext in (".tex", ".pdf", ".html", ".md")):
                        has_forbidden_substitution = True
                        substitution_details.append(f"{t_name} sur {p}")

            if has_forbidden_substitution:
                checks.append({
                    "check": "no_agent_substitution",
                    "status": "failed",
                    "evidence": (
                        "VIOLATION D'INTÉGRITÉ REJETÉE : L'agent a généré ou compilé un fichier local ("
                        + ", ".join(substitution_details)
                        + ") en substitution du document externe demandé. La compilation d'un fichier de substitution ne constitue jamais une réussite."
                    ),
                })
            else:
                checks.append({
                    "check": "no_agent_substitution",
                    "status": "passed",
                    "evidence": "Aucune fabrication locale de substitution détectée : l'agent n'a pas falsifié le résultat par génération artificielle.",
                })

            # 2. Vérification de la chaîne de provenance complète :
            # SOURCE WEB → URL → TÉLÉCHARGEMENT → FICHIER PHYSIQUE → HASH → TYPE/MAGIC BYTES → CONTENU → VÉRIFICATION.
            from core.artifacts.provenance import ProvenanceLedger
            ledger = ProvenanceLedger(filesystem.root)

            downloaded_files: list[str] = []
            for item in successful:
                data = item.get("data", {}) or {}
                dl_file = data.get("downloaded_file") or {}
                if isinstance(dl_file, dict) and dl_file.get("relative_path"):
                    downloaded_files.append(dl_file["relative_path"])
                elif data.get("saved_path"):
                    downloaded_files.append(data["saved_path"])

            for obs in state.observations:
                if isinstance(obs, dict) and obs.get("kind") == "downloaded_file" and obs.get("path"):
                    p_obs = obs["path"]
                    downloaded_files.append(p_obs)
                    if obs.get("url") and not ledger.get_provenance(p_obs):
                        try:
                            f_path = filesystem.resolve(p_obs)
                            if f_path.is_file():
                                ledger.record_download(
                                    origin_url=obs["url"],
                                    local_path=p_obs,
                                    raw_bytes=f_path.read_bytes(),
                                )
                        except Exception:
                            pass

            provenance_verified: list[str] = []
            provenance_errors: list[str] = []
            semantic_errors: list[str] = []
            for p in sorted(set(downloaded_files)):
                res = ledger.verify_provenance_chain(p, filesystem)
                if res.get("verified"):
                    # Vérifier également la correspondance sémantique stricte
                    sem = ledger.verify_semantic_match(p, state.user_request, filesystem)
                    if sem.get("match", True):
                        provenance_verified.append(
                            f"{p} (Source: {res['resolved_domain']}, {res['size_bytes']} octets, SHA-256: {res['sha256'][:16]}..., Type: {res['magic_bytes']})"
                        )
                    else:
                        semantic_errors.append(f"{p}: {sem.get('reason')}")
                        provenance_errors.append(f"{p}: Incompatibilité sémantique ({sem.get('reason')})")
                else:
                    provenance_errors.append(f"{p}: {res.get('error', 'Échec de provenance')}")

            provenance_passed = bool(provenance_verified) and not has_forbidden_substitution and not semantic_errors
            checks.append({
                "check": "chain_of_provenance",
                "status": "passed" if provenance_passed else "failed",
                "evidence": (
                    "Chaîne de provenance validée : " + " ; ".join(provenance_verified)
                    if provenance_verified
                    else (
                        "Échec de la chaîne de provenance : " + " ; ".join(provenance_errors)
                        if provenance_errors
                        else "Aucune chaîne de provenance (Source Web → URL → Téléchargement → Hash → Magic Bytes) n'a été établie."
                    )
                ),
            })

            checks.append({
                "check": "semantic_correspondence",
                "status": "passed" if (not semantic_errors and bool(provenance_verified)) else "failed",
                "evidence": (
                    "Correspondance sémantique confirmée avec la demande de l'utilisateur."
                    if (not semantic_errors and bool(provenance_verified))
                    else (
                        "Incompatibilité sémantique détectée : " + " ; ".join(semantic_errors)
                        if semantic_errors
                        else "Aucun document correspondant à la demande n'a été validé."
                    )
                ),
            })

            checks.append({
                "check": "document_retrieved_and_verified",
                "status": "passed" if provenance_passed else "failed",
                "evidence": (
                    "Document authentique physiquement téléchargé et vérifié sur le disque : " + ", ".join(provenance_verified)
                    if provenance_passed
                    else "Aucun document authentique n'a été récupéré depuis la source demandée dans le workspace."
                ),
            })

        # CONTRÔLE D'INTÉGRITÉ ET CONFORMITÉ DE L'ARTEFACT PRODUIT (demande -> attendu -> produit)
        art_req = detect_artifact_request(state.user_request, skill=state.skill_name or "")
        produced_deliverables = []
        for item in successful:
            produced_deliverables.extend(classify_origin(item))
        for pf in state.files:
            if pf not in [p for p, _ in produced_deliverables]:
                produced_deliverables.append((pf, "created"))

        art_eval = evaluate_artifacts(art_req, produced_deliverables)
        if art_eval["status"] == "failed":
            checks.append({
                "check": "artifact_conformance",
                "status": "failed",
                "evidence": art_eval["evidence"],
                "violations": art_eval.get("violations", []),
            })
        elif art_eval["status"] == "passed":
            checks.append({
                "check": "artifact_conformance",
                "status": "passed",
                "evidence": art_eval["evidence"],
            })

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

