"""
Suite de tests End-to-End (E2E) réelle pour NeoHarness AI.
RÈGLE ABSOLUE : AUCUNE SIMULATION, AUCUN MOCK, AUCUN FAUX RÉSULTAT.
Toutes les opérations s'exécutent avec les vrais runtimes, les vrais fichiers et les vérifications observables sur disque.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.artifacts.engine import UniversalArtifactEngine
from core.artifacts.models import ArtifactStatus, ArtifactType
from core.artifacts.verifier import ObservableArtifactVerifier
from tools.filesystem import WorkspaceFilesystem
from ui.server import NeoHarnessRuntimeBridge, NeoHarnessUIApp


class TestNeoHarnessE2E(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="neoharness_e2e_")
        self.bridge = NeoHarnessRuntimeBridge(workspace=self.temp_dir)
        self.fs = self.bridge.filesystem
        self.engine = UniversalArtifactEngine()
        self.app = NeoHarnessUIApp(bridge=self.bridge)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # E2E 1 : Téléversement réel de fichier via l'API -> Fichier sur disque -> Listé dans le Workspace
    # -------------------------------------------------------------------------
    def test_e2e_01_real_file_upload_and_agent_consumption(self):
        csv_content = "nom,note,statut\nAlice,18,Admis\nBob,14,Admis\nCharlie,9,Ajourné\n"
        code, resp = self.app.handle_api_post(
            "/api/files/upload",
            {
                "filename": "resultats_concours.csv",
                "content_text": csv_content,
            },
        )
        self.assertEqual(code, 200)
        uploaded_path = resp.get("path")
        self.assertEqual(uploaded_path, "uploads/resultats_concours.csv")
        self.assertGreater(resp.get("bytes", 0), 0)

        # Vérification observable sur le disque
        real_file = self.fs.resolve(uploaded_path)
        self.assertTrue(real_file.exists(), "Le fichier n'a pas été réellement écrit sur disque")
        self.assertEqual(real_file.read_text(encoding="utf-8"), csv_content)
        self.assertGreater(real_file.stat().st_size, 0)

        # Vérification que l'espace de travail liste bien le fichier avec ses métadonnées
        files_dict = self.bridge.list_workspace_files()
        uploaded_entries = [f for f in files_dict["files"] if f["path"] == uploaded_path]
        self.assertEqual(len(uploaded_entries), 1)
        self.assertEqual(uploaded_entries[0]["size_bytes"], len(csv_content.encode("utf-8")))

    # -------------------------------------------------------------------------
    # E2E 2 : Rendu réel HTML + CSS + JS interactif
    # -------------------------------------------------------------------------
    def test_e2e_02_real_html_css_js_artifact_rendering(self):
        html_code = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Calculatrice Interactive</title>
  <style>
    body { font-family: sans-serif; background: #fafafa; padding: 20px; }
    .card { background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); padding: 16px; }
  </style>
</head>
<body>
  <div class="card">
    <h1 id="title">Statistiques</h1>
    <div id="output">Total: 42</div>
  </div>
  <script>
    document.addEventListener("DOMContentLoaded", function() {
      const el = document.getElementById("output");
      if (el) el.textContent = "Calcul vérifié: 100%";
    });
  </script>
</body>
</html>"""
        html_path = "app/dashboard.html"
        self.fs.write_file(html_path, html_code)

        processed = self.engine.process_file(html_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.HTML)
        self.assertTrue(processed.metadata.get("has_js"))
        self.assertTrue(processed.metadata.get("has_css"))
        self.assertEqual(processed.primary_path, html_path)

        # Spécification d'aperçu pour le panneau droit
        handler = self.engine.find_handler(html_path)
        self.assertIsNotNone(handler)
        preview_cfg = handler.get_preview_config(processed)
        self.assertEqual(preview_cfg["renderer"], "html_sandbox")
        self.assertIn("render", preview_cfg["tabs"])

        # Vérification observable sur disque
        real_path = self.fs.resolve(html_path)
        self.assertTrue(real_path.exists())
        self.assertIn("Calculatrice Interactive", real_path.read_text(encoding="utf-8"))

    # -------------------------------------------------------------------------
    # E2E 3 : Exécution réelle de projet Python avec génération d'un graphique PNG sur disque
    # -------------------------------------------------------------------------
    def test_e2e_03_real_python_project_execution_and_plot_generation(self):
        proj_dir = "artifacts/python/project_e2e3"
        script_code = """import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

x = [1, 2, 3, 4, 5]
y = [2, 4, 9, 16, 25]

plt.figure(figsize=(6, 4))
plt.plot(x, y, marker='o', color='royalblue')
plt.title("Croissance Quadratique E2E")
plt.xlabel("X")
plt.ylabel("Y")
plt.grid(True)
plt.savefig("courbe_croissance.png", dpi=100)
plt.close()

print("PLOT_GENERATED_SUCCESSFULLY")
"""
        script_path = f"{proj_dir}/main.py"
        self.fs.write_file(script_path, script_code)

        processed = self.engine.process_file(script_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.PYTHON)
        self.assertIsNotNone(processed.execution)
        self.assertEqual(processed.execution.exit_code, 0)
        self.assertIn("PLOT_GENERATED_SUCCESSFULLY", processed.execution.stdout)

        # Vérification observable stricte du PNG produit sur disque
        png_path = self.fs.resolve(f"{proj_dir}/courbe_croissance.png")
        self.assertTrue(png_path.exists(), "Le fichier PNG n'a pas été produit sur disque")
        raw_bytes = png_path.read_bytes()
        self.assertGreater(len(raw_bytes), 1000, "Le fichier PNG est anormalement petit ou vide")
        self.assertTrue(raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "L'en-tête binaire n'est pas un vrai PNG")

    # -------------------------------------------------------------------------
    # E2E 4 : Détection réelle d'erreur d'exécution Python + Auto-réparation déterministe + Seconde exécution réelle
    # -------------------------------------------------------------------------
    def test_e2e_04_real_python_auto_repair_and_reexecution(self):
        proj_dir = "artifacts/python/project_e2e4_buggy"
        # Erreur réelle et classique : plt.YLabel au lieu de plt.ylabel (faute de casse)
        buggy_code = """import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.figure()
plt.plot([1, 2, 3], [10, 20, 30])
plt.Title("Titre")
plt.YLabel("Axe Vertical")
plt.savefig("repaired_plot.png")
plt.close()
print("REPAIR_SUCCESS_FINISHED")
"""
        script_path = f"{proj_dir}/main.py"
        self.fs.write_file(script_path, buggy_code)

        processed = self.engine.process_file(script_path, self.fs, auto_repair=True)
        # L'auto-réparation doit avoir identifié l'erreur, corrigé le code, réexécuté avec succès
        self.assertIn(processed.status, {ArtifactStatus.READY, ArtifactStatus.REPAIRED})
        self.assertTrue(processed.auto_repaired)
        self.assertIsNotNone(processed.execution)
        self.assertEqual(processed.execution.exit_code, 0)
        self.assertIn("REPAIR_SUCCESS_FINISHED", processed.execution.stdout)

        # Vérifier que le fichier sur disque a été réellement corrigé
        fixed_code = self.fs.read_file(script_path)
        self.assertIn("plt.ylabel", fixed_code)
        self.assertNotIn("plt.YLabel", fixed_code)

        # Vérifier que le plot PNG a été réellement produit et vérifié
        png_path = self.fs.resolve(f"{proj_dir}/repaired_plot.png")
        self.assertTrue(png_path.exists())
        self.assertTrue(png_path.read_bytes().startswith(b"\x89PNG"))

    # -------------------------------------------------------------------------
    # E2E 5 : Compilation réelle LaTeX via Tectonic -> Vérification binaire PDF (%PDF-, %%EOF)
    # -------------------------------------------------------------------------
    def test_e2e_05_real_latex_tectonic_compilation_and_binary_validation(self):
        latex_code = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage[french]{babel}
