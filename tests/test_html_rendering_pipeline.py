from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.documents import compile_html
from tools.filesystem import WorkspaceFilesystem
from ui.server import NeoHarnessRuntimeBridge, NeoHarnessUIApp


class NeoHarnessHtmlPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="neoharness_html_test_")
        self.workspace_dir = Path(self.temp_dir) / "workspace"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.fs = WorkspaceFilesystem(str(self.workspace_dir))
        self.bridge = NeoHarnessRuntimeBridge(workspace=str(self.workspace_dir))
        self.app = NeoHarnessUIApp(bridge=self.bridge)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_compile_html_valid_page(self) -> None:
        html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Calculateur</title>
    <style>
        body { font-family: sans-serif; background: #fafafa; }
        .box { padding: 20px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Calculateur</h1>
        <button id="btn">Calculer</button>
    </div>
    <script>
        document.getElementById("btn").addEventListener("click", () => {
            console.log("Calcul effectué");
        });
    </script>
</body>
</html>"""
        self.fs.write_file("calc.html", html, overwrite=True)
        res = compile_html("calc.html", filesystem=self.fs)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["type"], "html")
        self.assertEqual(res["scripts_checked"], 1)
        self.assertEqual(res["styles_checked"], 1)
        self.assertGreater(res["bytes"], 100)

    def test_02_compile_html_auto_repairs_missing_structure(self) -> None:
        fragment = "<div class='card'><h2>Fragment</h2><p>Texte court</div>"
        self.fs.write_file("frag.html", fragment, overwrite=True)
        res = compile_html("frag.html", filesystem=self.fs, auto_repair=True)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["repaired"])
        repaired_content = self.fs.read_file("frag.html")
        self.assertIn("<!DOCTYPE html>", repaired_content)
        self.assertIn("</html>", repaired_content)

    def test_03_compile_html_catches_js_syntax_error(self) -> None:
        html = """<!DOCTYPE html>
<html>
<head><title>Erreur JS</title></head>
<body>
    <script>
        function broken( {
            return 42;
        }
    </script>
</body>
</html>"""
        self.fs.write_file("broken.html", html, overwrite=True)
        res = compile_html("broken.html", filesystem=self.fs, auto_repair=False)
        self.assertEqual(res["status"], "error")
        self.assertIn("syntaxe", res["error"].lower())

    def test_04_bridge_compile_workspace_html(self) -> None:
        html = """<!DOCTYPE html>
<html>
<head><title>Test Bridge</title></head>
<body><main>Contenu</main></body>
</html>"""
        self.bridge.write_workspace_file("page.html", html)
        comp = self.bridge.compile_workspace_html("page.html")
        self.assertEqual(comp["status"], "success")
        self.assertEqual(comp["type"], "html")
        self.assertIn("/api/preview/workspace/page.html", comp["preview_url"])

    def test_05_api_compile_html_endpoint(self) -> None:
        payload = {
            "path": "app.html",
            "content": "<!DOCTYPE html><html><head><title>Via API</title></head><body><h1>Bonjour</h1></body></html>"
        }
        status, body = self.app.handle_api_post("/api/files/compile-html", payload)
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["type"], "html")

    def test_06_task_execution_with_html_produces_artifact(self) -> None:
        task_prompt = "Génère une page HTML simple avec un titre et un bouton"
        res = self.bridge.execute_task(task_prompt)
        self.assertIn(res["status"], {"Terminé", "Partiel"})
        # Vérifier qu'un artefact HTML est produit
        artifacts = res.get("preview_artifacts") or []
        html_artifacts = [a for a in artifacts if a.get("type") == "html"]
        self.assertTrue(len(html_artifacts) >= 1)
        self.assertTrue(self.bridge.filesystem.resolve(html_artifacts[0]["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
