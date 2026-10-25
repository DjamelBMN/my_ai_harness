"""
Tests réels pour le rendu Matplotlib headless et optimisé de NeoHarness AI.
RÈGLE ABSOLUE : AUCUNE SIMULATION, VRAI RUNTIME, VRAIS FICHIERS PNG.
"""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from core.artifacts.engine import UniversalArtifactEngine
from core.artifacts.models import ArtifactStatus
from tools.filesystem import WorkspaceFilesystem
from tools.python_runtime import validate_png
from tools.terminal import run_python_script


class TestMatplotlibHeadlessRendering(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_mpl_headless_")
        self.fs = WorkspaceFilesystem(self.temp_dir)
        self.engine = UniversalArtifactEngine()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_matplotlib_show_without_savefig_produces_valid_png_in_output(self):
        """Un script avec plt.show() et sans savefig ne bloque pas et produit figure_1.png dans output/."""
        code = """import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(-3, 3, 100)
y = x**2

plt.figure(figsize=(6, 4))
plt.plot(x, y, label="y = x^2", color="royalblue")
plt.title("Fonction Carre")
plt.grid(True)
plt.legend()
plt.show()  # Doit capturer automatiquement la figure sans bloquer
"""
        self.fs.write_file("parabole.py", code)

        t0 = time.monotonic()
        art = self.engine.process_file("parabole.py", self.fs, timeout_seconds=15)
        duration = time.monotonic() - t0

        # Vérification statut et temps d'exécution (très inférieur à 60s)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertLess(duration, 8.0, "L'exécution d'un graphique simple a dépassé le seuil de rapidité")

        # Vérification du dossier output/ et de la figure
        expected_fig = "output/figure_1.png"
        self.assertIn(expected_fig, art.output_paths)
        self.assertEqual(art.metadata.get("visual_output"), expected_fig)

        fig_abs = self.fs.resolve(expected_fig)
        self.assertTrue(fig_abs.is_file(), f"Le fichier {expected_fig} n'existe pas sur le disque")

        # Validation structurelle réelle du binaire PNG (IHDR, IDAT, IEND, CRC32)
        v = validate_png(fig_abs)
        self.assertTrue(v.get("valid"), f"Fichier PNG corrompu ou invalide : {v.get('error')}")
        self.assertGreater(v.get("width", 0), 100)
        self.assertGreater(v.get("height", 0), 100)
        self.assertGreater(v.get("size_bytes", 0), 1000)

    def test_02_multiple_figures_captured_in_order(self):
        """Plusieurs figures ouvertes sont toutes capturées dans l'ordre."""
        code = """import matplotlib.pyplot as plt

plt.figure()
plt.plot([1, 2, 3], [1, 4, 9])
plt.title("Figure 1")
plt.show()

plt.figure()
plt.plot([1, 2, 3], [1, 8, 27])
plt.title("Figure 2")
plt.show()
"""
        self.fs.write_file("multi_plots.py", code)

        art = self.engine.process_file("multi_plots.py", self.fs)
        self.assertEqual(art.status, ArtifactStatus.READY)
        figures = art.metadata.get("figures", [])
        self.assertEqual(len(figures), 2)
        self.assertEqual(figures[0], "output/figure_1.png")
        self.assertEqual(figures[1], "output/figure_2.png")

        for fig in figures:
            fig_abs = self.fs.resolve(fig)
            self.assertTrue(fig_abs.is_file())
            v = validate_png(fig_abs)
            self.assertTrue(v.get("valid"))

    def test_03_run_python_tool_captures_figures_cleanly(self):
        """L'outil run_python de l'agent capture les figures et renvoie la liste dans son résultat."""
        code = """import matplotlib.pyplot as plt
plt.plot([0, 1], [0, 1])
plt.title("Ligne")
plt.show()
"""
        self.fs.write_file("agent_script.py", code)
        res = run_python_script(self.fs.root, "agent_script.py", timeout_seconds=15)
        self.assertEqual(res["status"], "passed")
        self.assertEqual(res["exit_code"], 0)
        self.assertTrue(res.get("figures"))
        self.assertEqual(res["figures"][0]["path"], "output/figure_1.png")
        self.assertTrue(res["figures"][0]["valid"])


if __name__ == "__main__":
    unittest.main()

