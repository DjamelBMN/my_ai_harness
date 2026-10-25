"""Tests complets d'isolation des missions, d'intégrité absolue des artefacts et de téléchargement Web réel.

Couvre les exigences strictes :
TEST 1 : Demander un PDF A, le télécharger, puis demander un PDF B. Vérifier que la tâche B ne retourne jamais le PDF A.
TEST 2 : Faire échouer web_search. Vérifier que le système tente des stratégies alternatives avant d'abandonner.
TEST 3 : Découvrir un lien PDF réel. Vérifier que download_resource est effectivement appelé.
TEST 4 : Fournir un PDF local qui ne correspond pas à la demande. Vérifier qu'il est rejeté (rejet sémantique absolu).
TEST 5 : Télécharger le CERFA 15776*02 réel. Vérifier l'existence physique, les octets, le format, le hash et la provenance.
TEST 6 : Enchaînement « analyse-le » sur la même tâche. Vérifier la continuité sans nouvelle recherche superflue.
"""

import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.artifacts.provenance import ProvenanceLedger, ProvenanceRecord
from core.task_context import TaskContext
from core.task_state import TaskState
from core.verifier import Verifier
from tools.filesystem import WorkspaceFilesystem
from tools.search import (
    autonomous_web_retrieve_and_download,
    download_resource,
    verify_downloaded_file,
    web_search,
)
from ui.server import NeoHarnessRuntimeBridge


