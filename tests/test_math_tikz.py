# RÔLE DE CE FICHIER :
# Tests unitaires stricts pour le moteur déterministe de figures et tableaux mathématiques TikZ (Section D).
# Valide zéro hallucination, oracles SymPy stricts, gestion des asymptotes, arbres pondérés,
# versions enseignant/élève, compilation autonome Tectonic et contrôle visuel rasterisé.

from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import unittest
import sympy as sp

from tools.math_tikz import (
    MathConsistencyError,
    MathOracle,
    generate_variation_table,
    generate_sign_table,
    generate_probability_tree,
    generate_curve_plot,
    generate_math_figure,
    render_math_figure_to_pdf,
    verify_figure_consistency,
)
from tools.rasterizer import PDFRasterizer


class TestMathTikZFigures(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_math_tikz_")
        self.workspace = Path(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_variation_table_log_rational(self) -> None:
        """(a) Tableau de variations de f(x) = x - ln(x)/x : flèches et valeurs conformes au calcul SymPy."""
        result = generate_variation_table("x - ln(x)/x", var_str="x", domain=(0, sp.oo))

        # Vérifications structurelles et mathématiques
        self.assertTrue(result["verified"])
        self.assertIn("needspace", result["tikz"])
        self.assertIn(r"\matrix (m)", result["tikz"])

        # Racine de f'(x) = 0 à x = 1.0
        self.assertEqual(len(result["roots"]), 1)
        self.assertAlmostEqual(result["roots"][0], 1.0, places=7)

        # 2 intervalles : ]0; 1[ décroissant, ]1; +oo[ croissant
        intervals = result["intervals"]
        self.assertEqual(len(intervals), 2)

        self.assertEqual(intervals[0]["sign"], "-")
        self.assertEqual(intervals[0]["arrow"], "down")
        self.assertEqual(intervals[1]["sign"], "+")
        self.assertEqual(intervals[1]["arrow"], "up")

        # Valeurs aux bornes et extremum
        # en 0+ -> +oo, f(1) = 1, en +oo -> +oo
        point_vals = result["point_values"]
        self.assertEqual(point_vals[0], r"+\infty")
        self.assertEqual(point_vals[1], "1")
        self.assertEqual(point_vals[2], r"+\infty")

    def test_02_sign_table_trinomial(self) -> None:
        """(b) Tableau de signes d'un trinôme : 2x^2 - 4x - 6 = 2(x - 3)(x + 1)."""
        result = generate_sign_table("2*x**2 - 4*x - 6", var_str="x")

        self.assertTrue(result["verified"])
        self.assertEqual(result["roots"], [-1.0, 3.0])
        # Signe du coefficient dominant (2 > 0) à l'extérieur des racines
        self.assertEqual(result["signs"], ["+", "-", "+"])
        self.assertIn(r"\needspace", result["tikz"])
        self.assertIn(r"\matrix (m)", result["tikz"])

    def test_03_probability_tree_sum_validation(self) -> None:
        """(c) Arbre pondéré à 2 niveaux avec somme des probabilités = 1 à chaque nœud."""
        tree = {
            "root": [
                {
                    "event": "A",
                    "prob": "0.35",
                    "children": [
                        {"event": "B", "prob": "0.40"},
                        {"event": r"\bar{B}", "prob": "0.60"},
                    ],
                },
                {
                    "event": r"\bar{A}",
                    "prob": "0.65",
                    "children": [
                        {"event": "B", "prob": "0.20"},
                        {"event": r"\bar{B}", "prob": "0.80"},
                    ],
                },
            ]
        }
        result = generate_probability_tree(tree)

        self.assertTrue(result["verified"])
        self.assertEqual(result["levels"], 2)
        self.assertEqual(result["branches_count"], 2)
        self.assertIn(r"grow'=right", result["tikz"])
        self.assertIn(r"node[above] {0.35}", result["tikz"])
        self.assertIn(r"node[above] {0.65}", result["tikz"])

    def test_04_strict_math_oracle_rejection(self) -> None:
        """(d) Valeur volontairement fausse injectée : la livraison doit être bloquée avec MathConsistencyError."""
        # Cas 1 : Flèche contradictoire avec le signe de la dérivée
        with self.assertRaises(MathConsistencyError) as ctx_arrow:
            MathOracle.verify_derivative_sign_and_arrow(sign="+", arrow_dir="down")
        self.assertIn("flèche de variation non croissante", str(ctx_arrow.exception))

        # Cas 2 : Valeur d'extremum erronée
        x = sp.Symbol("x")
        with self.assertRaises(MathConsistencyError) as ctx_extr:
            MathOracle.verify_extremum_value(x**2, x, 2, 999.0)
        self.assertIn("écart >", str(ctx_extr.exception))

        # Cas 3 : Arbre de probabilités dont la somme != 1.0
        bad_tree = {
            "root": [
                {"event": "A", "prob": "0.4"},
                {"event": "B", "prob": "0.4"},  # somme 0.8 != 1.0
            ]
        }
        with self.assertRaises(MathConsistencyError) as ctx_tree:
            generate_probability_tree(bad_tree)
        self.assertIn("somme des branches", str(ctx_tree.exception))

        # Cas 4 : Émission de figure.rejected lors d'une tentative incohérente
        events = []
        def sink(name, data):
            events.append((name, data))

        with self.assertRaises(MathConsistencyError):
            generate_math_figure(
                "probability_tree",
                tree_spec=bad_tree,
                event_sink=sink,
            )
        self.assertIn("figure.rejected", [e[0] for e in events])

    def test_05_vertical_asymptote_and_infinite_limits(self) -> None:
        """(e) Fonction avec asymptote verticale et limites infinies : bonnes limites et double barre."""
        # f(x) = 1/(x - 2) sur ]-oo; +oo[, singularité en x = 2
        result = generate_variation_table("1/(x - 2)", var_str="x", domain=(-sp.oo, sp.oo))

        self.assertTrue(result["verified"])
        # Vérification de la double barre dans le TikZ
        self.assertIn(r"\draw[double, thick]", result["tikz"])

        # Limite à gauche de 2 = -oo, limite à droite de 2 = +oo
        point_vals = result["point_values"]
        self.assertEqual(point_vals[0], "0")
        self.assertEqual(point_vals[1], (r"-\infty", r"+\infty"))
        self.assertEqual(point_vals[2], "0")

        # 2 intervalles strictement décroissants
        self.assertEqual(result["intervals"][0]["arrow"], "down")
        self.assertEqual(result["intervals"][1]["arrow"], "down")

    def test_06_template_compilation_zero_errors_and_overfull(self) -> None:
        """(f) Compilation de gabarit TikZ autonome avec Tectonic sans erreur bloquante ni débordement majeur."""
        # Générer un tableau de variations complet
        var_res = generate_variation_table("x - ln(x)/x", var_str="x", domain=(0, sp.oo))
        comp_res = render_math_figure_to_pdf(
            var_res["tikz"],
            output_path="variation_table.pdf",
            workspace=self.workspace,
        )

        self.assertEqual(comp_res["status"], "success")
        self.assertTrue(comp_res.get("zero_error_verified"))
        pdf_path = Path(comp_res["pdf_path"])
        self.assertTrue(pdf_path.is_file())
        self.assertGreater(pdf_path.stat().st_size, 0)

    def test_07_rasterized_inspection_no_empty_page_no_overflow(self) -> None:
        """(g) Inspection visuelle rasterisée : pas de page vide ni de débordement hors marge."""
        # Générer et compiler une courbe avec pgfplots
        curve_res = generate_curve_plot(
            func_str="1/(x - 2)",
            var_str="x",
            x_min=-2.0,
            x_max=6.0,
            y_min=-5.0,
            y_max=5.0,
            asymptotes=[{"kind": "vertical", "value": 2.0}, {"kind": "horizontal", "value": 0.0}],
            tangents=[{"x": 3.0}],
        )
        comp_res = render_math_figure_to_pdf(
            curve_res["tikz"],
            output_path="curve_plot.pdf",
            workspace=self.workspace,
        )

        self.assertEqual(comp_res["status"], "success")
        pdf_path = Path(comp_res["pdf_path"])

        # Rastérisation et analyse géométrique de layout
        layout = PDFRasterizer.inspect_layout(pdf_path, expected_pages=1)
        self.assertTrue(layout["valid"])
        self.assertEqual(layout["page_count"], 1)
        self.assertEqual(len(layout["blank_pages"]), 0)
        self.assertEqual(len(layout["margin_overflows"]), 0)
        self.assertTrue(os.path.isfile(layout["first_page_preview"]))

    def test_08_student_version_blanks(self) -> None:
        """Vérifie que la version élève (student_version=True) masque les réponses par \\phantom."""
        student_res = generate_variation_table("x - ln(x)/x", var_str="x", domain=(0, sp.oo), student_version=True)
        self.assertTrue(student_res["student_version"])
        self.assertIn(r"\phantom", student_res["tikz"])
        # Ne doit pas contenir de flèche de variation dessinée
        self.assertNotIn(r"\draw[->", student_res["tikz"])


if __name__ == "__main__":
    unittest.main()

