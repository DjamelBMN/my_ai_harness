# RÔLE DE CE FICHIER :
# Fournit un navigateur web dynamique (Playwright Chromium headless) avec gestion
# du cycle de vie, extraction de l'arbre DOM, clics, saisies, téléchargements physiques,
# capture d'écran, conformité robots.txt et repli gracieux en mode statique dégradé.

from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import io
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

from tools.search import verify_downloaded_file


class RobotsChecker:
    """Gestionnaire de conformité robots.txt avec mise en cache par domaine."""

    def __init__(self, user_agent: str = "NeoHarnessAI/1.0") -> None:
        self.user_agent = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def get_parser(self, url: str) -> urllib.robotparser.RobotFileParser | None:
        try:
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin in self._cache:
                return self._cache[origin]

            robots_url = f"{origin}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            # Lecture avec court timeout pour ne pas bloquer l'agent
            req = urllib.request.Request(
                robots_url,
                headers={"User-Agent": self.user_agent},
            )
            try:
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    raw_lines = resp.read().decode("utf-8", errors="replace").splitlines()
                    rp.parse(raw_lines)
            except Exception:
                # Si robots.txt inaccessible ou erreur 404, par défaut autoriser
                rp.parse(["User-agent: *", "Allow: /"])

            self._cache[origin] = rp
            return rp
        except Exception:
            return None

    def can_fetch(
        self,
        url: str,
        override: bool = False,
        justification: str = "",
    ) -> tuple[bool, str]:
        """Vérifie si l'accès à l'URL est autorisé par robots.txt."""
        if override:
            return True, f"Accès forcé avec justification : {justification}"

        parser = self.get_parser(url)
        if parser is None:
            return True, "robots.txt non disponible (accès autorisé par défaut)"

        allowed = parser.can_fetch(self.user_agent, url)
        if not allowed:
            return (
                False,
                f"Accès refusé par robots.txt pour l'URL '{url}'. Action bloquée par politique de conformité.",
            )
        return True, "Autorisé par robots.txt"


class _SimpleDOMParser(HTMLParser):
    """Parseur HTML statique de secours pour extraire les éléments cliquables et textuels."""

    def __init__(self) -> None:
        super().__init__()
        self.elements: list[dict[str, Any]] = []
        self.text_parts: list[str] = []
        self._counter = 1
        self._current_tag: str | None = None
        self._current_attrs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        self._current_tag = tag.lower()
        self._current_attrs = attr_dict

        if tag in {"a", "button", "input", "select", "textarea"}:
            eid = f"e_{self._counter}"
            self._counter += 1
            text = attr_dict.get("value") or attr_dict.get("placeholder") or attr_dict.get("aria-label") or ""
            href = attr_dict.get("href", "")
            self.elements.append(
                {
                    "id": eid,
                    "tag": tag,
                    "text": text,
                    "href": href,
                    "name": attr_dict.get("name", ""),
                    "type": attr_dict.get("type", ""),
                }
            )

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.text_parts.append(clean)
            if self.elements and not self.elements[-1]["text"]:
                self.elements[-1]["text"] = clean[:60]


