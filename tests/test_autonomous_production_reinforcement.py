# RÔLE DE CE FICHIER :
# Tests unitaires et d'intégration obligatoires pour la mission de renforcement de NeoHarness AI :
#   1. test_no_unrequested_artifact
#   2. test_pdf_only_when_requested
#   3. test_docx_generation
#   4. test_docx_integrity
#   5. test_dynamic_filename
#   6. test_download_vs_generation
#   7. test_image_transcription_fidelity
#   8. test_unreadable_image_detection
#   9. test_task_context_continuity
# + Tests complémentaires pour les représentations mathématiques avancées (droite graduée, graphes, convexité).

from __future__ import annotations

import io
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock

from PIL import Image, ImageDraw

from core.artifact_intent import (
    detect_artifact_request,
    evaluate_artifacts,
    suggest_filename,
)
from core.artifacts.provenance import ProvenanceLedger
from core.task_context import TaskContext
from core.task_state import TaskState
from core.verifier import Verifier
from tools.docx import (
    DocxVerificationError,
    generate_docx,
    verify_docx_file,
)
from tools.filesystem import WorkspaceFilesystem
from tools.math_tikz import (
    MathConsistencyError,
    generate_convexity_table,
    generate_graph,
    generate_math_figure,
    generate_number_line,
)
from tools.vision import transcribe_image


