"""Tests unitaires et d'intégration pour la mémoire conversationnelle et la continuité de tâche."""

import unittest
from core.task_context import TaskContext, TaskContinuityManager
from core.intent_engine import IntentEngine


class TestConversationalMemory(unittest.TestCase):
    """Vérifie la robustesse de la mémoire conversationnelle et des enchaînements multi-tours."""

    def setUp(self):
        self.context = TaskContext(
            task_id="task-math-curriculum-001",
            conversation_id="conv-math-curriculum",
            title="Programme de maths Première",
        )
        self.intent_engine = IntentEngine()

    def test_multi_turn_curriculum_continuity(self):
        """Enchaînement canonique :
        1. Trouve le programme officiel de Première spécialité maths.
        2. analyse la partie sur les suites
        3. compare avec celui de Terminale
        4. fais-moi un tableau
        5. ajoute les compétences associées
        """
        # Tour 1 : Objectif initial
        t1_prompt = "Trouve le programme officiel de Première spécialité maths."
        self.assertTrue(self.context.is_relevant_to_active_task(t1_prompt))
        self.context.record_turn(
            user_prompt=t1_prompt,
            assistant_summary="Programme de Première spécialité mathématiques trouvé : Algèbre, Analyse, Géométrie, Probas-Stats.",
            skill="rag",
            agent="ResearchAgent",
            intent="general_question",
            status="completed",
            sources=[{"title": "Programme Première Spé Maths", "url": "https://eduscol.education.fr/maths-1ere"}],
        )
        self.assertEqual(self.context.initial_objective, t1_prompt)
        self.assertEqual(len(self.context.sources), 1)

        # Tour 2 : "analyse la partie sur les suites"
        t2_prompt = "analyse la partie sur les suites"
        self.assertTrue(self.context.is_relevant_to_active_task(t2_prompt))
        # Vérification du prompt de continuité généré
        c_prompt2 = self.context.build_continuity_prompt(t2_prompt)
        self.assertIn("Programme Première Spé Maths", c_prompt2)
        self.assertIn("ANALYSE DÉTAILLÉE", c_prompt2)

        self.context.record_turn(
            user_prompt=t2_prompt,
            assistant_summary="Les suites en 1ère couvrent la récurrence intuitive, suites arithmétiques, géométriques et limites intuitives.",
            skill="rag",
            agent="ResearchAgent",
            intent="general_question",
            status="completed",
        )
        self.assertEqual(len(self.context.turns), 2)

        # Tour 3 : "compare avec celui de Terminale"
        t3_prompt = "compare avec celui de Terminale"
        self.assertTrue(self.context.is_relevant_to_active_task(t3_prompt))
        c_prompt3 = self.context.build_continuity_prompt(t3_prompt)
        self.assertIn("COMPARAISON STRUCTURÉE", c_prompt3)

        self.context.record_turn(
            user_prompt=t3_prompt,
            assistant_summary="En Terminale, les suites introduisent le raisonnement par récurrence formel, le théorème de convergence monotone.",
            skill="rag",
            agent="ResearchAgent",
            intent="general_question",
            status="completed",
        )
        self.assertEqual(len(self.context.turns), 3)

        # Tour 4 : "fais-moi un tableau"
        t4_prompt = "fais-moi un tableau"
        self.assertTrue(self.context.is_relevant_to_active_task(t4_prompt))
        c_prompt4 = self.context.build_continuity_prompt(t4_prompt)
        self.assertIn("TABLEAU COMPARATIF SYNTHÉTIQUE", c_prompt4)

        self.context.record_turn(
            user_prompt=t4_prompt,
            assistant_summary="| Notion | 1ère Spécialité | Terminale Spécialité |\n|---|---|---|\n| Récurrence | Intuition | Formelle |",
            skill="rag",
            agent="ResearchAgent",
            intent="general_question",
            status="completed",
        )
        self.assertEqual(len(self.context.turns), 4)

        # Tour 5 : "ajoute les compétences associées"
        t5_prompt = "ajoute les compétences associées"
        self.assertTrue(self.context.is_relevant_to_active_task(t5_prompt))
        c_prompt5 = self.context.build_continuity_prompt(t5_prompt)
        self.assertIn("ENRICHISSEMENT ET COMPLÉMENT", c_prompt5)

        self.context.record_turn(
            user_prompt=t5_prompt,
            assistant_summary="Tableau mis à jour avec la colonne Compétences (Chercher, Modéliser, Représenter, Raisonner, Calculer, Communiquer).",
            skill="rag",
            agent="ResearchAgent",
            intent="general_question",
            status="completed",
        )
        self.assertEqual(len(self.context.turns), 5)
        self.assertFalse(self.context.is_explicit_new_task(t5_prompt))

    def test_atomic_clock_link_autonomous_choice(self):
        """Enchaînement :
        1. Où trouver l'heure atomique ?
        2. donne le lien
        3. peu importe
        L'agent doit sélectionner immédiatement la source primaire la plus autoritaire.
        """
        clock_ctx = TaskContext(
            task_id="task-atomic-clock-002",
            conversation_id="conv-atomic-clock",
            title="Heure atomique officielle",
        )

        # Tour 1
        t1 = "Où trouver l'heure atomique ?"
        clock_ctx.record_turn(
            user_prompt=t1,
            assistant_summary="L'heure atomique légale en France est générée par le SYRTE à l'Observatoire de Paris, et au niveau international par le BIPM.",
            sources=[
                {"title": "Observatoire de Paris - Heure légale", "url": "https://syrte.obspm.fr/tictac/heure.php"},
                {"title": "BIPM - Temps Universel Coordonné", "url": "https://www.bipm.org/fr/time-metrology"},
            ],
        )
        self.assertEqual(len(clock_ctx.sources), 2)
        primary_link = clock_ctx.get_primary_source_link()
        self.assertEqual(primary_link, "https://syrte.obspm.fr/tictac/heure.php")

        # Tour 2 : "donne le lien"
        t2 = "donne le lien"
        self.assertTrue(clock_ctx.is_relevant_to_active_task(t2))
        prompt2 = clock_ctx.build_continuity_prompt(t2)
        self.assertIn("LIEN DIRECT", prompt2)
        self.assertIn("https://syrte.obspm.fr/tictac/heure.php", prompt2)

        # Tour 3 : "peu importe"
        t3 = "peu importe"
        self.assertTrue(clock_ctx.is_relevant_to_active_task(t3))
        prompt3 = clock_ctx.build_continuity_prompt(t3)
        self.assertIn("CHOIX AUTONOME IMMÉDIAT", prompt3)
        self.assertIn("Ne demande pas de confirmation", prompt3)
        self.assertIn("https://syrte.obspm.fr/tictac/heure.php", prompt3)

    def test_product_comparison_sequence(self):
        """Enchaînement commercial :
        1. Trouve les meilleures offres pour un PC ultraportable 16 Go.
        2. compare les deux premières
        3. lequel est le meilleur ?
        4. donne-moi le lien
        5. et si je prends le deuxième ?
        """
        pc_ctx = TaskContext(
            task_id="task-pc-offers-003",
            conversation_id="conv-pc-offers",
            title="Comparatif PC ultraportables",
        )

        # 1. Requête initiale
        pc_ctx.record_turn(
            user_prompt="Trouve les meilleures offres pour un PC ultraportable 16 Go.",
            assistant_summary="Offres trouvées : 1. Lenovo ThinkPad T14 (899 €) ; 2. Dell XPS 13 (999 €).",
            sources=[
                {"title": "Lenovo Shop", "url": "https://lenovo.com/deal-t14"},
                {"title": "Dell Store", "url": "https://dell.com/deal-xps13"},
            ],
        )

        # 2. compare les deux premières
        self.assertTrue(pc_ctx.is_relevant_to_active_task("compare les deux premières"))
        p_comp = pc_ctx.build_continuity_prompt("compare les deux premières")
        self.assertIn("COMPARAISON STRUCTURÉE", p_comp)

        # 3. lequel est le meilleur ?
        self.assertTrue(pc_ctx.is_relevant_to_active_task("lequel est le meilleur ?"))
        p_best = pc_ctx.build_continuity_prompt("lequel est le meilleur ?")
        self.assertIn("RECOMMANDATION TRANCHÉE ET JUSTIFIÉE", p_best)

        # 4. donne-moi le lien
        self.assertTrue(pc_ctx.is_relevant_to_active_task("donne-moi le lien"))
        p_link = pc_ctx.build_continuity_prompt("donne-moi le lien")
        self.assertIn("LIEN DIRECT", p_link)
        self.assertIn("https://lenovo.com/deal-t14", p_link)

        # 5. et si je prends le deuxième ?
        self.assertTrue(pc_ctx.is_relevant_to_active_task("et si je prends le deuxième ?"))
        p_second = pc_ctx.build_continuity_prompt("et si je prends le deuxième ?")
        self.assertIn("ANALYSE D'ALTERNATIVE", p_second)

    def test_task_isolation_between_conversations(self):
        """Vérifie l'étanchéité stricte des contextes de tâches différentes."""
        manager = TaskContinuityManager()
        ctx_a = manager.get_or_create_context(conversation_id="conv-a", task_id="task-a", user_prompt="Calcul des suites")
        ctx_b = manager.get_or_create_context(conversation_id="conv-b", task_id="task-b", user_prompt="Page web d'accueil")

        ctx_a.record_turn(user_prompt="Calcul des suites", assistant_summary="Suite un calculée", files_modified=[{"path": "workspace/suite.py", "type": "modified"}])
        ctx_b.record_turn(user_prompt="Page web d'accueil", assistant_summary="HTML créé", files_modified=[{"path": "workspace/index.html", "type": "created"}])

        self.assertIn("workspace/suite.py", ctx_a.files)
        self.assertNotIn("workspace/index.html", ctx_a.files)

        self.assertIn("workspace/index.html", ctx_b.files)
        self.assertNotIn("workspace/suite.py", ctx_b.files)

        # Suivi continu dans conv-a
        resolved_a = manager.resolve_active_task("conv-a", "ajoute n=100")
        self.assertEqual(resolved_a.task_id, "task-a")
        self.assertIn("workspace/suite.py", resolved_a.files)

        # Demande explicite de nouvelle tâche
        self.assertTrue(resolved_a.is_explicit_new_task("nouvelle tâche : génère un rapport"))


if __name__ == "__main__":
    unittest.main()