class DynamicBrowser:
    """Navigateur Web dynamique basé sur Playwright Chromium avec repli statique."""

    def __init__(
        self,
        workspace_root: Path | str = "workspace",
        enable_playwright: bool = True,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.downloads_dir = self.workspace_root / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.enable_playwright = enable_playwright
        self.robots_checker = RobotsChecker()

        self._playwright = None
        self._browser = None
        self._contexts: dict[str, Any] = {}
        self._pages: dict[str, Any] = {}
        self._element_maps: dict[str, dict[str, Any]] = {}
        self._playwright_available = False

        if self.enable_playwright:
            self._init_playwright()

    def _init_playwright(self) -> None:
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._playwright_available = True
        except Exception:
            self._playwright_available = False
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
            self._playwright = None
            self._browser = None

    def _get_page(self, session_id: str = "default") -> Any:
        if not self._playwright_available or self._browser is None:
            return None

        if session_id not in self._contexts:
            context = self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                accept_downloads=True,
            )
            page = context.new_page()
            self._contexts[session_id] = context
            self._pages[session_id] = page
            self._element_maps[session_id] = {}

        return self._pages[session_id]

    def navigate(
        self,
        url: str,
        session_id: str = "default",
        override_robots: bool = False,
        justification: str = "",
    ) -> dict[str, Any]:
        """Navigue vers une URL avec vérification robots.txt et extraction de l'arbre DOM."""
        if not url:
            raise ValueError("L'URL ne peut pas être vide.")

        # Vérification robots.txt
        allowed, msg = self.robots_checker.can_fetch(
            url,
            override=override_robots,
            justification=justification,
        )
        if not allowed:
            return {
                "status": "blocked",
                "url": url,
                "error": msg,
                "warnings": [msg],
            }

        page = self._get_page(session_id)
        if page is None:
            return self._navigate_static(url, session_id)

        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status_code = response.status if response else 200
            title = page.title()

            # Extraction structurée des éléments interactifs
            interactive_js = """
            () => {
                const nodes = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                return nodes.slice(0, 100).map((el, i) => {
                    const tag = el.tagName.toLowerCase();
                    const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim();
                    const href = el.getAttribute('href') || '';
                    const name = el.getAttribute('name') || '';
                    const type = el.getAttribute('type') || '';
                    const id = 'e_' + (i + 1);
                    el.setAttribute('data-neoharness-id', id);
                    return { id, tag, text: text.slice(0, 80), href: href.slice(0, 120), name, type };
                });
            }
            """
            elements = page.evaluate(interactive_js)
            elem_map = {item["id"]: item for item in elements}
            self._element_maps[session_id] = elem_map

            # Résumé textuel du DOM
            dom_lines = [f"[PAGE] {title} ({url}) - HTTP {status_code}"]
            for el in elements[:40]:
                href_part = f"-> {el['href']}" if el.get("href") else ""
                dom_lines.append(f"[{el['id']}] <{el['tag']}> {el['text']} {href_part}".strip())

            return {
                "status": "success",
                "mode": "playwright_dynamic",
                "url": page.url,
                "title": title,
                "status_code": status_code,
                "dom_summary": "\n".join(dom_lines),
                "elements_count": len(elements),
                "elements": elements,
                "warnings": [],
            }
        except Exception as err:
            # En cas d'erreur Playwright, repli vers extraction statique
            res = self._navigate_static(url, session_id)
            res["warnings"].append(f"Échec Playwright ({err}), repli statique appliqué.")
            return res

    def _navigate_static(self, url: str, session_id: str = "default") -> dict[str, Any]:
        """Extraction statique dégradée avec avertissement explicite."""
        warnings = ["mode statique dégradé : Playwright indisponible"]
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeoHarnessAI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                content_bytes = resp.read()
                raw_html = content_bytes.decode("utf-8", errors="replace")
                status_code = resp.status

            parser = _SimpleDOMParser()
            parser.feed(raw_html)
            self._element_maps[session_id] = {el["id"]: el for el in parser.elements}

            # Titre
            title_match = re.search(r"<title>(.*?)</title>", raw_html, re.I | re.S)
            title = title_match.group(1).strip() if title_match else "Sans titre"

            dom_lines = [f"[PAGE STATIQUE] {title} ({url}) - HTTP {status_code}"]
            for el in parser.elements[:40]:
                href_part = f"-> {el['href']}" if el.get("href") else ""
                dom_lines.append(f"[{el['id']}] <{el['tag']}> {el['text']} {href_part}".strip())

            return {
                "status": "success",
                "mode": "static_fallback",
                "url": url,
                "title": title,
                "status_code": status_code,
                "dom_summary": "\n".join(dom_lines),
                "elements_count": len(parser.elements),
                "elements": parser.elements,
                "warnings": warnings,
            }
        except Exception as err:
            return {
                "status": "failed",
                "mode": "static_fallback",
                "url": url,
                "error": str(err),
                "warnings": warnings,
            }

    def click_element(self, element_id: str, session_id: str = "default") -> dict[str, Any]:
        """Clique sur un élément identifié par son ID stable."""
        page = self._get_page(session_id)
        if page is None:
            return {
                "status": "failed",
                "error": "L'interaction par clic nécessite le navigateur dynamique actif.",
                "warnings": ["mode statique dégradé : clic impossible"],
            }

        selector = f'[data-neoharness-id="{element_id}"]'
        try:
            page.click(selector, timeout=5000)
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            return {
                "status": "success",
                "action": "click",
                "element_id": element_id,
                "url": page.url,
                "title": page.title(),
            }
        except Exception as err:
            return {
                "status": "failed",
                "action": "click",
                "element_id": element_id,
                "error": str(err),
            }

    def fill_input(self, element_id: str, text: str, session_id: str = "default") -> dict[str, Any]:
        """Remplit un champ texte interactif identifié par son ID."""
        page = self._get_page(session_id)
        if page is None:
            return {
                "status": "failed",
                "error": "La saisie texte nécessite le navigateur dynamique actif.",
                "warnings": ["mode statique dégradé : saisie impossible"],
            }

        selector = f'[data-neoharness-id="{element_id}"]'
        try:
            page.fill(selector, text, timeout=5000)
            return {
                "status": "success",
                "action": "fill",
                "element_id": element_id,
                "text": text,
            }
        except Exception as err:
            return {
                "status": "failed",
                "action": "fill",
                "element_id": element_id,
                "error": str(err),
            }

    def screenshot(
        self,
        target_path: str | None = None,
        session_id: str = "default",
    ) -> dict[str, Any]:
        """Prend une capture d'écran de la page pour inspection multimodale en repli."""
        page = self._get_page(session_id)
        dest = (
            Path(target_path).resolve()
            if target_path
            else self.downloads_dir / f"screenshot_{session_id}_{int(time.time())}.png"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)

        if page is None:
            # En mode statique, génère une image minimale de repli
            dest.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
            return {
                "status": "success",
                "path": str(dest),
                "size_bytes": dest.stat().st_size,
                "warnings": ["mode statique dégradé : capture minimale générée"],
            }

        try:
            page.screenshot(path=str(dest), full_page=False)
            return {
                "status": "success",
                "path": str(dest),
                "size_bytes": dest.stat().st_size,
                "warnings": [],
            }
        except Exception as err:
            return {"status": "failed", "error": str(err)}

    def download_via_browser(
        self,
        url: str,
        target_filename: str | None = None,
        session_id: str = "default",
        task_id: str = "",
    ) -> dict[str, Any]:
        """Télécharge un fichier physiquement avec vérification d'intégrité (taille, hash, magic bytes)."""
        filename = (
            target_filename
            or Path(urllib.parse.urlparse(url).path).name
            or f"download_{int(time.time())}.bin"
        )
        dest_path = self.downloads_dir / filename

        # Téléchargement physique des octets
        raw_bytes: bytes = b""
        page = self._get_page(session_id)
        download_succeeded = False

        if page is not None:
            try:
                with page.expect_download(timeout=10000) as download_info:
                    page.goto(url)
                download = download_info.value
                download.save_as(str(dest_path))
                raw_bytes = dest_path.read_bytes()
                download_succeeded = True
            except Exception:
                download_succeeded = False

        if not download_succeeded:
            # Repli direct HTTP sécurisé
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NeoHarnessAI/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    raw_bytes = resp.read()
                dest_path.write_bytes(raw_bytes)
            except Exception as err:
                return {
                    "status": "failed",
                    "url": url,
                    "error": f"Échec du téléchargement physique : {err}",
                }

        # Vérification physique obligatoire de l'artefact
        verification = verify_downloaded_file(dest_path)
        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        return {
            "status": "success" if verification.get("valid") else "failed",
            "url": url,
            "filename": filename,
            "saved_path": str(dest_path),
            "size_bytes": len(raw_bytes),
            "sha256": sha256,
            "verification": verification,
            "task_id": task_id,
        }

    def close(self, session_id: str | None = None) -> None:
        """Ferme proprement les contextes et le navigateur."""
        if session_id:
            ctx = self._contexts.pop(session_id, None)
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass
            self._pages.pop(session_id, None)
            self._element_maps.pop(session_id, None)
        else:
            for ctx in list(self._contexts.values()):
                try:
                    ctx.close()
                except Exception:
                    pass
            self._contexts.clear()
            self._pages.clear()
            self._element_maps.clear()
            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self._playwright_available = False
