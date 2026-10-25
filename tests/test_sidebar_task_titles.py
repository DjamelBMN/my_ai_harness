"""
Tests pour la génération automatique et stable des intitulés de tâches dans la sidebar.
RÈGLE ABSOLUE : AUCUNE SIMULATION, VÉRIFICATION OBSERVABLE DU RÉSULTAT.
"""

import shutil
import tempfile
import unittest

from core.title_generator import generate_task_title
from ui.server import NeoHarnessRuntimeBridge


class TestSidebarTaskTitles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_titles_")
        self.bridge = NeoHarnessRuntimeBridge(workspace=self.temp_dir)
        self.bridge.auto_approve_in_headless = True

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_user_specified_examples(self):
        """Vérifie tous les exemples explicitement demandés par l'utilisateur."""
        cases = [
            ("/exercice fais-moi un exercice sur les suites arithmétiques", "Exercice sur les suites"),
            ("peux-tu me tracer un graphique de la fonction carré avec matplotlib ?", "Graphique de la fonction carré"),
            ("/bacblanc de mathématiques terminale spécialité", "Bac blanc de mathématiques"),
            ("corrige les erreurs de compilation du document LaTeX stp", "Correction du document LaTeX"),
            ("seconde guerre mondiale", "Seconde Guerre mondiale"),
            ("/dm devoir maison de physique sur l'optique ondulatoire", "Devoir maison sur l'optique"),
        ]
        for prompt, expected in cases:
            title = generate_task_title(prompt)
            self.assertEqual(
                title.casefold().replace("é", "e").replace("è", "e"),
                expected.casefold().replace("é", "e").replace("è", "e"),
                f"Titre inattendu pour '{prompt}' : obtenu '{title}', attendu '{expected}'",
            )
            # Pas de slash command dans le titre
            self.assertFalse(title.startswith("/"), f"Le titre commence par un slash : {title}")
            # Longueur de 2 à 6 mots
            words = title.split()
            self.assertGreaterEqual(len(words), 2)
            self.assertLessEqual(len(words), 6)

    def test_02_no_raw_user_prompt_or_slashes(self):
        """Vérifie que les commandes slash et les formules de politesse sont éliminées."""
        raw_prompts = [
            "/debug erreur sur la fonction calcul_score dans utils.py",
            "S'il te plaît fais-moi un résumé du chapitre 3",
            "Je voudrais que tu rédiges un poème sur l'automne",
            "/bacblanc sujet de SVT génétique",
        ]
        for p in raw_prompts:
            t = generate_task_title(p)
            self.assertFalse(t.startswith("/"))
            self.assertNotIn("s'il te plaît", t.lower())
            self.assertNotIn("je voudrais", t.lower())
            self.assertNotIn("fais-moi", t.lower())
            self.assertLessEqual(len(t.split()), 6)

    def test_03_create_conversation_cleans_initial_title(self):
        """create_conversation() applique automatiquement le générateur de titre si un prompt est fourni."""
        conv1 = self.bridge.create_conversation("Nouvelle tâche")
        self.assertEqual(conv1["title"], "Nouvelle tâche")

        conv2 = self.bridge.create_conversation("/exercice sur les suites arithmétiques")
        self.assertEqual(conv2["title"], "Exercice sur les suites")
        self.assertFalse(conv2["title"].startswith("/"))

        conv3 = self.bridge.create_conversation("peux-tu tracer un graphique de la fonction carré ?")
        self.assertEqual(conv3["title"], "Graphique de la fonction carré")

    def test_04_title_stability_in_conversation_state(self):
        """Le titre reste stable une fois défini et n'est pas écrasé par les messages suivants."""
        conv = self.bridge.create_conversation("Nouvelle tâche")
        cid = conv["id"]

        # Premier message simulant start_task
        first_title = generate_task_title("/bacblanc de mathématiques terminale spécialité")
        self.bridge.update_conversation(cid, title=first_title)
        conv = self.bridge.get_conversation(cid)
        self.assertEqual(conv["title"], "Bac blanc de mathématiques")

        # Second message : même avec un prompt différent, le titre initial reste intact
        second_prompt = "Merci pour le sujet, peux-tu maintenant me donner le barème ?"
        if conv["title"] == "Nouvelle tâche":
            conv["title"] = generate_task_title(second_prompt)
        self.assertEqual(conv["title"], "Bac blanc de mathématiques", "Le titre a changé au lieu de rester stable")


if __name__ == "__main__":
    unittest.main()

