from __future__ import annotations

import http.server
from pathlib import Path
import socketserver
import tempfile
import threading
import time
import unittest

from tools.browser import DynamicBrowser, RobotsChecker


class MockHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/robots.txt":
            content = b"User-agent: *\nDisallow: /blocked/\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/index.html":
            html_content = b"""<!DOCTYPE html>
<html>
<head><title>Page Test NeoHarness</title></head>
<body>
    <h1>Bienvenue</h1>
    <a href="/download/sample.pdf">Telecharger PDF</a>
    <input type="text" name="username" placeholder="Entrez votre nom" value="User42" />
    <button id="btn_submit">Valider</button>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)
        elif self.path == "/blocked/secret.html":
            content = b"<html><body>Page Secrete Bloquee</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/download/sample.pdf":
            # Octets conformes magic bytes PDF (%PDF-1.4)
            pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", 'attachment; filename="sample.pdf"')
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # Supprime les logs verbeux de SimpleHTTPRequestHandler durant les tests
        pass


class TestDynamicBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Démarre un serveur HTTP local sur un port éphémère
        cls.server = socketserver.TCPServer(("127.0.0.1", 0), MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        self.browser = DynamicBrowser(workspace_root=self.workspace, enable_playwright=True)

    def tearDown(self) -> None:
        self.browser.close()
        self.temp_dir.cleanup()

    def test_01_graceful_degradation_when_playwright_disabled(self) -> None:
        """Dégradation gracieuse en mode statique quand Playwright n'est pas actif."""
        static_browser = DynamicBrowser(workspace_root=self.workspace, enable_playwright=False)
        try:
            res = static_browser.navigate(f"{self.base_url}/index.html")
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["mode"], "static_fallback")
            self.assertIn("mode statique dégradé : Playwright indisponible", res["warnings"][0])
            self.assertEqual(res["title"], "Page Test NeoHarness")
            self.assertGreaterEqual(res["elements_count"], 2)
        finally:
            static_browser.close()

    def test_02_structured_dom_extraction_on_local_page(self) -> None:
        """Extraction DOM structurée sur une page HTML servie localement."""
        res = self.browser.navigate(f"{self.base_url}/index.html")
        self.assertEqual(res["status"], "success")
        self.assertIn("Page Test NeoHarness", res["title"])

        # Vérifie les éléments interactifs extraits
        elements = res["elements"]
        tags = [e["tag"] for e in elements]
        self.assertIn("a", tags)
        self.assertIn("input", tags)
        self.assertIn("button", tags)

        # Vérifie le résumé DOM
        self.assertIn("sample.pdf", res["dom_summary"])

    def test_03_respect_of_robots_txt_blocking(self) -> None:
        """Respect de robots.txt avec refus explicite et message compréhensible."""
        blocked_url = f"{self.base_url}/blocked/secret.html"
        res = self.browser.navigate(blocked_url)

        self.assertEqual(res["status"], "blocked")
        self.assertIn("Accès refusé par robots.txt", res["error"])

        # Forçage autorisé avec justification tracée
        res_forced = self.browser.navigate(
            blocked_url,
            override_robots=True,
            justification="Inspection forensique autorisée",
        )
        self.assertEqual(res_forced["status"], "success")

    def test_04_physical_download_with_integrity_and_magic_bytes(self) -> None:
        """Téléchargement physique avec vérification d'intégrité (magic bytes, SHA-256)."""
        download_url = f"{self.base_url}/download/sample.pdf"
        dl_res = self.browser.download_via_browser(
            url=download_url,
            target_filename="sample_test.pdf",
            task_id="task-browser-01",
        )
        self.assertEqual(dl_res["status"], "success")
        self.assertTrue(Path(dl_res["saved_path"]).exists())
        self.assertGreater(dl_res["size_bytes"], 0)
        self.assertTrue(dl_res["sha256"])

        # Vérification physique des magic bytes
        verif = dl_res["verification"]
        self.assertTrue(verif["valid"])
        self.assertEqual(verif["format"], "pdf")


if __name__ == "__main__":
    unittest.main()
