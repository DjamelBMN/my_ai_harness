# RÔLE DE CE FICHIER :
# Valide la persistance et la continuité du contexte de la tâche active.
# Teste les enchaînements de demandes courtes (« ensuite », « corrige ça », « passe au test suivant »,
# « ça marche », « améliore-le », « continue ») sur une même tâche active,
# sans simulation, avec vérification des fichiers, des statuts et de l'isolation entre tâches.

import unittest
from core.context import Context
from core.intent_engine import IntentEngine
from core.task import Task
from core.task_context import TaskContext
from ui.server import NeoHarnessRuntimeBridge


class TestTaskContextContinuity(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = IntentEngine()

    def test_01_continuity_request_detection(self) -> None:
        """Vérifie la détection systématique des messages de continuité sur une tâche active."""
        tc = TaskContext(
            conversation_id="conv-test-1",
            initial_objective="Générer un exercice sur les suites arithmétiques",
            last_skill="exercice",
            last_agent="coder",
            last_intent="coding",
            files=["exercice_suites.tex"],
        )

        continuity_phrases = [
            "ensuite",
            "et ensuite",
            "puis",
            "après",
            "continue",
            "continue s'il te plaît",
            "poursuis",
            "avance",
            "fais la suite",
            "corrige ça",
            "corrige l'erreur",
            "répare ça",
            "règle le problème",
            "fix",
            "débogue le script",
            "passe au test suivant",
            "lance les tests",
            "relance les tests",
            "teste-le",
            "ça marche",
            "ça fonctionne",
            "c'est bon",
            "parfait",
            "super",
            "améliore-le",
            "peaufine",
            "optimise",
            "complète",
            "refais-le",
            "compile-le",
            "affiche-le",
            "ajoute la question 2",
        ]

        for phrase in continuity_phrases:
            self.assertTrue(
                tc.is_continuity_request(phrase),
                f"La phrase '{phrase}' aurait dû être reconnue comme une continuité de la tâche active.",
            )

        # Vérifie qu'une demande explicite de nouvelle tâche n'est pas traitée comme une continuité
        new_task_phrases = [
            "nouvelle tâche",
            "autre tâche s'il te plaît",
            "change de sujet",
            "recommence à zéro",
        ]
        for phrase in new_task_phrases:
            self.assertFalse(
                tc.is_continuity_request(phrase),
                f"La phrase '{phrase}' est une rupture explicite et ne doit pas être traitée comme continuité.",
            )

    def test_02_intent_engine_continuity_resolution(self) -> None:
        """Vérifie que l'IntentEngine oriente les messages courts selon le contexte de la tâche active."""
        tc = TaskContext(
            conversation_id="conv-test-2",
            initial_objective="Écrire un script python de calcul matriciel",
            last_skill="",
            last_agent="coder",
            last_intent="coding",
            files=["matrix.py"],
        )
        tc.record_error("TypeError: unsupported operand type", compiler="python")

        # 1. « corrige ça » avec erreur active -> coding avec fichiers cibles
        dec_fix = self.engine.decide("corrige ça", task_context=tc)
        self.assertEqual(dec_fix.intent, "coding")
        self.assertTrue(dec_fix.requires_modification)
        self.assertIn("matrix.py", dec_fix.files_required)

        # 2. « passe au test suivant » -> testing avec fichiers cibles
        dec_test = self.engine.decide("passe au test suivant", task_context=tc)
        self.assertEqual(dec_test.intent, "testing")
        self.assertTrue(dec_test.requires_tests)

        # 3. « ensuite » -> conserve l'intention coding
        dec_next = self.engine.decide("ensuite", task_context=tc)
        self.assertEqual(dec_next.intent, "coding")
        self.assertTrue(dec_next.requires_workspace)

        # 4. « améliore-le » -> conserve l'intention coding
        dec_improve = self.engine.decide("améliore-le", task_context=tc)
        self.assertEqual(dec_improve.intent, "coding")

    def test_03_task_context_serialization_and_errors(self) -> None:
        """Vérifie le cycle de vie, la sérialisation et la résolution des erreurs."""
        tc = TaskContext(conversation_id="conv-test-3")
        self.assertEqual(tc.initial_objective, "")

        # Tour 1 : objectif initial et modification
        tc.record_turn(
            "crée un script data.py",
            "Script créé avec succès",
            skill="",
            agent="coder",
            intent="coding",
            status="Terminé",
            files_modified=[{"path": "data.py", "action": "created"}],
        )
        self.assertEqual(tc.initial_objective, "crée un script data.py")
        self.assertIn("data.py", tc.files)
        self.assertEqual(len(tc.turns), 1)

        # Tour 2 : apparition d'une erreur
        tc.record_turn(
            "exécute data.py",
            "Échec à l'exécution",
            status="Erreur",
            errors=["NameError: name 'df' is not defined"],
        )
        self.assertEqual(len(tc.get_unresolved_errors()), 1)
        self.assertEqual(tc.get_unresolved_errors()[0]["message"], "NameError: name 'df' is not defined")

        # Tour 3 : correction et résolution
        tc.record_turn(
            "corrige ça",
            "Erreur corrigée",
            status="Terminé",
            files_modified=[{"path": "data.py", "action": "modified"}],
        )
        self.assertEqual(len(tc.get_unresolved_errors()), 0)

        # Sérialisation et reconstruction
        raw_dict = tc.to_dict()
        restored = TaskContext.from_dict(raw_dict)
        self.assertEqual(restored.conversation_id, tc.conversation_id)
        self.assertEqual(restored.initial_objective, tc.initial_objective)
        self.assertEqual(restored.files, tc.files)
        self.assertEqual(len(restored.turns), 3)

    def test_04_bridge_multi_turn_continuity_without_spurious_tasks(self) -> None:
        """Vérifie qu'un enchaînement de messages courts reste sur la tâche active sans créer de tâche parasite."""
        bridge = NeoHarnessRuntimeBridge()
        bridge.auto_approve_in_headless = True

        # Création de la conversation initiale
        conv = bridge.create_conversation("Calculatrice Python")
        cid = conv["id"]
        initial_conv_count = len(bridge.list_conversations())

        # Tour 1 : Objectif initial
        res1 = bridge.execute_task(
            "code une fonction add(a, b) dans workspace/calc.py",
            conversation_id=cid,
        )
        self.assertEqual(res1["conversation"]["id"], cid)
        self.assertEqual(len(bridge.list_conversations()), initial_conv_count)

        tc = TaskContext.from_conversation(bridge.get_conversation(cid))
        self.assertEqual(tc.conversation_id, cid)
        self.assertIn("add", tc.initial_objective.lower())

        # Tour 2 : Message court « ensuite »
        res2 = bridge.execute_task("ensuite", conversation_id=cid)
        self.assertEqual(res2["conversation"]["id"], cid)
        # Aucune nouvelle tâche créée
        self.assertEqual(len(bridge.list_conversations()), initial_conv_count)
        tc2 = TaskContext.from_conversation(bridge.get_conversation(cid))
        self.assertEqual(tc2.initial_objective, tc.initial_objective)
        self.assertEqual(len(tc2.turns), 2)

        # Tour 3 : Message court « passe au test suivant »
        res3 = bridge.execute_task("passe au test suivant", conversation_id=cid)
        self.assertEqual(res3["conversation"]["id"], cid)
        self.assertEqual(len(bridge.list_conversations()), initial_conv_count)
        tc3 = TaskContext.from_conversation(bridge.get_conversation(cid))
        self.assertEqual(len(tc3.turns), 3)

        # Tour 4 : Message court « ça marche »
        res4 = bridge.execute_task("ça marche", conversation_id=cid)
        self.assertEqual(res4["conversation"]["id"], cid)
        self.assertEqual(len(bridge.list_conversations()), initial_conv_count)
        tc4 = TaskContext.from_conversation(bridge.get_conversation(cid))
        self.assertEqual(len(tc4.turns), 4)

    def test_05_conversation_isolation_and_selection(self) -> None:
        """Vérifie que deux tâches actives distinctes ne partagent pas leur contexte."""
        bridge = NeoHarnessRuntimeBridge()
        bridge.auto_approve_in_headless = True

        # Tâche 1 : LaTeX Bac Blanc
        c1 = bridge.create_conversation("Bac blanc de mathématiques")
        cid1 = c1["id"]
        tc1 = TaskContext(
            conversation_id=cid1,
            initial_objective="Bac blanc de mathématiques 2026",
            last_skill="bacblanc",
            files=["bacblanc.tex"],
        )
        c1["task_context"] = tc1.to_dict()
        bridge._save_conversations()

        # Tâche 2 : Script Python Matplotlib
        c2 = bridge.create_conversation("Graphique de la fonction carré")
        cid2 = c2["id"]
        tc2 = TaskContext(
            conversation_id=cid2,
            initial_objective="Tracer la fonction carré avec matplotlib",
            last_skill="",
            last_agent="coder",
            files=["plot_square.py"],
        )
        c2["task_context"] = tc2.to_dict()
        bridge._save_conversations()

        # Sélection de la tâche 1
        sel1 = bridge.select_conversation(cid1)
        self.assertEqual(sel1["id"], cid1)
        self.assertEqual(bridge.orchestrator.context.task_context.conversation_id, cid1)
        self.assertIn("bacblanc.tex", bridge.orchestrator.context.task_context.files)
        self.assertNotIn("plot_square.py", bridge.orchestrator.context.task_context.files)

        # Sélection de la tâche 2
        sel2 = bridge.select_conversation(cid2)
        self.assertEqual(sel2["id"], cid2)
        self.assertEqual(bridge.orchestrator.context.task_context.conversation_id, cid2)
        self.assertIn("plot_square.py", bridge.orchestrator.context.task_context.files)
        self.assertNotIn("bacblanc.tex", bridge.orchestrator.context.task_context.files)


if __name__ == "__main__":
    unittest.main()

