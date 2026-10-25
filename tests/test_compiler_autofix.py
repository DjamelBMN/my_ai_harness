from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.compiler import AutonomousCompiler, parse_compiler_log, fix_compiler_issue, CompilerIssue


class TestCompilerAutofix(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.compiler = AutonomousCompiler(workspace=self.workspace, max_attempts=5)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_missing_brace_autofix(self) -> None:
        """(a) Correction automatique d'une accolade fermante manquante."""
        tex_file = self.workspace / "doc_brace.tex"
        tex_content = r"""\documentclass{article}
\begin{document}
Voici un texte avec \textbf{du gras non fermé
et une seconde ligne.
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        res = self.compiler.compile(tex_file, auto_fix=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(Path(res["pdf_path"]).exists())
        self.assertGreater(res["size_bytes"], 0)
        self.assertTrue(res["zero_error_verified"])

        # Vérifier que le fichier source a été réparé proprement
        repaired = tex_file.read_text(encoding="utf-8")
        self.assertIn("}", repaired)

    def test_02_unescaped_ampersand_autofix(self) -> None:
        """(b) Correction automatique d'un caractère '&' non échappé."""
        tex_file = self.workspace / "doc_amp.tex"
        tex_content = r"""\documentclass{article}
\begin{document}
Rapport financier : Chiffre d'affaires & Bénéfice net en hausse.
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        res = self.compiler.compile(tex_file, auto_fix=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(Path(res["pdf_path"]).exists())
        self.assertTrue(res["zero_error_verified"])

        repaired = tex_file.read_text(encoding="utf-8")
        self.assertIn(r"\&", repaired)

    def test_03_nonexistent_package_autofix(self) -> None:
        """(c) Retrait automatique d'un package inexistant."""
        tex_file = self.workspace / "doc_pkg.tex"
        tex_content = r"""\documentclass{article}
\usepackage{pkgTotalementInexistant9999}
\begin{document}
Document sans le package manquant.
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        res = self.compiler.compile(tex_file, auto_fix=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(Path(res["pdf_path"]).exists())
        self.assertTrue(res["zero_error_verified"])

        repaired = tex_file.read_text(encoding="utf-8")
        self.assertIn("autofix: retiré", repaired)

    def test_04_unfixable_error_stops_cleanly_incomplete(self) -> None:
        """(d) Une erreur impossible à résoudre s'arrête au plafond avec statut 'incomplete'."""
        short_compiler = AutonomousCompiler(workspace=self.workspace, max_attempts=2)
        tex_file = self.workspace / "doc_broken.tex"
        # Fichier avec macro corrompue répétitive
        tex_content = r"""\documentclass{article}
\begin{document}
\csname badsyntax 12345\endcsname
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        res = short_compiler.compile(tex_file, auto_fix=False)
        self.assertEqual(res["status"], "incomplete")
        self.assertIsNone(res["pdf_path"])
        self.assertIn("remaining_issues", res)

    def test_05_cascade_error_single_root_cause(self) -> None:
        """(e) Erreurs en cascade résolues en traitant la cause racine primaire."""
        tex_file = self.workspace / "doc_cascade.tex"
        # Une seule accolade non fermée génère plusieurs erreurs TeX consécutives
        tex_content = r"""\documentclass{article}
\begin{document}
\section{Titre}
\textbf{Premier texte sans fermeture
\section{Autre section}
Paragraphe normal.
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        res = self.compiler.compile(tex_file, auto_fix=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["zero_error_verified"])

    def test_06_worsening_error_triggers_rollback(self) -> None:
        """(f) Une correction qui aggrave le nombre d'erreurs déclenche un rollback."""
        events: list[tuple[str, dict]] = []

        def capture_event(name: str, data: dict) -> None:
            events.append((name, data))

        tracked_compiler = AutonomousCompiler(
            workspace=self.workspace,
            max_attempts=3,
            event_sink=capture_event,
        )

        tex_file = self.workspace / "doc_rollback.tex"
        tex_content = r"""\documentclass{article}
\begin{document}
Tom & Jerry
\end{document}
"""
        tex_file.write_text(tex_content, encoding="utf-8")

        # Mock build qui simule une augmentation des erreurs après une mauvaise correction
        orig_build = tracked_compiler._run_single_build

        def mocked_build(p: Path, src: str, timeout: float = 30.0) -> tuple[bool, bytes | None, str]:
            if "badcmd" in src:
                fake_log = "error: doc_rollback.tex:10: Bad 1\nerror: doc_rollback.tex:11: Bad 2\nerror: doc_rollback.tex:12: Bad 3\n"
                return False, None, fake_log
            return orig_build(p, src, timeout)

        tracked_compiler._run_single_build = mocked_build

        original_fix = fix_compiler_issue

        def worsening_fix(src: str, issue: CompilerIssue, strategy: int = 1) -> tuple[str, str]:
            if strategy == 1:
                # Injection d'erreurs supplémentaires lors de la première passe
                return src.replace("Tom & Jerry", "Tom & Jerry\n\\badcmd1\n\\badcmd2"), "Correction aggravante simulée"
            return original_fix(src, issue, strategy)

        import tools.compiler as comp_mod
        comp_mod.fix_compiler_issue = worsening_fix

        try:
            res = tracked_compiler.compile(tex_file, auto_fix=True)
            # Vérifier qu'un événement compile.rollback a bien été émis
            rollback_events = [ev for ev in events if ev[0] == "compile.rollback"]
            self.assertGreaterEqual(len(rollback_events), 1)
        finally:
            comp_mod.fix_compiler_issue = original_fix


if __name__ == "__main__":
    unittest.main()