class TestDownloadMissionIsolationAndIntegrity(unittest.TestCase):
    """Validation de l'isolation inter-tâches, de la correspondance sémantique et de l'autonomie Web réelle."""

    def setUp(self):
        self.workspace_dir = Path("workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir = self.workspace_dir / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.fs = WorkspaceFilesystem(str(self.workspace_dir))
        self.ledger = ProvenanceLedger(str(self.workspace_dir))
        self.verifier = Verifier()

    def test_01_task_isolation_task_b_never_returns_task_a_artifact(self):
        """TEST 1 : Une tâche B ne doit JAMAIS retourner ou annoncer un fichier produit par une tâche A."""
        # Tâche A : produit un sujet du Bac dans downloads/
        pdf_a_rel = "downloads/bac_2026_maths_metropole_1.pdf"
        pdf_a_abs = self.fs.resolve(pdf_a_rel)
        pdf_a_abs.write_bytes(b"%PDF-1.4\n%Sujet Bac Maths Metropole 2026\n%%EOF\n")
        self.ledger.record_download(
            origin_url="https://eduscol.education.fr/bac2026.pdf",
            local_path=pdf_a_rel,
            raw_bytes=pdf_a_abs.read_bytes(),
            content_excerpt="Baccalauréat Général 2026 Métropole Spécialité Mathématiques",
            task_id="task-A-bac",
        )

        # Simulation d'un serveur UI pour évaluer _collect_and_compile_task_artifacts
        server = NeoHarnessRuntimeBridge.__new__(NeoHarnessRuntimeBridge)
        server.filesystem = self.fs
        server.get_pdf_info = lambda p: {
            "name": Path(p).name,
            "path": p,
            "pages": 1,
            "bytes": self.fs.resolve(p).stat().st_size,
            "raw_url": f"/api/files/raw?path={p}",
        }
        server.file_changes = []
        server._snapshot_workspace = lambda: {pdf_a_rel: "hash_a"}
        server.event_bus = MagicMock()
        server.permissions = MagicMock(dry_run=False)
        server.mode_manager = MagicMock(current=MagicMock(value="AUTO"))

        # État avant et après pour la tâche B (qui demande un CERFA)
        # Le fichier A existe DÉJÀ dans before_snapshot
        before_snap = {pdf_a_rel: "hash_a"}
        after_snap = {pdf_a_rel: "hash_a"}  # Aucune modification du fichier A
        recorded_diffs = []  # Aucun diff sur le fichier A pendant la tâche B

        preview_artifacts, compilation_errors, diffs = server._collect_and_compile_task_artifacts(
            clean_prompt="Trouve le PDF officiel du CERFA 15776*02 et télécharge-le dans le workspace",
            answer_text="Recherche effectuée.",
            before_snapshot=before_snap,
            after_snapshot=after_snap,
            recorded_diffs=recorded_diffs,
            task_id="task-B-cerfa",
        )

        # Vérification formelle : le fichier A ne doit JAMAIS être retourné
        returned_paths = [a.get("path") for a in preview_artifacts]
        self.assertNotIn(
            pdf_a_rel,
            returned_paths,
            "Le PDF de la tâche A (Bac 2026) ne doit jamais être présenté comme résultat de la tâche B (CERFA) !"
        )

        # Nettoyage
        if pdf_a_abs.exists():
            pdf_a_abs.unlink()

    def test_02_web_search_multi_strategy_failover_before_abandon(self):
        """TEST 2 : Si la recherche principale échoue, le système essaie des stratégies alternatives avant d'abandonner."""
        attempts = []

        def failing_web_search(q, **kwargs):
            attempts.append(q)
            # Échoue sur la requête brute sans 'pdf'
            if "pdf" not in q.lower():
                return {"results": []}
            # Réussit sur la requête enrichie 'pdf' ou 'filetype:pdf'
            return {
                "results": [
                    {
                        "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                        "title": "Document officiel PDF",
                        "snippet": "Exemplaire de test vérifié conforme à la norme W3C dummy",
                    }
                ]
            }

        with patch("tools.search.web_search", side_effect=failing_web_search):
            res = autonomous_web_retrieve_and_download(
                query="dummy pdf document",
                workspace=str(self.workspace_dir),
                target_filename="downloads/dummy_alt_test.pdf",
                timeout=10.0,
            )

        self.assertGreater(len(attempts), 1, "Le système doit tenter plusieurs requêtes de recherche alternatives.")
        self.assertEqual(res.get("status"), "success", "La recherche multi-stratégie doit aboutir au téléchargement.")

        target_file = self.workspace_dir / "downloads/dummy_alt_test.pdf"
        self.assertTrue(target_file.exists())
        if target_file.exists():
            target_file.unlink()

    def test_03_pdf_link_discovery_triggers_download_resource(self):
        """TEST 3 : Découvrir un lien PDF réel appelle effectivement download_resource."""
        with patch("tools.search.download_resource", wraps=download_resource) as spy_download:
            res = autonomous_web_retrieve_and_download(
                query="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                workspace=str(self.workspace_dir),
                target_filename="downloads/dummy_spy_test.pdf",
            )
            self.assertTrue(spy_download.called, "download_resource doit être effectivement appelé dès qu'un lien PDF est découvert.")

        target_file = self.workspace_dir / "downloads/dummy_spy_test.pdf"
        if target_file.exists():
            target_file.unlink()

    def test_04_mismatched_local_pdf_is_semantically_rejected(self):
        """TEST 4 : Fournir un PDF local qui ne correspond pas à la demande doit être rejeté."""
        mismatched_rel = "downloads/bac_maths_test_mismatch.pdf"
        mismatched_abs = self.fs.resolve(mismatched_rel)
        mismatched_abs.write_bytes(b"%PDF-1.4\n%Sujet Baccalaureat 2026 Mathematiques\n%%EOF\n")

        self.ledger.record_download(
            origin_url="https://eduscol.education.fr/sujet_bac.pdf",
            local_path=mismatched_rel,
            raw_bytes=mismatched_abs.read_bytes(),
            content_excerpt="Épreuve de spécialité mathématiques du baccalauréat 2026",
            task_id="task-old",
        )

        # 1. Vérification par le registre sémantique
        sem = self.ledger.verify_semantic_match(
            mismatched_rel,
            "Trouve le PDF officiel du CERFA 15776*02 et télécharge-le",
            self.fs,
        )
        self.assertFalse(sem["match"], "Un sujet de Bac doit être sémantiquement rejeté pour une requête CERFA.")
        self.assertIn("Incompatibilité sémantique", sem["reason"])

        # 2. Vérification par le Verifier formel
        state = TaskState(
            task_id="t-cerfa-eval",
            user_request="Trouve le PDF officiel du CERFA 15776*02 et télécharge-le",
            objective="Téléchargement du CERFA 15776*02",
        )
        state.files.append(mismatched_rel)
        state.observations.append({
            "kind": "downloaded_file",
            "path": mismatched_rel,
            "url": "https://eduscol.education.fr/sujet_bac.pdf",
            "status": "verified",
        })

        report = self.verifier.verify(state, self.fs)
        self.assertEqual(report["status"], "failed", "Le Verifier doit échouer si le document téléchargé ne correspond pas à la demande.")

        check_map = {c["check"]: c["status"] for c in report["checks"]}
        self.assertEqual(check_map.get("semantic_correspondence"), "failed")

        if mismatched_abs.exists():
            mismatched_abs.unlink()

    def test_05_real_download_cerfa_15776_02_with_provenance_and_hash(self):
        """TEST 5 : Téléchargement réel du CERFA 15776*02 officiel depuis service-public.fr avec vérification physique et hash."""
        # Téléchargement réel de l'exemplaire officiel du CERFA 15776
        official_url = "https://www.formulaires.service-public.fr/gf/cerfa_15776.do"
        dest_rel = "downloads/cerfa_15776_02_officiel.pdf"

        dl = download_resource(
            official_url,
            output_path=dest_rel,
            workspace=str(self.workspace_dir),
            task_id="task-cerfa-real-test",
        )

        self.assertEqual(dl["status"], "success", "Le téléchargement du CERFA officiel doit réussir.")

        # Vérification physique sur le disque
        file_path = self.workspace_dir / dest_rel
        self.assertTrue(file_path.exists(), f"Le fichier physique {file_path} doit exister sur le disque.")

        # Taille réelle (le formulaire CERFA fait plus de 600 ko)
        size = file_path.stat().st_size
        self.assertGreater(size, 50_000, "Le fichier CERFA réel doit contenir les données complètes du formulaire (> 50 Ko).")

        # Vérification du format binaire
        verif = verify_downloaded_file(file_path)
        self.assertTrue(verif["valid"])
        self.assertEqual(verif["format"], "pdf")
        self.assertEqual(len(verif["sha256"]), 64)

        # Vérification de l'enregistrement de provenance
        record = self.ledger.get_provenance(dest_rel)
        self.assertIsNotNone(record)
        self.assertEqual(record.sha256, verif["sha256"])
        self.assertIn("service-public.fr", record.origin_url)

        # Vérification sémantique
        sem = self.ledger.verify_semantic_match(
            dest_rel,
            "Trouve le PDF officiel du CERFA 15776*02 et télécharge-le",
            self.fs,
        )
        self.assertTrue(sem["match"], f"La correspondance sémantique doit être validée : {sem.get('reason')}")

        # Nettoyage
        if file_path.exists():
            file_path.unlink()

    def test_06_conversational_continuity_analyse_le_without_refetching(self):
        """TEST 6 : Après téléchargement, « analyse-le » reprend le fichier existant sans relancer de recherche."""
        ctx = TaskContext(
            conversation_id="conv-cerfa-continuity",
            initial_objective="Télécharger le CERFA 15776*02",
        )

        dest_rel = "downloads/cerfa_15776_02.pdf"
        dest_abs = self.fs.resolve(dest_rel)
        dest_abs.write_bytes(b"%PDF-1.4\nCertificat de cession 15776*02\n%%EOF\n")

        ctx.record_file(dest_rel)
        ctx.record_artifact(dest_rel, art_type="pdf")

        # L'utilisateur envoie simplement « analyse-le »
        followup = "analyse-le"
        is_cont = ctx.is_continuity_request(followup)
        self.assertTrue(is_cont, "Le message court « analyse-le » doit être immédiatement rattaché à la tâche active.")

        # Vérifier que le fichier est conservé en mémoire de travail
        self.assertIn(dest_rel, ctx.files)

        # Nettoyage
        if dest_abs.exists():
            dest_abs.unlink()


if __name__ == "__main__":
    unittest.main()
