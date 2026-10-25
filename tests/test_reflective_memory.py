from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from core.memory import ReflectiveMemory
from core.planner import Planner
from core.task import Task


class TestReflectiveMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_reflective.sqlite"
        self.memory = ReflectiveMemory(db_path=self.db_path, decay_rate=0.9)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_sqlite_and_fts5_persistence(self) -> None:
        """Persistance SQLite et recherche FTS5 fonctionnelle."""
        self.memory.record_mission(
            mission_id="m-101",
            objectif="Corriger un bug dans le routeur",
            statut="success",
            nb_steps=4,
        )
        lesson_id = self.memory.record_lesson(
            mission_id="m-101",
            declencheur_pattern="router config flags synchronisation",
            diagnostic="Désynchronisation entre config.yaml et router.py",
            regle="Toujours vérifier que les flags de config.yaml correspondent au router",
            score_utilite=1.5,
        )
        self.assertTrue(lesson_id)

        # Nouvelle instance pointant vers la même base physique pour valider la persistance
        fresh_memory = ReflectiveMemory(db_path=self.db_path)
        hits = fresh_memory.retrieve_relevant_lessons("bug de configuration router", limit=3)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["id"], lesson_id)
        self.assertIn("config.yaml", hits[0]["regle"])

    def test_02_automatic_lesson_extraction_after_failure(self) -> None:
        """Extraction automatique d'au moins une règle précise après échec simulé."""
        extracted = self.memory.extract_lessons_from_mission(
            mission_id="m-failed-01",
            objectif="Modifier le fichier calculator.py",
            statut="failure",
            history_summary="L'exécution a échoué avec SyntaxError: unexpected EOF while parsing",
            error_details="SyntaxError in calculator.py line 42",
        )
        self.assertGreaterEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["diagnostic"], "Syntaxe invalide")

        # Vérifier que la règle est désormais interrogeable
        hits = self.memory.retrieve_relevant_lessons("edition fichier code python syntaxe", limit=3)
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("AST", hits[0]["regle"])

    def test_03_injection_in_planner_for_similar_pattern(self) -> None:
        """Injection de la leçon lors d'une mission ultérieure au pattern similaire."""
        # Enregistre une leçon sur la répétition d'outils
        self.memory.record_lesson(
            mission_id="m-rep-01",
            declencheur_pattern="repetition outil echec boucle repetitif",
            diagnostic="Répétition d'outil en échec",
            regle="Changer d'outil au second échec au lieu de boucler",
            score_utilite=1.5,
        )

        planner = Planner(reflective_memory=self.memory)
        task = Task(
            description="Exécuter un outil en échec répétitif pour résoudre le problème",
        )
        state = planner.plan(task)

        # Vérifie que la leçon pertinente est attachée à l'état de la tâche
        self.assertTrue(hasattr(state, "relevant_lessons"))
        self.assertGreaterEqual(len(state.relevant_lessons), 1)
        rule = state.relevant_lessons[0]["regle"]
        self.assertIn("Changer d'outil", rule)

        # Vérifie le formatage non-privilégié
        formatted = ReflectiveMemory.format_lessons_for_prompt(state.relevant_lessons)
        self.assertIn('<donnees_non_fiables source="memoire_reflexive">', formatted)
        self.assertIn("</donnees_non_fiables>", formatted)
        self.assertIn("Changer d'outil au second échec", formatted)

    def test_04_score_decay_when_not_used(self) -> None:
        """Décroissance du score temporel (decay factor) si non utilisée."""
        now = time.time()
        # Enregistre deux leçons : une récente et une ancienne (il y a 30 jours)
        recent_id = self.memory.record_lesson(
            mission_id="m-recent",
            declencheur_pattern="optimization cache memoire",
            diagnostic="Cache non purgé",
            regle="Vider le cache avant l'invalidation",
            score_utilite=1.0,
            created_at=now,
        )
        old_id = self.memory.record_lesson(
            mission_id="m-old",
            declencheur_pattern="optimization cache memoire",
            diagnostic="Ancien cache périmé",
            regle="Utiliser un LRU cache au lieu d'un dict global",
            score_utilite=1.0,
            created_at=now - (30 * 86400),  # il y a 30 jours
        )

        # Recherche des leçons à l'instant présent
        hits = self.memory.retrieve_relevant_lessons("optimization cache memoire", limit=5, current_time=now)
        self.assertEqual(len(hits), 2)
        # La récente doit avoir un score supérieur à l'ancienne
        recent_hit = next(h for h in hits if h["id"] == recent_id)
        old_hit = next(h for h in hits if h["id"] == old_id)

        self.assertGreater(recent_hit["effective_score"], old_hit["effective_score"])
        # Pour decay_rate=0.9 sur 30 jours, 0.9^30 ~= 0.042
        self.assertLess(old_hit["effective_score"], 0.1)


if __name__ == "__main__":
    unittest.main()