class TestAutonomousProductionReinforcement(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_prod_reinf_")
        self.fs = WorkspaceFilesystem(self.temp_dir)
        self.verifier = Verifier()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Ne jamais générer un fichier non demandé
    # -------------------------------------------------------------------------
    def test_no_unrequested_artifact(self) -> None:
        """Explication / analyse / recherche -> aucun fichier ne doit être attendu ni généré."""
        prompt = "Explique-moi les identités remarquables et leur démonstration géométrique"
        req = detect_artifact_request(prompt)
        self.assertFalse(req.wants_file)
        self.assertEqual(req.formats, [])

        # Cas nominal : aucun fichier produit -> succès
        eval_ok = evaluate_artifacts(req, [])
        self.assertEqual(eval_ok["status"], "not_applicable")

        # Violation : un PDF est produit à tort pour une simple explication -> rejet Verifier
        eval_err = evaluate_artifacts(req, [("cours.pdf", "compiled")])
        self.assertEqual(eval_err["status"], "failed")
        self.assertTrue(any("Fichier non demandé produit" in v for v in eval_err["violations"]))

        # Contrôle par le Verifier
        state = TaskState(user_request=prompt, intent="general_question")
        state.tool_results.append({
            "tool": "compile_document",
            "status": "success",
            "data": {"path": "cours.pdf", "relative_path": "cours.pdf"},
        })
        report = self.verifier.verify(state, self.fs)
        self.assertEqual(report["status"], "failed")
        conformance_check = next(c for c in report["checks"] if c["check"] == "artifact_conformance")
        self.assertEqual(conformance_check["status"], "failed")

    # -------------------------------------------------------------------------
    # 2. PDF uniquement lorsque demandé
    # -------------------------------------------------------------------------
    def test_pdf_only_when_requested(self) -> None:
        """Lorsque l'utilisateur demande un PDF, seul un PDF est accepté (DOCX refusé)."""
        prompt = "Génère un document PDF complet sur les suites arithmétiques et géométriques"
        req = detect_artifact_request(prompt)
        self.assertTrue(req.wants_file)
        self.assertIn("pdf", req.formats)
        self.assertNotIn("docx", req.formats)

        # Si seul un DOCX est produit alors qu'un PDF était demandé -> rejet
        eval_bad = evaluate_artifacts(req, [("suites.docx", "generated")])
        self.assertEqual(eval_bad["status"], "failed")
        self.assertTrue(any("Format non demandé" in v or "non produit" in v for v in eval_bad["violations"]))

        # Si le PDF est produit (avec un .tex intermédiaire toléré) -> validation
        eval_good = evaluate_artifacts(req, [("suites.tex", "generated"), ("suites.pdf", "compiled")])
        self.assertEqual(eval_good["status"], "passed")

    # -------------------------------------------------------------------------
    # 3. Génération DOCX avec Pandoc
    # -------------------------------------------------------------------------
    def test_docx_generation(self) -> None:
        """L'outil generate_docx produit un fichier DOCX physique valide et émet ARTIFACT_READY."""
        content = "# Théorème de Pythagore\n\nDans un triangle rectangle, le carré de l'hypoténuse est égal à la somme des carrés des côtés de l'angle droit :\n\n$$a^2 + b^2 = c^2$$\n"
        events = []

        def sink(name, data):
            events.append((name, data))

        res = generate_docx(
            content=content,
            title="Théorème de Pythagore",
            workspace=self.fs.root,
            event_sink=sink,
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["format"], "docx")
        self.assertTrue(Path(res["path"]).is_file())
        self.assertGreater(res["size_bytes"], 0)
        self.assertTrue(res["verified"])
        self.assertIn("ARTIFACT_READY", [e[0] for e in events])

    # -------------------------------------------------------------------------
    # 4. Intégrité physique DOCX (ZIP, [Content_Types].xml, word/document.xml)
    # -------------------------------------------------------------------------
    def test_docx_integrity(self) -> None:
        """Contrôles physiques stricts : signature PK, manifest et document.xml."""
        # A. Fichier valide
        valid_res = generate_docx(
            content="Contenu de test pour intégrité.",
            title="Test Intégrité",
            workspace=self.fs.root,
        )
        verif = verify_docx_file(valid_res["path"])
        self.assertTrue(verif["valid"])
        self.assertTrue(verif["manifest_present"])
        self.assertTrue(verif["document_xml_present"])

        # B. Fichier corrompu (sans signature ZIP PK)
        fake_path = self.fs.resolve("fake.docx")
        fake_path.write_bytes(b"NOT A ZIP FILE CONTENT")
        with self.assertRaises(DocxVerificationError) as ctx_pk:
            verify_docx_file(fake_path)
        self.assertIn("Signature ZIP 'PK' absente", str(ctx_pk.exception))

        # C. Archive ZIP sans word/document.xml
        incomplete_path = self.fs.resolve("incomplete.docx")
        with zipfile.ZipFile(incomplete_path, "w") as zf:
            zf.writestr("[Content_Types].xml", "<Types/>")
        with self.assertRaises(DocxVerificationError) as ctx_doc:
            verify_docx_file(incomplete_path)
        self.assertIn("word/document.xml", str(ctx_doc.exception))

    # -------------------------------------------------------------------------
    # 5. Nom de fichier dynamique adapté au contenu
    # -------------------------------------------------------------------------
    def test_dynamic_filename(self) -> None:
        """Le nom de fichier généré est représentatif du contenu sans noms génériques."""
        # 1. Identités remarquables
        p1 = "Crée le document Word des identités remarquables"
        n1 = suggest_filename(p1, "docx")
        self.assertEqual(n1, "identites_remarquables.docx")

        # 2. CERFA
        p2 = "Trouve le PDF officiel du CERFA 15776*02 et télécharge-le"
        n2 = suggest_filename(p2, "pdf")
        self.assertEqual(n2, "cerfa_15776_02.pdf")

        # 3. Sujet de Bac
        p3 = "Génère le PDF du sujet officiel du Bac 2026 spécialité maths"
        n3 = suggest_filename(p3, "pdf")
        self.assertEqual(n3, "sujet_bac_2026_maths.pdf")

    # -------------------------------------------------------------------------
    # 6. Téléchargement distant vs substitution locale
    # -------------------------------------------------------------------------
    def test_download_vs_generation(self) -> None:
        """Un document distant demandé doit provenir du Web et ne jamais être généré localement."""
        prompt = "Trouve le PDF officiel du CERFA 15776*02 et télécharge-le dans le workspace"
        req = detect_artifact_request(prompt)
        self.assertEqual(req.mode, "download")

        # Cas interdit : l'agent a compilé ou généré un fichier local au lieu de télécharger
        eval_subst = evaluate_artifacts(req, [("cerfa_15776_02.pdf", "compiled")])
        self.assertEqual(eval_subst["status"], "failed")
        self.assertTrue(any("Substitution interdite" in v for v in eval_subst["violations"]))

        # Cas conforme : fichier téléchargé physiquement depuis le Web
        eval_dl = evaluate_artifacts(req, [("downloads/cerfa_15776_02.pdf", "downloaded")])
        self.assertEqual(eval_dl["status"], "passed")

    # -------------------------------------------------------------------------
    # 7. Fidélité absolue lors de la reproduction d'une image
    # -------------------------------------------------------------------------
    def test_image_transcription_fidelity(self) -> None:
        """transcribe_image reproduit ce qui est visible sans inventer de suite."""
        # Création d'une image nette avec un exercice
        img = Image.new("RGB", (700, 120), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((25, 40), "Exercice 2 : Calculer la dérivée de f(x) = 3x^2 + 5x - 7", fill="black")
        img_path = self.fs.resolve("exercice_net.png")
        img.save(img_path)

        res = transcribe_image(img_path)
        self.assertTrue(res["fidelity_guaranteed"])
        self.assertIn("Exercice", res["text"])
        self.assertIn("f(x)", res["text"])

    # -------------------------------------------------------------------------
    # 8. Détection des parties illisibles [illisible]
    # -------------------------------------------------------------------------
    def test_unreadable_image_detection(self) -> None:
        """Une image floue ou dégradée produit obligatoirement [illisible] sans invention."""
        # Création d'une image uniformément grise / bruitée sans texte discernable
        img = Image.new("RGB", (300, 100), color=(200, 200, 200))
        img_path = self.fs.resolve("exercice_flou.png")
        img.save(img_path)

        res = transcribe_image(img_path, min_confidence=40.0)
        self.assertTrue(res["has_unreadable"])
        self.assertIn("[illisible]", res["text"])

    # -------------------------------------------------------------------------
    # 9. Continuité de tâche et analyse du même fichier
    # -------------------------------------------------------------------------
    def test_task_context_continuity(self) -> None:
        """TaskContext conserve le fichier téléchargé et l'URL source pour 'analyse-le'."""
        ctx = TaskContext(conversation_id="conv-test-123")
        ctx.initial_request = "Télécharge le document CERFA 15776*02"
        ctx.record_download(
            path="downloads/cerfa_15776_02.pdf",
            origin_url="https://service-public.fr/cerfa15776.pdf",
            document_name="CERFA 15776*02",
        )
        ctx.record_artifact("downloads/cerfa_15776_02.pdf", "pdf")
        ctx.record_verification({"status": "passed", "check": "sha256_match"})

        # Vérification des champs exigés dans TaskContext
        self.assertEqual(ctx.downloaded_file, "downloads/cerfa_15776_02.pdf")
        self.assertEqual(ctx.searched_document, "CERFA 15776*02")
        self.assertEqual(ctx.primary_source_url, "https://service-public.fr/cerfa15776.pdf")
        self.assertEqual(ctx.artifact_path, "downloads/cerfa_15776_02.pdf")
        self.assertEqual(ctx.artifact_type, "pdf")
        self.assertEqual(len(ctx.verification_results), 1)

        # Enchaînement : l'utilisateur dit « analyse-le »
        prompt_next = "analyse-le"
        self.assertTrue(ctx.is_continuity_request(prompt_next))
        continuity_prompt = ctx.build_continuity_prompt(prompt_next)

        # L'instruction doit explicitement ordonner d'analyser le même fichier sans relancer de recherche
        self.assertIn("downloads/cerfa_15776_02.pdf", continuity_prompt)
        self.assertIn("Ne recommence PAS la recherche Internet", continuity_prompt)
        self.assertIn("read_document", continuity_prompt)

    # -------------------------------------------------------------------------
    # 10. Représentations mathématiques avancées (droite graduée, graphe, convexité)
    # -------------------------------------------------------------------------
    def test_advanced_math_representations(self) -> None:
        """Vérifie la génération déterministe et les oracles de cohérence pour droite graduée, graphes et convexité."""
        # A. Droite graduée avec intervalle [-2, 3[
        nl_res = generate_number_line(
            intervals=[{"start": -2, "end": 3, "start_included": True, "end_included": False}],
            x_min=-5,
            x_max=5,
        )
        self.assertTrue(nl_res["verified"])
        self.assertIn(r"\begin{tikzpicture}", nl_res["tikz"])
        self.assertIn("line width=2.5pt", nl_res["tikz"])

        # Rejet si borne début > borne fin
        with self.assertRaises(MathConsistencyError):
            generate_number_line(intervals=[{"start": 4, "end": 1}])

        # B. Graphe orienté pondéré
        graph_res = generate_graph(
            nodes=["A", "B", "C"],
            edges=[
                {"from": "A", "to": "B", "weight": "0.5"},
                {"from": "B", "to": "C", "weight": "0.8"},
                {"from": "C", "to": "A", "weight": "1.0"},
            ],
            directed=True,
            weighted=True,
        )
        self.assertTrue(graph_res["verified"])
        self.assertIn("->, thick", graph_res["tikz"])

        # Rejet si arête vers un sommet inexistant
        with self.assertRaises(MathConsistencyError):
            generate_graph(nodes=["A", "B"], edges=[{"from": "A", "to": "Z"}])

        # C. Tableau de convexité pour f(x) = x^3 - 3x (d2f = 6x, racine x=0)
        conv_res = generate_convexity_table("x**3 - 3*x", var_str="x")
        self.assertTrue(conv_res["verified"])
        self.assertEqual(conv_res["roots"], [0.0])
        self.assertEqual(conv_res["convexities"], ["Concave", "Convexe"])
        self.assertIn(r"\text{Inflexion}", conv_res["tikz"])


if __name__ == "__main__":
    unittest.main()

