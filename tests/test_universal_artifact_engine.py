import os
import shutil
import tempfile
import unittest
import json

from core.artifacts.models import Artifact, ArtifactType, ArtifactStatus
from core.artifacts.handlers import (
    HtmlArtifactHandler,
    LatexArtifactHandler,
    PythonArtifactHandler,
    MarkdownArtifactHandler,
    SvgArtifactHandler,
    MermaidArtifactHandler,
    JsonArtifactHandler,
    CsvArtifactHandler,
    ImageArtifactHandler,
    PdfArtifactHandler,
)
from core.artifacts.engine import UniversalArtifactEngine
from tools.filesystem import WorkspaceFilesystem


class TestUniversalArtifactEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_artifact_engine_")
        self.workspace_dir = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.fs = WorkspaceFilesystem(root=self.workspace_dir)
        self.engine = UniversalArtifactEngine()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. HTML Handler
    # -------------------------------------------------------------------------
    def test_html_handler_success_and_repair(self):
        valid_html = """<!DOCTYPE html>
<html>
<head><title>Test App</title><style>body { font-family: sans-serif; }</style></head>
<body>
  <h1>Interactive Widget</h1>
  <button id="btn">Click me</button>
  <script>
    document.getElementById("btn").addEventListener("click", () => {
      console.log("Clicked");
    });
  </script>
</body>
</html>"""
        self.fs.write_file("app.html", valid_html)
        art = self.engine.process_file("app.html", self.fs)
        self.assertEqual(art.type, ArtifactType.HTML)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertTrue(art.metadata.get("has_js"))
        self.assertTrue(art.metadata.get("has_css"))

        # Auto-repair HTML with missing doctype/tags
        broken_html = "<h1>Simple Header</h1><script>let a = 1; let b = 2;</script>"
        self.fs.write_file("broken.html", broken_html)
        repaired_art = self.engine.process_file("broken.html", self.fs, auto_repair=True)
        self.assertIn(repaired_art.status, {ArtifactStatus.READY, ArtifactStatus.REPAIRED})
        repaired_code = self.fs.read_file("broken.html")
        self.assertIn("<!DOCTYPE html>", repaired_code)
        self.assertIn("</html>", repaired_code)

    # -------------------------------------------------------------------------
    # 2. LaTeX & PDF Handler (Real Tectonic compilation)
    # -------------------------------------------------------------------------
    def test_latex_handler_compilation(self):
        tex_source = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\title{Universal Engine Test}
\author{NeoHarness}
\begin{document}
\maketitle
\section{Verification}
Real compilation via Tectonic without simulation.
\end{document}"""
        self.fs.write_file("test_doc.tex", tex_source)
        art = self.engine.process_file("test_doc.tex", self.fs)
        if art.status == ArtifactStatus.READY:
            self.assertTrue(len(art.output_paths) > 0)
            pdf_path = art.output_paths[0]
            self.assertTrue(self.fs.resolve(pdf_path).exists())
            pdf_bytes = self.fs.read_bytes(pdf_path)
            self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
            self.assertIn(b"%%EOF", pdf_bytes[-1024:])

    # -------------------------------------------------------------------------
    # 3. Python Handler (Real execution & Output file / Plot detection)
    # -------------------------------------------------------------------------
    def test_python_execution_and_plot_generation(self):
        py_code = """
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.figure(figsize=(6, 4))
plt.plot([1, 2, 3, 4], [10, 20, 25, 30], marker='o')
plt.title('Real Test Plot')
plt.grid(True)
plt.savefig('output_plot.png', dpi=100)
plt.close()

