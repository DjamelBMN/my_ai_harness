"""Tests réels de l'exécution Python et de la détection/rendu des artefacts (calculs & graphiques Matplotlib)."""

import unittest
from pathlib import Path
from tools.filesystem import WorkspaceFilesystem
from core.artifacts.models import ArtifactType, ArtifactStatus
from core.artifacts.engine import UniversalArtifactEngine


class TestPythonResultRendering(unittest.TestCase):
    """Vérifie l'exécution réelle sans simulation des scripts Python (calculs et graphiques)."""

    def setUp(self):
        self.workspace_dir = Path("workspace")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.workspace_dir / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fs = WorkspaceFilesystem(str(self.workspace_dir))
        self.engine = UniversalArtifactEngine()

    def test_python_calculation_script_execution_and_metrics(self):
        """Test d'un script de calcul financier/mathématique pur (comme dans la capture utilisateur).
        Doit retourner un exit_code == 0, mesurer la durée en ms, et afficher les métriques clés.
        """
        script_code = '''# Calcul de seuil financier
capital = 1000.0
taux = 0.05
annee = 0
seuil = 1500.0

while capital < seuil:
    capital = capital * (1 + taux)
    annee += 1

print(f"Le seuil est atteint au bout de : {annee} ans.")
print(f"Le montant final est de : {capital:.2f} €")
'''
        script_path = "script_seuil_test.py"
        self.fs.write_file(script_path, script_code, overwrite=True)

        # Exécution réelle via UniversalArtifactEngine.process_file
        result = self.engine.process_file(script_path, self.fs)

        self.assertIsNotNone(result)
        self.assertEqual(result.type, ArtifactType.PYTHON)
        exec_info = result.execution
        self.assertIsNotNone(exec_info)
        self.assertEqual(int(exec_info.exit_code), 0, f"Le script doit réussir avec le code 0. Stderr: {exec_info.stderr}")
        self.assertIn("Le seuil est atteint au bout de : 9 ans.", exec_info.stdout)
        self.assertIn("Le montant final est de : 1551.33 €", exec_info.stdout)
        self.assertGreater(exec_info.duration_ms, 0)

        # Nettoyage
        file_on_disk = self.workspace_dir / script_path
        if file_on_disk.exists():
            file_on_disk.unlink()

    def test_python_matplotlib_real_png_generation(self):
        """Test d'un script Matplotlib générant une parabole y = x^2 sur [-5, 5].
        Doit produire un fichier PNG réel, avec le header b'\\x89PNG\\r\\n\\x1a\\n' et être détecté.
        """
        script_code = '''import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(-5, 5, 200)
y = x ** 2

plt.figure(figsize=(7, 4.5), dpi=100)
plt.plot(x, y, label="y = x²", color="#2563EB", linewidth=2)
plt.title("Parabole f(x) = x² sur [-5, 5]")
plt.xlabel("x")
plt.ylabel("f(x)")
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend()
plt.tight_layout()
plt.show()
'''
        script_path = "plot_parabola_test.py"
        self.fs.write_file(script_path, script_code, overwrite=True)

        result = self.engine.process_file(script_path, self.fs)

        self.assertIsNotNone(result)
        exec_info = result.execution
        self.assertIsNotNone(exec_info)
        self.assertEqual(int(exec_info.exit_code or 0), 0, f"Échec d'exécution : {exec_info.stderr}")

        # Vérification qu'au moins une image PNG a été capturée et enregistrée dans les sorties
        output_paths_norm = [p.replace("\\", "/") for p in result.output_paths]
        png_outputs = [p for p in output_paths_norm if p.lower().endswith(".png")]
        self.assertTrue(len(png_outputs) > 0, f"Aucune figure PNG dans output_paths : {result.output_paths}")

        # Vérifier que le fichier PNG généré existe réellement sur le disque
        generated_png = self.workspace_dir / png_outputs[0]
        self.assertTrue(generated_png.exists(), f"Le fichier PNG {generated_png} doit exister sur le disque.")
        self.assertGreater(generated_png.stat().st_size, 1000, "Le fichier PNG doit contenir au moins 1 Ko de données.")

        # Vérification binaire stricte de l'en-tête PNG
        with open(generated_png, "rb") as f:
            header = f.read(8)
        self.assertEqual(header, b"\x89PNG\r\n\x1a\n", "Le fichier doit avoir la signature binaire officielle PNG.")

        # Nettoyage
        file_on_disk = self.workspace_dir / script_path
        if file_on_disk.exists():
            file_on_disk.unlink()
        if generated_png.exists():
            generated_png.unlink()

    def test_python_syntax_error_reporting(self):
        """Vérifie que les erreurs de script ne provoquent pas de crash et renvoient un exit_code != 0."""
        script_code = 'print("Ceci va planter" +\n'
        script_path = "broken_syntax_test.py"
        self.fs.write_file(script_path, script_code, overwrite=True)

        result = self.engine.process_file(script_path, self.fs)
        self.assertIsNotNone(result)
        exec_info = result.execution
        self.assertIsNotNone(exec_info)
        self.assertNotEqual(int(exec_info.exit_code or 0), 0)
        self.assertTrue(
            "SyntaxError" in exec_info.stderr or "never closed" in exec_info.stderr or "line 1" in exec_info.stderr,
            f"Stderr inattendu : {exec_info.stderr}",
        )

        # Nettoyage
        file_on_disk = self.workspace_dir / script_path
        if file_on_disk.exists():
            file_on_disk.unlink()


if __name__ == "__main__":
    unittest.main()

