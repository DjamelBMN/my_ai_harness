import unittest
import tempfile
import subprocess
from pathlib import Path

from core.checkpoint import CheckpointManager, DeadlockDetector
from tools.filesystem import WorkspaceFilesystem


class TestCheckpointBacktracking(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

        # Initialisation d'un vrai dépôt git utilisateur pour prouver la non-pollution
        subprocess.run(["git", "init"], cwd=self.workspace, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "User Dev"], cwd=self.workspace, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "user@dev.local"], cwd=self.workspace, capture_output=True, check=True)

        # Fichier initial utilisateur
        (self.workspace / "README.md").write_text("# Projet Utilisateur\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.workspace, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit utilisateur"], cwd=self.workspace, capture_output=True, check=True)

        self.mgr = CheckpointManager(workspace=self.workspace)
        self.detector = DeadlockDetector(max_consecutive_errors=3)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- 1. Test Rollback physique de 3 fichiers ---
    def test_01_create_checkpoint_and_rollback(self):
        """Vérifie la restauration exacte de l'espace physique après modification de 3 fichiers."""
        # État initial : fichier base.py
        (self.workspace / "base.py").write_text("print('base')\n", encoding="utf-8")
        cp1 = self.mgr.create_checkpoint("point_depart", memory_state={"step": 1})

        # Modification de 3 fichiers
        (self.workspace / "base.py").write_text("print('modifie')\n", encoding="utf-8")
        (self.workspace / "nouveau1.py").write_text("x = 1\n", encoding="utf-8")
        (self.workspace / "nouveau2.py").write_text("y = 2\n", encoding="utf-8")

        self.assertTrue((self.workspace / "nouveau1.py").exists())
        self.assertTrue((self.workspace / "nouveau2.py").exists())
        self.assertEqual((self.workspace / "base.py").read_text(encoding="utf-8"), "print('modifie')\n")

        # Rollback au point de départ
        ok, restored_mem, _ = self.mgr.rollback(cp1)
        self.assertTrue(ok)
        self.assertEqual(restored_mem.get("step"), 1)

        # Le fichier base.py est restauré
        self.assertEqual((self.workspace / "base.py").read_text(encoding="utf-8"), "print('base')\n")
        # Les fichiers créés après le checkpoint sont supprimés
        self.assertFalse((self.workspace / "nouveau1.py").exists())
        self.assertFalse((self.workspace / "nouveau2.py").exists())

    # --- 2. Isolation totale : Ne pollue pas le git utilisateur ---
    def test_02_shadow_repo_does_not_pollute_user_git_log(self):
        """Les snapshots ne doivent JAMAIS apparaître dans le git log de l'utilisateur."""
        # Création de plusieurs snapshots shadow
        (self.workspace / "work.txt").write_text("v1\n", encoding="utf-8")
        self.mgr.create_checkpoint("snap1")
        (self.workspace / "work.txt").write_text("v2\n", encoding="utf-8")
        self.mgr.create_checkpoint("snap2")

        # Vérification du git log du workspace utilisateur
        res = subprocess.run(["git", "log", "--oneline"], cwd=self.workspace, capture_output=True, text=True, check=True)
        user_log = res.stdout.strip()

        self.assertNotIn("checkpoint: snap1", user_log)
        self.assertNotIn("checkpoint: snap2", user_log)
        self.assertIn("Initial commit utilisateur", user_log)

    # --- 3. Détection d'impasse et marquage dead-end ---
    def test_03_deadlock_detection_and_mark_dead_end(self):
        """Détection d'impasse à 3 erreurs consécutives et marquage dead-end."""
        is_dl, reason = self.detector.is_deadlock(consecutive_tool_failures=3)
        self.assertTrue(is_dl)
        self.assertIn("3 échecs", reason)

        # Création et marquage d'une branche comme impasse
        cid = self.mgr.create_checkpoint("branche_ko", hypothesis="tentative par script bash")
        self.mgr.mark_dead_end(cid, reason="droits insuffisants")

        meta = self.mgr.checkpoints[cid]
        self.assertTrue(meta.dead_end)
        self.assertFalse(meta.is_healthy)
        self.assertIn("DEAD_END", meta.hypothesis)

    # --- 4. Exploration de 2 branches et abandon de la mauvaise ---
    def test_04_candidate_branches_exploration(self):
        """Exploration de deux pistes : conservation de la bonne, abandon de l'autre."""
        root_cp = self.mgr.create_checkpoint("racine", memory_state={"phase": "init"})

        # Piste A : tente d'installer un package non standard (échoue)
        (self.workspace / "approach_a.py").write_text("# Tentative complexe", encoding="utf-8")
        cp_a = self.mgr.create_checkpoint("piste_a", hypothesis="Piste A lourde")
        self.mgr.mark_dead_end(cp_a, reason="échec de compilation")

        # Rollback à la racine
        self.mgr.rollback(root_cp)
        self.assertFalse((self.workspace / "approach_a.py").exists())

        # Piste B : solution standard directe (réussit)
        (self.workspace / "approach_b.py").write_text("def solve(): return True\n", encoding="utf-8")
        cp_b = self.mgr.create_checkpoint("piste_b", hypothesis="Piste B simple")

        self.assertTrue((self.workspace / "approach_b.py").exists())
        self.assertFalse((self.workspace / "approach_a.py").exists())
        self.assertTrue(self.mgr.checkpoints[cp_b].is_healthy)
        self.assertTrue(self.mgr.checkpoints[cp_a].dead_end)


if __name__ == "__main__":
    unittest.main()
