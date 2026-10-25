"""Tests réels de l'autonomie Web et de la règle stricte de vérification pour les missions de téléchargement.

Vérifie :
1. Téléchargement réel et vérification physique (existence, taille, format, SHA-256).
2. Navigation HTML et extraction des liens de téléchargement de documents.
3. Stratégie multi-tentatives et bascule sur des sources alternatives en cas d'échec.
4. Règle absolue du Verifier : échec si aucun document n'est physiquement récupéré, succès uniquement si le fichier existe et est vérifié.
5. Continuité conversationnelle sur les demandes « cherche ailleurs », « essaie une autre source », « télécharge-le », « ouvre-le », « analyse-le ».
"""

import unittest
from pathlib import Path
from tools.filesystem import WorkspaceFilesystem
from tools.search import (
    download_resource,
    verify_downloaded_file,
    _extract_download_links,
    fetch_url,
    web_search,
)
from core.verifier import Verifier
from core.task_state import TaskState
from core.task_context import TaskContext


class TestAutonomousWebRetrieval(unittest.TestCase):
    """Vérification de l'autonomie Web réelle sans simulation."""

    def setUp(self):
        self.workspace_dir = Path("workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir = self.workspace_dir / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.fs = WorkspaceFilesystem(str(self.workspace_dir))
        self.verifier = Verifier()

    def test_01_real_download_and_physical_verification(self):
        """Télécharge physiquement une ressource distante réelle et vérifie sa taille et son empreinte."""
        target_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        dest_rel = "downloads/dummy_w3c_test.pdf"

        res = download_resource(target_url, output_path=dest_rel, workspace=str(self.workspace_dir))
        self.assertEqual(res["status"], "success")

        # Vérification physique sur le disque
        file_path = self.workspace_dir / dest_rel
        self.assertTrue(file_path.exists(), f"Le fichier {file_path} doit exister sur le disque.")
        self.assertGreater(file_path.stat().st_size, 500, "Le fichier doit contenir des données non vides.")

        # Vérification binaire
        verif = verify_downloaded_file(file_path)
        self.assertTrue(verif["valid"])
        self.assertEqual(verif["format"], "pdf")
        self.assertTrue(len(verif["sha256"]) == 64, "L'empreinte SHA-256 doit être valide.")

        # Nettoyage
        if file_path.exists():
            file_path.unlink()

    def test_02_download_links_extraction_from_html(self):
        """Vérifie l'extraction et la résolution de liens de téléchargement depuis une page HTML."""
        html_sample = '''<!DOCTYPE html>
<html>
<head><title>Annales Bac 2026</title></head>
<body>
  <h1>Sujets de Baccalauréat Spécialité Mathématiques 2026</h1>
  <p>Retrouvez ci-dessous les épreuves officielles :</p>
  <ul>
    <li><a href="/fichiers/sujet_bac_2026_metropole_jour1.pdf">Télécharger le Sujet 1 Métropole (PDF)</a></li>
    <li><a href="https://externalsite.org/corrige_bac_2026.pdf">Corrigé officiel détaillé</a></li>
    <li><a href="/actualites/reforme">Consulter les actualités</a></li>
    <li><a href="javascript:void(0)">Imprimer</a></li>
  </ul>
</body>
</html>'''
        base_url = "https://eduscol.education.fr/mathematiques/annales"
        links = _extract_download_links(html_sample, base_url)

        self.assertEqual(len(links), 2)
        # Lien 1 résolu en URL absolue
        self.assertEqual(links[0]["url"], "https://eduscol.education.fr/fichiers/sujet_bac_2026_metropole_jour1.pdf")
        self.assertIn("Sujet 1 Métropole", links[0]["text"])
        self.assertEqual(links[0]["filename"], "sujet_bac_2026_metropole_jour1.pdf")

        # Lien 2 externe
        self.assertEqual(links[1]["url"], "https://externalsite.org/corrige_bac_2026.pdf")
        self.assertIn("Corrigé", links[1]["text"])

    def test_03_verifier_rejects_search_without_download(self):
        """RÈGLE CRITIQUE : Le Verifier doit déclarer ÉCHEC si une recherche a réussi
        mais qu'aucun document n'a été physiquement téléchargé pour une demande de récupération.
        """
        prompt = "Trouve le sujet 1 de mathématiques spécialité du bac 2026 Métropole et télécharge-le."
        state = TaskState(
            user_request=prompt,
            mode="AUTO",
            intent="research",
            requires_web_search=True,
            intent_decision={"requires_download": True, "requires_web": True},
        )
        # L'agent a trouvé des sources Web
        state.sources.append({
            "title": "Sujets Bac Métropole 2026",
            "url": "https://eduscol.education.fr/annales-2026",
            "snippet": "Le sujet 1 de mathématiques est disponible.",
            "source": "eduscol",
        })
        # MAIS aucun outil n'a téléchargé de fichier
        state.record_tool_result({
            "name": "web_search",
            "tool": "web_search",
            "status": "success",
            "summary": "1 source trouvée",
            "data": {"count": 1},
        })

        # Exécution du Verifier
        report = self.verifier.verify(state, self.fs)

        # La recherche est réussie mais la mission DOIT être déclarée FAILED
        self.assertEqual(report["status"], "failed")
        check_names = {c["check"]: c["status"] for c in report["checks"]}
        self.assertEqual(check_names.get("web_sources_observed"), "passed")
        self.assertEqual(check_names.get("document_retrieved_and_verified"), "failed")

    def test_04_verifier_accepts_when_document_physically_downloaded(self):
        """Le Verifier valide la mission UNIQUEMENT lorsque le document existe physiquement sur le disque."""
        prompt = "Trouve le sujet 1 de mathématiques spécialité du bac 2026 Métropole et télécharge-le."
        state = TaskState(
            user_request=prompt,
            mode="AUTO",
            intent="research",
            requires_web_search=True,
            intent_decision={"requires_download": True, "requires_web": True},
        )
        # Création physique d'un faux PDF valide dans le workspace
        dest_rel = "downloads/sujet_bac_2026_metropole_jour1.pdf"
        dest_file = self.workspace_dir / dest_rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_bytes(b"%PDF-1.4\n%Fake PDF for test\n%%EOF\n")

        state.sources.append({
            "title": "Sujets Bac Métropole 2026",
            "url": "https://eduscol.education.fr/annales-2026",
            "snippet": "Téléchargement réussi.",
            "source": "eduscol",
        })
        state.observations.append({
            "kind": "downloaded_file",
            "path": dest_rel,
            "size_bytes": dest_file.stat().st_size,
            "url": "https://eduscol.education.fr/sujet1.pdf",
            "status": "verified",
        })
        state.record_tool_result({
            "name": "web_search",
            "tool": "web_search",
            "status": "success",
            "summary": "Fichier téléchargé et vérifié",
            "data": {
                "downloaded_file": {
                    "relative_path": dest_rel,
                    "size_bytes": dest_file.stat().st_size,
                }
            },
        })

        report = self.verifier.verify(state, self.fs)
        self.assertEqual(report["status"], "passed")
        check_names = {c["check"]: c["status"] for c in report["checks"]}
        self.assertEqual(check_names.get("document_retrieved_and_verified"), "passed")

        # Nettoyage
        if dest_file.exists():
            dest_file.unlink()

    def test_05_conversational_continuity_for_retrieval(self):
        """Vérifie la continuité contextuelle sur les enchaînements de téléchargement et recherche alternative."""
        ctx = TaskContext(
            conversation_id="conv-web-dl-test",
            initial_objective="Trouve le sujet 1 de mathématiques du bac 2026 et télécharge-le.",
        )
        ctx.record_sources([
            {"title": "Eduscol Sujet 1", "url": "https://eduscol.education.fr/sujet1.pdf"},
        ])

        # 1. « cherche ailleurs »
        self.assertTrue(ctx.is_relevant_to_active_task("cherche ailleurs"))
        p_else = ctx.build_continuity_prompt("cherche ailleurs")
        self.assertIn("RECHERCHE ALTERNATIVE", p_else)

        # 2. « essaie une autre source »
        self.assertTrue(ctx.is_relevant_to_active_task("essaie une autre source"))
        p_other = ctx.build_continuity_prompt("essaie une autre source")
        self.assertIn("RECHERCHE ALTERNATIVE", p_other)

        # 3. « télécharge-le »
        self.assertTrue(ctx.is_relevant_to_active_task("télécharge-le"))
        p_dl = ctx.build_continuity_prompt("télécharge-le")
        self.assertIn("TÉLÉCHARGEMENT EFFECTIF DU DOCUMENT", p_dl)
        self.assertIn("https://eduscol.education.fr/sujet1.pdf", p_dl)

        # 4. « ouvre-le »
        self.assertTrue(ctx.is_relevant_to_active_task("ouvre-le"))
        p_open = ctx.build_continuity_prompt("ouvre-le")
        self.assertIn("OUVERTURE ET APERÇU", p_open)

        # 5. « analyse-le »
        self.assertTrue(ctx.is_relevant_to_active_task("analyse-le"))
        p_ana = ctx.build_continuity_prompt("analyse-le")
        self.assertIn("ANALYSE DE DOCUMENT TÉLÉCHARGÉ", p_ana)

        # 6. « continue »
        self.assertTrue(ctx.is_relevant_to_active_task("continue"))
        p_cont = ctx.build_continuity_prompt("continue")
        self.assertIn("CONSIGNE DE CONTINUITÉ", p_cont)


    def test_06_exact_bac_retrieval_and_continuity_analysis(self):
        """Vérifie le routage exact de la demande de téléchargement du sujet de bac et de la continuité 'analyse-le'."""
        from core.intent_engine import IntentEngine
        from core.planner import Planner
        from core.task import Task

        prompt = (
            "Trouve sur Internet le sujet 1 de maths spécialité du bac 2026 Métropole, "
            "télécharge réellement le PDF dans le workspace, vérifie-le, puis affiche-le dans le panneau droit ; "
            "ensuite je te dirai simplement “analyse-le” pour vérifier la continuité de la même tâche."
        )

        # 1. Classification de la demande initiale
        ie = IntentEngine()
        dec1 = ie.decide(prompt)
        self.assertEqual(dec1.intent, "research")
        self.assertIn("web_search", dec1.required_tools)
        self.assertTrue(dec1.requires_web)

        # Planification
        planner = Planner()
        state1 = planner.plan(Task(description=prompt, type="researcher"))
        self.assertEqual(state1.intent, "research")
        self.assertTrue(state1.requires_web_search)
        self.assertIn("web_search", state1.intent_decision.get("required_tools", []))

        # 2. Continuité conversationnelle sur 'analyse-le'
        ctx = TaskContext(
            conversation_id="conv-bac-test",
            initial_objective=prompt,
            last_intent="research",
            last_agent="researcher",
            files=["downloads/spe-mathematiques-2026-metropole-1-sujet-officiel.pdf"],
        )
        dec2 = ie.decide("analyse-le", task_context=ctx)
        self.assertEqual(dec2.intent, "file_analysis")
        self.assertIn("read_document", dec2.required_tools)
        self.assertIn("downloads/spe-mathematiques-2026-metropole-1-sujet-officiel.pdf", dec2.files_required)


if __name__ == "__main__":
    unittest.main()

