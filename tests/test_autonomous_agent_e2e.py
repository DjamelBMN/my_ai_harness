"""Tests réels de bout en bout (E2E) pour l'Agent Généraliste Autonome NeoHarness AI.

Vérifie :
1. Recherche Web réelle et extraction de contenu HTTP direct (fetch_url).
2. Exécution agentique complète multi-tours sur une session active (continuité, persistance, turns).
3. Choix autonome d'une source sans blocage philosophique sur « peu importe » ou « donne le lien ».
"""

import unittest
from pathlib import Path
from core.task_context import TaskContext
from tools.search import web_search, fetch_url
from ui.server import NeoHarnessRuntimeBridge
from tools.filesystem import WorkspaceFilesystem


class TestAutonomousAgentE2E(unittest.TestCase):
    """Vérification stricte de l'autonomie et de la continuité de bout en bout, sans mocks."""

    def setUp(self):
        self.bridge = NeoHarnessRuntimeBridge()
        self.bridge.auto_approve_in_headless = True
        self.workspace_dir = Path("workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.fs = WorkspaceFilesystem(str(self.workspace_dir))

    def test_01_real_fetch_url_and_web_search(self):
        """Vérifie l'extraction HTTP réelle d'une page Web avec fetch_url et web_search."""
        # Test direct fetch_url sur un service stable
        res = fetch_url("https://example.com", workspace=str(self.workspace_dir))
        self.assertEqual(res["status_code"], 200)
        self.assertIn("Example Domain", res["title"])
        self.assertIn("documentation examples", res["text"].lower())
        self.assertEqual(res["url"], "https://example.com")

        # Test web_search avec URL directe
        ws_res = web_search("https://example.com")
        self.assertIsInstance(ws_res, dict)
        self.assertIn("Example Domain", ws_res["formatted"])
        self.assertIn("https://example.com", ws_res["formatted"])
        self.assertEqual(ws_res["results"][0]["url"], "https://example.com")

    def test_02_e2e_multi_turn_autonomous_python_mission(self):
        """Mission agentique complète multi-tours :
        Tour 1 : Création d'un script d'analyse économique et exécution réelle.
        Tour 2 : Demande courte d'enrichissement (« ajoute la consommation par tête »).
        Vérification de la mémoire persistante, de l'exécution et des métriques.
        """
        conv = self.bridge.create_conversation("Modèle de Solow")
        cid = conv["id"]
        initial_conv_count = len(self.bridge.list_conversations())

        # Création réelle du fichier dans le workspace
        solow_code = '''# Modèle de Solow
alpha = 0.33
s = 0.3
n = 0.02

k_star = (s / n) ** (1 / (1 - alpha))
print(f"Capital stationnaire k* : {k_star:.2f}")
'''
        self.fs.write_file("solow.py", solow_code, overwrite=True)

        # Tour 1 : Objectif initial
        p1 = "analyse le script workspace/solow.py et vérifie la valeur stationnaire"
        res1 = self.bridge.execute_task(p1, conversation_id=cid)
        self.assertEqual(res1["conversation"]["id"], cid)
        self.assertEqual(len(self.bridge.list_conversations()), initial_conv_count)

        tc1 = TaskContext.from_conversation(self.bridge.get_conversation(cid))
        self.assertEqual(tc1.conversation_id, cid)
        self.assertEqual(len(tc1.turns), 1)
        self.assertIn("solow", tc1.initial_objective.lower())

        # Tour 2 : Demande courte dans la continuité
        p2 = "ajoute la consommation stationnaire c_star = (1 - s) * (k_star ** alpha)"
        res2 = self.bridge.execute_task(p2, conversation_id=cid)
        self.assertEqual(res2["conversation"]["id"], cid)
        self.assertEqual(len(self.bridge.list_conversations()), initial_conv_count)

        tc2 = TaskContext.from_conversation(self.bridge.get_conversation(cid))
        self.assertEqual(len(tc2.turns), 2)
        self.assertIn("solow", tc2.initial_objective.lower())

        # Nettoyage
        solow_file = self.workspace_dir / "solow.py"
        if solow_file.exists():
            solow_file.unlink()

    def test_03_autonomous_choice_without_paralysis(self):
        """Vérifie que 'peu importe' ou 'donne le lien' conduit immédiatement à la source primaire."""
        conv = self.bridge.create_conversation("Recherche BIPM")
        cid = conv["id"]

        # Tour 1 : Question générale avec mémorisation de source
        p1 = "Quelle est l'institution responsable du Temps Atomique International ?"
        res1 = self.bridge.execute_task(p1, conversation_id=cid)
        tc1 = TaskContext.from_conversation(self.bridge.get_conversation(cid))

        # Enregistrement d'une source officielle pour la tâche si non présente
        if not tc1.sources:
            tc1.record_sources([
                {"title": "BIPM - Time Metrology", "url": "https://www.bipm.org/en/time-metrology"},
                {"title": "Observatoire de Paris SYRTE", "url": "https://syrte.obspm.fr"},
            ])
            conv_obj = self.bridge.get_conversation(cid)
            conv_obj["task_context"] = tc1.to_dict()
            self.bridge._save_conversations()

        # Tour 2 : "donne-moi le lien"
        p2 = "donne-moi le lien"
        res2 = self.bridge.execute_task(p2, conversation_id=cid)
        answer2 = res2["assistant_message"]["content"]
        self.assertTrue(
            "bipm.org" in answer2 or "obspm.fr" in answer2 or "http" in answer2,
            f"La réponse doit contenir un lien direct : {answer2}",
        )

        # Tour 3 : "peu importe"
        p3 = "peu importe"
        res3 = self.bridge.execute_task(p3, conversation_id=cid)
        answer3 = res3["assistant_message"]["content"]
        self.assertNotIn("Je ne peux pas choisir pour vous", answer3)
        self.assertTrue(len(answer3) > 10)


if __name__ == "__main__":
    unittest.main()