print('PLOT_GENERATED_SUCCESSFULLY')
"""
        self.fs.write_file("plot_script.py", py_code)
        art = self.engine.process_file("plot_script.py", self.fs)
        self.assertEqual(art.type, ArtifactType.PYTHON)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertIsNotNone(art.execution)
        self.assertEqual(art.execution.exit_code, 0)
        self.assertIn("PLOT_GENERATED_SUCCESSFULLY", art.execution.stdout)
        # Verify the generated plot was discovered and registered as an output
        self.assertIn("output_plot.png", art.output_paths)
        self.assertTrue(self.fs.resolve("output_plot.png").exists())

    def test_python_syntax_error_detection(self):
        broken_py = "def broken_func(\n  print('missing paren'"
        self.fs.write_file("broken.py", broken_py)
        art = self.engine.process_file("broken.py", self.fs)
        self.assertEqual(art.status, ArtifactStatus.ERROR)
        self.assertIsNotNone(art.error)

    # -------------------------------------------------------------------------
    # 4. SVG Handler (Real XML ElementTree validation & Auto-repair)
    # -------------------------------------------------------------------------
    def test_svg_handler_validation_and_repair(self):
        valid_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
  <circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" />
</svg>"""
        self.fs.write_file("icon.svg", valid_svg)
        art = self.engine.process_file("icon.svg", self.fs)
        self.assertEqual(art.type, ArtifactType.SVG)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertEqual(art.metadata.get("viewBox"), "0 0 100 100")

        # Test repair of unclosed tag in SVG
        broken_svg = '<svg viewBox="0 0 50 50"><circle cx="25" cy="25" r="20">'
        self.fs.write_file("broken.svg", broken_svg)
        repaired_art = self.engine.process_file("broken.svg", self.fs, auto_repair=True)
        self.assertEqual(repaired_art.status, ArtifactStatus.REPAIRED)
        self.assertTrue(repaired_art.auto_repaired)
        repaired_content = self.fs.read_file("broken.svg")
        self.assertIn("</svg>", repaired_content)

    # -------------------------------------------------------------------------
    # 5. Mermaid Handler
    # -------------------------------------------------------------------------
    def test_mermaid_handler(self):
        mermaid_code = """graph TD
  A[Start] --> B{Decide}
  B -->|Yes| C[Proceed]
  B -->|No| D[Halt]
"""
        self.fs.write_file("diagram.mmd", mermaid_code)
        art = self.engine.process_file("diagram.mmd", self.fs)
        self.assertEqual(art.type, ArtifactType.MERMAID)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertEqual(art.metadata.get("diagram_type"), "graph")

    # -------------------------------------------------------------------------
    # 6. JSON Handler
    # -------------------------------------------------------------------------
    def test_json_handler_validation_and_repair(self):
        valid_json = json.dumps({"project": "NeoHarness", "engine": "Universal", "features": 10}, indent=2)
        self.fs.write_file("data.json", valid_json)
        art = self.engine.process_file("data.json", self.fs)
        self.assertEqual(art.type, ArtifactType.JSON)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertEqual(art.metadata.get("items_count"), 3)

        # Test repair of trailing comma via engine process_file
        broken_json = '{"a": 1, "b": 2,}'
        self.fs.write_file("broken.json", broken_json)
        repaired_art = self.engine.process_file("broken.json", self.fs, auto_repair=True)
        self.assertEqual(repaired_art.status, ArtifactStatus.REPAIRED)
        self.assertTrue(repaired_art.auto_repaired)
        parsed = json.loads(self.fs.read_file("broken.json"))
        self.assertEqual(parsed["b"], 2)

    # -------------------------------------------------------------------------
    # 7. CSV Handler
    # -------------------------------------------------------------------------
    def test_csv_handler(self):
        csv_data = """id,nom,score,ville
1,Alice,95,Paris
2,Bob,88,Lyon
3,Charlie,92,Marseille
"""
        self.fs.write_file("scores.csv", csv_data)
        art = self.engine.process_file("scores.csv", self.fs)
        self.assertEqual(art.type, ArtifactType.CSV)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertEqual(art.metadata.get("row_count"), 3)
        self.assertEqual(art.metadata.get("column_count"), 4)
        self.assertEqual(art.metadata.get("delimiter"), ",")

    # -------------------------------------------------------------------------
    # 8. Markdown Handler
    # -------------------------------------------------------------------------
    def test_markdown_handler(self):
        md_text = """# Universal Engine
The math equation is $E = mc^2$ and display:
$$\\int_0^\\infty e^{-x} dx = 1$$
"""
        self.fs.write_file("report.md", md_text)
        art = self.engine.process_file("report.md", self.fs)
        self.assertEqual(art.type, ArtifactType.MARKDOWN)
        self.assertEqual(art.status, ArtifactStatus.READY)
        self.assertTrue(art.metadata.get("has_math"))

    # -------------------------------------------------------------------------
    # 9. Universal Engine Materialization & Version History Rollback
    # -------------------------------------------------------------------------
    def test_engine_extract_and_materialize_blocks(self):
        prompt = "Génère une page web html et un script python de calcul"
        llm_response = """
Here is the interactive component and simulation script:

```html
<!DOCTYPE html>
<html><body><h1>Calculateur</h1></body></html>
```

And the Python script:
```python
x = 42
print(f"Computed {x}")
```
"""
        created = self.engine.extract_and_materialize_blocks(prompt, llm_response, self.fs)
        self.assertEqual(len(created), 2)
        self.assertIn("index.html", created)
        self.assertIn("script.py", created)

    def test_version_history_and_rollback(self):
        v1_code = "print('version 1')\n"
        self.fs.write_file("script.py", v1_code)
        art1 = self.engine.process_file("script.py", self.fs)
        self.assertEqual(len(art1.versions), 1)

        v2_code = "print('version 2')\n"
        self.fs.write_file("script.py", v2_code, overwrite=True)
        art2 = self.engine.process_file("script.py", self.fs)
        self.assertEqual(len(art2.versions), 2)

        v1_id = art2.versions[0].version_id
        rolled_back = self.engine.rollback("script.py", v1_id, self.fs)
        self.assertEqual(rolled_back.status, ArtifactStatus.READY)
        current_content = self.fs.read_file("script.py")
        self.assertEqual(current_content, v1_code)


if __name__ == "__main__":
    unittest.main()

