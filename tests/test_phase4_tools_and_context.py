import unittest
import tempfile
from pathlib import Path

from tools.editor import edit_file, EditAmbiguityError, EditSyntaxError
from tools.viewer import view_file
from tools.code_search import search_code
from tools.terminal import truncate_output, execute_bounded_command
from core.context import Context
from core.context_manager import ContextManager
from tools.filesystem import WorkspaceFilesystem


class TestPhase4ToolsAndContext(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fs = WorkspaceFilesystem(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- 1. Éditeur ciblé : Remplacement unique, ambiguïté et syntax error ---
    def test_01_edit_file_unique_replacement_success(self):
        """edit_file remplace une occurrence unique avec validation de syntaxe."""
        f_path = self.fs.resolve("app.py")
        f_path.write_text("def greet():\n    return 'hello'\n", encoding="utf-8")

        res = edit_file(
            "app.py",
            old_str="return 'hello'",
            new_str="return 'bonjour'",
            filesystem=self.fs,
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("return 'bonjour'", f_path.read_text(encoding="utf-8"))

    def test_02_edit_file_ambiguous_string_rejected(self):
        """edit_file refuse de modifier une chaîne ambiguë présente plusieurs fois."""
        f_path = self.fs.resolve("dup.py")
        f_path.write_text("x = 10\nx = 10\n", encoding="utf-8")

        with self.assertRaises(EditAmbiguityError) as ctx:
            edit_file(
                "dup.py",
                old_str="x = 10",
                new_str="x = 20",
                filesystem=self.fs,
            )
        self.assertIn("apparaît 2 fois", str(ctx.exception))

    def test_03_edit_file_syntax_error_rollback(self):
        """edit_file détecte une SyntaxError Python et annule la modification."""
        f_path = self.fs.resolve("buggy.py")
        initial_code = "def valid():\n    return 42\n"
        f_path.write_text(initial_code, encoding="utf-8")

        with self.assertRaises(EditSyntaxError) as ctx:
            edit_file(
                "buggy.py",
                old_str="return 42",
                new_str="return def invalid",
                filesystem=self.fs,
            )
        self.assertIn("erreur de syntaxe", str(ctx.exception).lower())
        # Le fichier n'a pas été corrompu
        self.assertEqual(f_path.read_text(encoding="utf-8"), initial_code)

    # --- 2. Visualiseur fenêtré (view_file) ---
    def test_04_view_file_bounded_pagination(self):
        """view_file pagine correctement sans saturer le contexte."""
        f_path = self.fs.resolve("big_file.txt")
        lines = [f"Ligne {i}" for i in range(1, 501)]
        f_path.write_text("\n".join(lines), encoding="utf-8")

        # Fenêtre bornée de 20 lignes
        view = view_file("big_file.txt", start_line=10, end_line=29, filesystem=self.fs)
        self.assertEqual(view["status"], "success")
        self.assertEqual(view["lines_returned"], 20)
        self.assertIn("0010: Ligne 10", view["content"])
        self.assertIn("0029: Ligne 29", view["content"])
        self.assertNotIn("0030: Ligne 30", view["content"])

    # --- 3. Recherche de code ciblée (search_code) ---
    def test_05_search_code_ignores_git_and_node_modules(self):
        """search_code ignore strictement les répertoires parasites."""
        # Fichier légitime
        (self.fs.resolve("src")).mkdir(parents=True, exist_ok=True)
        (self.fs.resolve("src/main.py")).write_text("SECRET_TOKEN = 'valid'\n", encoding="utf-8")

        # Fichiers dans des répertoires parasites (créés directement sur le système de fichiers)
        git_dir = Path(self.temp_dir.name) / ".git"
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / "dummy.txt").write_text("SECRET_TOKEN = 'git_internal'\n", encoding="utf-8")

        node_dir = Path(self.temp_dir.name) / "node_modules" / "pkg"
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "index.js").write_text("SECRET_TOKEN = 'node'\n", encoding="utf-8")

        res = search_code("SECRET_TOKEN", filesystem=self.fs)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["results_count"], 1)
        self.assertEqual(res["results"][0]["file"], "src/main.py")

    # --- 4. Exécuteur borné et tronquage intelligent ---
    def test_06_truncate_output_head_and_tail(self):
        """truncate_output préserve 50 lignes en tête et 50 en queue."""
        long_output = "\n".join(f"Ligne {i}" for i in range(1, 201))
        truncated = truncate_output(long_output, head_lines=50, tail_lines=50)

        self.assertIn("Ligne 1", truncated)
        self.assertIn("Ligne 50", truncated)
        self.assertIn("100 lignes tronquées", truncated)
        self.assertIn("Ligne 151", truncated)
        self.assertIn("Ligne 200", truncated)

    # --- 5. Compaction de contexte sémantique ---
    def test_07_context_manager_preserves_facts_and_decisions(self):
        """ContextManager préserve les décisions validées et synthétise les anciens tours."""
        ctx = Context()
        ctx.history = [
            f"Tour {i} : Recherche d'informations préliminaires et exploration des pistes"
            for i in range(1, 15)
        ]

        class FakeTaskContext:
            decisions = ["Architecture MVC retenue", "Base de données SQLite validée"]
            constraints = ["Temps de réponse < 200ms"]

        ctx.task_context = FakeTaskContext()
        mgr = ContextManager(max_items=4, max_characters=1500)
        compacted = mgr.compact(ctx)

        # Les décisions et contraintes sont préservées
        self.assertTrue(any("DÉCISIONS VALIDÉES" in h for h in compacted.history))
        self.assertTrue(any("CONTRAINTES IMMUABLES" in h for h in compacted.history))
        # Les anciens tours sont synthétisés
        self.assertTrue(any("SYNTHÈSE TOURS ANCIENS" in h for h in compacted.history))


if __name__ == "__main__":
    unittest.main()