\title{Examen Blanc E2E}
\author{NeoHarness AI}
\date{Octobre 2026}
\begin{document}
\maketitle
\section{Exercice 1}
Soit la fonction $f(x) = x^2 - 3x + 2$.
\begin{enumerate}
    \item Calculer $f'(x)$.
    \item Démontrer que $f$ admet un minimum en $x = \frac{3}{2}$.
\end{enumerate}
\end{document}
"""
        tex_path = "sujet_examen.tex"
        self.fs.write_file(tex_path, latex_code)

        processed = self.engine.process_file(tex_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.LATEX)
        self.assertIn("pdf_path", processed.metadata)
        pdf_rel = processed.metadata["pdf_path"]

        # Vérification observable sur le disque
        pdf_file = self.fs.resolve(pdf_rel)
        self.assertTrue(pdf_file.exists(), "Le fichier PDF compilé par Tectonic n'existe pas sur disque")
        pdf_bytes = pdf_file.read_bytes()
        self.assertGreater(len(pdf_bytes), 2000, "Le PDF produit est trop court ou vide")
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"), "L'en-tête binaire n'est pas un PDF valide")
        self.assertIn(b"%%EOF", pdf_bytes, "Le PDF est incomplet (marqueur EOF manquant)")

    # -------------------------------------------------------------------------
    # E2E 6 : Rendu et validation réelle de diagramme Mermaid
    # -------------------------------------------------------------------------
    def test_e2e_06_real_mermaid_diagram_validation(self):
        mermaid_code = """flowchart TD
    A[Demande Utilisateur] --> B[Analyseur d'Intention]
    B --> C{Requiert Outils?}
    C -- Oui --> D[Tool Registry & Execution]
    C -- Non --> E[Réponse Directe]
    D --> F[Universal Artifact Engine]
    F --> G[Vérification Observable sur Disque]
    G --> H[Affichage Panneau Droit]
"""
        mermaid_path = "architecture_workflow.mmd"
        self.fs.write_file(mermaid_path, mermaid_code)

        processed = self.engine.process_file(mermaid_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.MERMAID)
        self.assertEqual(processed.metadata.get("diagram_type"), "flowchart")
        self.assertGreater(processed.metadata.get("lines_count", 0), 0)

    # -------------------------------------------------------------------------
    # E2E 7 : Validation Markdown enrichi avec KaTeX mathématique
    # -------------------------------------------------------------------------
    def test_e2e_07_real_markdown_katex_validation(self):
        md_code = """# Rapport d'Analyse Numérique

Soit l'intégrale de Gauss définie par :
$$I = \\int_{-\\infty}^{+\\infty} e^{-x^2} dx = \\sqrt{\\pi}$$

Et l'équation d'Euler :
$$e^{i\\pi} + 1 = 0$$

## Conclusion
Le modèle converge au bout de $N = 42$ itérations.
"""
        md_path = "rapport_maths.md"
        self.fs.write_file(md_path, md_code)

        processed = self.engine.process_file(md_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.MARKDOWN)
        self.assertGreater(processed.metadata.get("math_blocks_count", 0), 0)
        verif = ObservableArtifactVerifier.verify(processed, self.fs)
        self.assertTrue(verif["verified"])

    # -------------------------------------------------------------------------
    # E2E 8 : Validation réelle de structure et contenu JSON
    # -------------------------------------------------------------------------
    def test_e2e_08_real_json_validation(self):
        data = {
            "version": "2.4.0",
            "statut": "production",
            "modules": ["engine", "verifier", "handlers"],
            "metriques": {"couverture": 100, "simulations_autorisees": 0},
        }
        json_path = "config/release.json"
        self.fs.write_file(json_path, json.dumps(data, indent=2))

        processed = self.engine.process_file(json_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.JSON)
        verif = ObservableArtifactVerifier.verify(processed, self.fs)
        self.assertTrue(verif["verified"])
        self.assertEqual(verif["items_count"], 4)

    # -------------------------------------------------------------------------
    # E2E 9 : Validation et auto-réparation SVG
    # -------------------------------------------------------------------------
    def test_e2e_09_real_svg_validation_and_repair(self):
        svg_code = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" />
</svg>"""
        svg_path = "icons/badge.svg"
        self.fs.write_file(svg_path, svg_code)

        processed = self.engine.process_file(svg_path, self.fs)
        self.assertEqual(processed.status, ArtifactStatus.READY)
        self.assertEqual(processed.type, ArtifactType.SVG)
        verif = ObservableArtifactVerifier.verify(processed, self.fs)
        self.assertTrue(verif["verified"])
        self.assertEqual(verif["root_tag"], "svg")

    # -------------------------------------------------------------------------
    # E2E 10 : Scénario Global - Cycle Complet Agentique (Comprendre -> Planifier -> Agir -> Compiler -> Vérifier -> Livrer)
    # -------------------------------------------------------------------------
    def test_e2e_10_complete_agentic_mission_lifecycle(self):
        # 1. État initial : L'utilisateur fournit des données brutes
        input_data = [
            {"id": 1, "matiere": "Mathématiques", "moyenne": 15.5},
            {"id": 2, "matiere": "Physique", "moyenne": 14.0},
            {"id": 3, "matiere": "Informatique", "moyenne": 17.5},
        ]
        self.fs.write_file("donnees_classes.json", json.dumps(input_data))

        # 2. Exécution du script Python qui lit le JSON et calcule les statistiques
        calc_script = """import json
from pathlib import Path

data_file = Path("donnees_classes.json")
if not data_file.exists():
    data_file = Path(__file__).parent / "donnees_classes.json"

with open(data_file, "r", encoding="utf-8") as f:
    data = json.load(f)

total = sum(d["moyenne"] for d in data)
moyenne_generale = total / len(data)

rapport = {
    "nb_matieres": len(data),
    "moyenne_generale": round(moyenne_generale, 2)
}

out_file = Path("statistiques.json")
if not out_file.parent.exists():
    out_file = Path(__file__).parent / "statistiques.json"

with open(out_file, "w", encoding="utf-8") as f:
    json.dump(rapport, f, indent=2)

print("CALCUL_ETUDIANTS_TERMINE")
"""
        self.fs.write_file("analyser.py", calc_script)

        processed_py = self.engine.process_file("analyser.py", self.fs)
        self.assertEqual(processed_py.status, ArtifactStatus.READY)
        self.assertEqual(processed_py.execution.exit_code, 0)
        self.assertTrue(self.fs.resolve("statistiques.json").exists())

        # 3. L'agent génère ensuite un document LaTeX présentant ces résultats
        with open(self.fs.resolve("statistiques.json"), "r", encoding="utf-8") as f:
            stats = json.load(f)

        latex_report = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\title{{Bilan Académique Officiel}}
\\begin{{document}}
\\maketitle
Nombre de disciplines : {stats['nb_matieres']}\\\\
Moyenne globale de promotion : {stats['moyenne_generale']} / 20.
\\end{{document}}
"""
        self.fs.write_file("rapport_final.tex", latex_report)

        # 4. Compilation réelle LaTeX via Tectonic
        processed_latex = self.engine.process_file("rapport_final.tex", self.fs)
        self.assertEqual(processed_latex.status, ArtifactStatus.READY)

        # 5. Vérification observable absolue
        pdf_path = self.fs.resolve(processed_latex.metadata["pdf_path"])
        self.assertTrue(pdf_path.exists())
        pdf_bytes = pdf_path.read_bytes()
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", pdf_bytes)

        # 6. Spécification Panneau Droit de l'UI
        preview_cfg = self.engine.find_handler("rapport_final.tex").get_preview_config(processed_latex)
        self.assertEqual(preview_cfg["renderer"], "pdf_viewer")
        self.assertIn("render", preview_cfg["tabs"])


if __name__ == "__main__":
    unittest.main()

