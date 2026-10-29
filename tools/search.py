# RÔLE DE CE FICHIER :
# Exécute les recherches locales dans le workspace et la recherche Internet réelle
# (HTTP/HTTPS via Bing, DuckDuckGo Lite, Google News RSS et l'API Wikipédia).
# Aucune source n'est jamais simulée ou inventée en cas d'échec réseau.
# Établit la chaîne de provenance infalsifiable pour tout artefact téléchargé.

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import logging
import os
from pathlib import Path
import re
import time
import unicodedata
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from tools.filesystem import WORKSPACE_ROOT, WorkspaceFilesystem

# pypdf écrit des avertissements sans gravité ("incorrect startxref pointer", ...)
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
WIKI_USER_AGENT = "NeoHarnessAI/1.0 (Local Agentic Operating Environment)"

_DIRECT_FILE_EXTS = (".pdf", ".docx", ".zip", ".png", ".jpg")
_SKIP_SUBPAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js",
                      ".zip", ".docx", ".pdf", ".xlsx", ".ico", ".woff", ".woff2")


# ---------------------------------------------------------------------------
# Utilitaires texte
# ---------------------------------------------------------------------------

def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    no_scripts = re.sub(r"<(script|style|noscript|svg|head)[^>]*>[\s\S]*?</\1>", " ", raw, flags=re.I)
    without_tags = re.sub(r"<[^>]+>", " ", no_scripts)
    unescaped = html.unescape(without_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def _norm_txt(s: str) -> str:
    """Minuscules sans accents, pour comparer des textes de façon robuste."""
    return "".join(
        c for c in unicodedata.normalize("NFD", (s or "").lower())
        if unicodedata.category(c) != "Mn"
    )


_SEM_STOP = {
    "cours", "pdf", "telecharge", "telecharger", "download", "filetype", "format",
    "sur", "les", "des", "une", "pour", "avec", "dans", "cette", "mais", "moi",
    "fichier", "document", "internet", "site", "http", "https", "www",
}


def _query_stems(query: str, min_len: int = 4) -> list[str]:
    """Mots-clés significatifs d'une requête (sans accents, sans pluriel simple)."""
    stems: list[str] = []
    for w in re.findall(r"[a-z0-9]{%d,}" % min_len, _norm_txt(query)):
        if w in _SEM_STOP:
            continue
        stem = w[:-1] if (w.endswith("s") and len(w) > 4) else w
        if stem not in stems:
            stems.append(stem)
    return stems


def _relevant(dl: dict[str, Any], query: str) -> bool:
    """Le contenu et l'URL d'un document (ou d'un résultat de recherche) doivent
    contenir les mots-clés de la requête. Ne regarde pas le nom du fichier local."""
    stems = _query_stems(query)
    if not stems:
        return True
    prov = dl.get("provenance") or {}
    hay = _norm_txt(" ".join([dl.get("url", ""), prov.get("content_excerpt", "")]))
    need = len(stems) if len(stems) <= 2 else (len(stems) + 1) // 2
    return sum(1 for k in stems if k in hay) >= need


def _clean_download_query(query: str) -> str:
    """Retire les verbes de commande ('télécharge...') et 'au format pdf' d'une requête."""
    text = " ".join((query or "").strip().split())
    cleaned = re.sub(
        r"(?i)^(?:/research\s+)?(?:télécharge|telecharge|télécharger|telecharger|récupère|recupere|trouve|cherche|recherche)"
        r"(?:-moi)?\s+(?:sur\s+(?:internet|le\s+web)\s+)?",
        "",
        text,
    )
    cleaned = re.sub(r"(?i)\b(?:au\s+format|en\s+format|format)\s+pdf\b", " pdf", cleaned)
    cleaned = re.sub(r"(?i)^(?:(?:un|une|le|la|les|des)\s+|l')", "", cleaned)
    return " ".join(cleaned.split()) or text


# ---------------------------------------------------------------------------
# Moteurs de recherche
# ---------------------------------------------------------------------------

def _unwrap_ddg_url(href: str) -> str:
    href = html.unescape(href.strip())
    if "uddg=" in href:
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return qs["uddg"][0]
        raw_target = href.split("uddg=", 1)[1].split("&", 1)[0]
        return urllib.parse.unquote(raw_target)
    if href.startswith("//"):
        return "https:" + href
    return href


def _unwrap_bing_url(href: str) -> str:
    """Décode les redirections Bing (&u=a1<base64>) vers l'URL finale directe."""
    href = html.unescape(href.strip())
    if "&u=a1" in href or "?u=a1" in href:
        try:
            m = re.search(r"[?&]u=a1([a-zA-Z0-9_-]+)", href)
            if m:
                raw_b64 = m.group(1)
                padding = len(raw_b64) % 4
                if padding:
                    raw_b64 += "=" * (4 - padding)
                decoded = base64.urlsafe_b64decode(raw_b64).decode("utf-8", errors="ignore")
                if decoded.startswith(("http://", "https://")):
                    return decoded
        except Exception:
            pass
    return href


def _search_bing(query: str, timeout: float = 6.0) -> list[dict[str, Any]]:
    """Recherche via Bing HTML pour un accès direct et non bloqué aux annales et documents."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/search?q={encoded}&setlang=fr-FR"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        page = resp.read().decode("utf-8", errors="replace")

    results: list[dict[str, Any]] = []
    items = re.findall(
        r'<li[^>]*class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>.*?<h2><a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>',
        page,
        re.S,
    )
    for raw_href, raw_title, raw_snippet in items:
        final_url = _unwrap_bing_url(raw_href)
        if not final_url.startswith(("http://", "https://")):
            continue
        title = _clean_html(raw_title)
        snippet = _clean_html(raw_snippet)
        if not title:
            continue
        domain = urllib.parse.urlparse(final_url).netloc
        results.append({
            "title": title,
            "url": final_url,
            "snippet": snippet,
            "source": domain or "Bing",
            "published_at": "",
            "provider": "bing",
        })
    return results

def _search_ddgs(query: str, timeout: float = 8.0, max_results: int = 8) -> list[dict[str, Any]]:
    """Recherche via la bibliothèque ddgs (sans clé API). Les liens publicitaires sont écartés."""
    from ddgs import DDGS  # ImportError remontée volontairement : visible dans errors

    ad_markers = ("bing.com/aclick", "duckduckgo.com/y.js", "/aclick?")
    results: list[dict[str, Any]] = []
    for item in DDGS(timeout=int(timeout)).text(query, region="fr-fr", max_results=max_results + 3):
        url = str(item.get("href") or "").strip()
        title = _clean_html(str(item.get("title") or ""))
        if not url.startswith(("http://", "https://")) or not title:
            continue
        if any(marker in url for marker in ad_markers):
            continue
        results.append({
            "title": title,
            "url": url,
            "snippet": _clean_html(str(item.get("body") or "")),
            "source": urllib.parse.urlparse(url).netloc or "Web",
            "published_at": "",
            "provider": "ddgs",
        })
        if len(results) >= max_results:
            break
    return results

def _search_duckduckgo_lite(query: str, timeout: float = 8.0) -> list[dict[str, Any]]:
    body = urllib.parse.urlencode({"q": query}).encode("utf-8")
    request = urllib.request.Request(
        "https://lite.duckduckgo.com/lite/",
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Referer": "https://lite.duckduckgo.com/",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read().decode("utf-8", errors="replace")

    links = re.findall(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\']result-link["\'][^>]*>(.*?)</a>',
        page,
        flags=re.S | re.I,
    )
    if not links:
        links = re.findall(
            r'<a[^>]+class=["\']result-link["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            page,
            flags=re.S | re.I,
        )
    snippets = re.findall(
        r'<td[^>]+class=["\']result-snippet["\'][^>]*>(.*?)</td>',
        page,
        flags=re.S | re.I,
    )

    results: list[dict[str, Any]] = []
    for index, (raw_href, raw_title) in enumerate(links):
        url = _unwrap_ddg_url(raw_href)
        if not url.startswith(("https://", "http://")):
            continue
        if "duckduckgo.com/y.js" in url:
            continue
        title = _clean_html(raw_title)
        snippet = _clean_html(snippets[index]) if index < len(snippets) else ""
        domain = urllib.parse.urlparse(url).netloc
        if not title:
            continue
        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "source": domain or "Web",
            "published_at": "",
            "provider": "duckduckgo_lite",
        })
    return results


def _search_google_news_rss(query: str, timeout: float = 8.0) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=fr&gl=FR&ceid=FR:fr"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        xml_bytes = response.read()

    root = ET.fromstring(xml_bytes)
    results: list[dict[str, Any]] = []
    for item in root.findall("./channel/item"):
        title = _clean_html(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        description = _clean_html(item.findtext("description") or "")
        pub_date = (item.findtext("pubDate") or "").strip()
        source_el = item.find("source")
        source_name = (
            _clean_html(source_el.text or "")
            if source_el is not None and source_el.text
            else ""
        )
        source_url = (
            source_el.attrib.get("url", "").strip()
            if source_el is not None
            else ""
        )
        if not title or not link.startswith(("https://", "http://")):
            continue
        results.append({
            "title": title,
            "url": link,
            "snippet": description or title,
            "source": source_name or urllib.parse.urlparse(source_url or link).netloc or "Google News",
            "published_at": pub_date,
            "provider": "google_news_rss",
        })
    return results


def _search_wikipedia_fr(query: str, timeout: float = 8.0) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    url = (
        "https://fr.wikipedia.org/w/api.php"
        f"?action=query&list=search&utf8=1&format=json&srlimit=3&srsearch={encoded}"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": WIKI_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))

    search_items = payload.get("query", {}).get("search", [])
    results: list[dict[str, Any]] = []
    for item in search_items:
        raw_title = str(item.get("title") or "").strip()
        if not raw_title:
            continue
        article_url = "https://fr.wikipedia.org/wiki/" + urllib.parse.quote(
            raw_title.replace(" ", "_")
        )
        snippet = _clean_html(str(item.get("snippet") or ""))
        timestamp = str(item.get("timestamp") or "").strip()
        results.append({
            "title": f"{raw_title} — Wikipédia",
            "url": article_url,
            "snippet": snippet,
            "source": "fr.wikipedia.org",
            "published_at": timestamp,
            "provider": "wikipedia_api",
        })
    return results


def _extract_search_keywords(raw_query: str) -> str:
    """Nettoie les formules conversationnelles autour d'une requête de recherche Web."""
    text = " ".join(raw_query.strip().split())
    patterns = [
        r"^(?:/research\s+)?(?:recherche|cherche|trouve|chercher|rechercher)\s+(?:sur\s+(?:internet|le\s+web)|en\s+ligne)\s+",
        r"^(?:/research\s+)?(?:fais|effectue)\s+une\s+recherche\s+(?:web|internet)\s+(?:sur\s+)?",
        r"^(?:/research\s+)?(?:trouve|cherche|recherche)\s+",
        r"^(?:les\s+|des\s+|le\s+|la\s+|un\s+|une\s+)?",
    ]
    text = re.sub(r"(?i)(?:Copier|Modifier|Régénérer|Regenerer|NeoHarness AI|Mission non terminée[^\r\n]*)\s*", " ", text)

    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.I).strip()
    cleaned = re.sub(r";\s*ensuite.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r",\s*(?:ensuite|télécharge|telecharge|récupère|recupere|enregistre|vérifie|verifie|affiche|regarde).*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+(?:et\s+)?(?:télécharge|telecharge|récupère|recupere|enregistre|vérifie|verifie|affiche|résume|resume|synthétise|donne).*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+dans\s+le\s+workspace.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+dans\s+l'aperçu.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+dans\s+le\s+panneau.*$", "", cleaned, flags=re.I)
    cleaned = cleaned.strip(" .?!;:,")
    if re.match(r"^sujet", cleaned, flags=re.I) and "bac" in cleaned.casefold():
        cleaned = re.sub(r"^sujet\s*(?:\d+)?\s*(?:de\s+)?", "", cleaned, flags=re.I).strip()
        cleaned = f"bac {cleaned} sujet"
    return cleaned or text


# ---------------------------------------------------------------------------
# Extraction de liens
# ---------------------------------------------------------------------------

def _extract_download_links(html_text: str, base_url: str) -> list[dict[str, str]]:
    """Extrait et résout tous les liens de téléchargement de documents présents dans un HTML."""
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    link_pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\'#\s>]+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    doc_extensions = {".pdf", ".docx", ".doc", ".xlsx", ".zip", ".tex", ".png", ".jpg", ".jpeg", ".csv"}
    doc_keywords = {"télécharger", "telecharger", "download", "sujet", "corrigé", "corrige", "énoncé", "enonce", "annale", "pdf", "officiel"}

    for match in link_pattern.finditer(html_text):
        raw_href = match.group(1).strip()
        raw_anchor = _clean_html(match.group(2)).strip()
        if not raw_href or raw_href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        abs_url = urllib.parse.urljoin(base_url, raw_href)
        if not abs_url.startswith(("http://", "https://")) or abs_url in seen:
            continue

        parsed = urllib.parse.urlparse(abs_url)
        path_lower = parsed.path.lower()
        anchor_lower = raw_anchor.lower()
        has_doc_ext = any(path_lower.endswith(ext) for ext in doc_extensions)
        has_doc_kw = any(kw in anchor_lower or kw in path_lower for kw in doc_keywords)

        if has_doc_ext or has_doc_kw:
            seen.add(abs_url)
            filename = Path(parsed.path).name or "document.pdf"
            links.append({
                "url": abs_url,
                "text": raw_anchor or filename,
                "filename": filename,
                "is_direct_doc": has_doc_ext,
            })
    return links


def _extract_all_links(html_text: str, base_url: str, limit: int = 400) -> list[dict[str, str]]:
    """Tous les liens <a> d'une page (utile pour explorer les sous-pages d'un cours)."""
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    pattern = re.compile(r'<a\s+[^>]*href=["\']([^"\'\s>]+)["\'][^>]*>(.*?)</a>', re.I | re.S)
    for match in pattern.finditer(html_text):
        href = match.group(1).strip()
        if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = urllib.parse.urldefrag(urllib.parse.urljoin(base_url, href))[0]
        if not abs_url.startswith(("http://", "https://")) or abs_url in seen:
            continue
        seen.add(abs_url)
        links.append({"url": abs_url, "text": _clean_html(match.group(2)).strip()})
        if len(links) >= limit:
            break
    return links


# ---------------------------------------------------------------------------
# Vérification et téléchargement
# ---------------------------------------------------------------------------

def verify_downloaded_file(file_path: Path | str) -> dict[str, Any]:
    """Vérifie physiquement l'existence, la taille, l'intégrité binaire et le format d'un fichier téléchargé."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return {
            "valid": False,
            "exists": False,
            "size_bytes": 0,
            "format": "unknown",
            "sha256": "",
            "error": f"Fichier introuvable sur le disque : {file_path}",
        }

    size = p.stat().st_size
    if size <= 0:
        return {
            "valid": False,
            "exists": True,
            "size_bytes": 0,
            "format": "empty",
            "sha256": "",
            "error": "Le fichier téléchargé est vide (0 octet).",
        }

    with open(p, "rb") as f:
        header = f.read(512)
        f.seek(0)
        sha256_hash = hashlib.sha256(f.read()).hexdigest()

    fmt = "unknown"
    is_valid_header = False
    if header.startswith(b"%PDF-"):
        fmt = "pdf"
        is_valid_header = True
    elif header.startswith(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])):
        fmt = "png"
        is_valid_header = True
    elif header.startswith(bytes([0xff, 0xd8, 0xff])):
        fmt = "jpeg"
        is_valid_header = True
    elif header.startswith(bytes([0x50, 0x4b, 0x03, 0x04])):
        fmt = "zip_or_docx"
        is_valid_header = True
    else:
        try:
            header.decode("utf-8")
            fmt = "text"
            is_valid_header = True
        except Exception:
            fmt = "binary"
            is_valid_header = size > 50

    return {
        "valid": is_valid_header,
        "exists": True,
        "size_bytes": size,
        "format": fmt,
        "sha256": sha256_hash,
        "summary": f"Fichier {fmt.upper()} authentifié ({size} octets) sur le disque.",
    }


def _extract_pdf_info(raw_bytes: bytes) -> tuple[str, int]:
    """Extrait (extrait de texte des premières pages, nombre de pages) d'un PDF en mémoire."""
    pages = max(1, len(re.findall(rb"/Type\s*/Page\b", raw_bytes)))
    excerpt = ""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = len(reader.pages)
        parts: list[str] = []
        for page in reader.pages[:3]:
            parts.append(page.extract_text() or "")
            if sum(len(p) for p in parts) >= 4000:
                break
        excerpt = "\n".join(parts)[:4000]
    except Exception:
        pass
    return excerpt, pages


def download_resource(
    url: str,
    output_path: str = "",
    workspace: str | Path = WORKSPACE_ROOT,
    timeout: float = 15.0,
    attempted_sources: list[dict[str, Any]] | None = None,
    task_id: str = "",
    relevance_query: str = "",
    reject_html: bool = False,
    context_hint: str = "",
) -> dict[str, Any]:
    """Télécharge physiquement une ressource distante dans le workspace, vérifie son intégrité
    et enregistre sa chaîne de provenance.

    - relevance_query : si fourni, le document n'est PAS écrit sur le disque (ni enregistré dans
      le ledger de provenance) quand son contenu/URL ne correspond pas à la requête.
    - reject_html : refuse une réponse HTML (page Web) quand on attend un vrai document.
    - context_hint : texte du lien/page parente, utilisé seulement si aucun texte n'est extractible.
    """
    clean_url = (url or "").strip()
    if not clean_url.startswith(("http://", "https://")):
        raise ValueError(f"URL de téléchargement invalide : {url!r}")

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/octet-stream,text/html,application/xhtml+xml,*/*",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status_code = resp.status
        content_type = str(resp.headers.get("content-type") or "").lower()
        raw_bytes = resp.read()

    # Suivi automatique des redirections JavaScript (ex: ANTS window.location.href) ou meta refresh
    if raw_bytes.strip().startswith(b"<") and (b"window.location.href" in raw_bytes or b"http-equiv" in raw_bytes.lower()):
        decoded_head = raw_bytes[:4000].decode("utf-8", errors="replace")
        redir_match = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", decoded_head, re.I)
        if not redir_match:
            redir_match = re.search(r'url=([^"\'>\s]+)', decoded_head, re.I)
        if redir_match:
            redir_url = urllib.parse.urljoin(clean_url, redir_match.group(1))
            try:
                req_redir = urllib.request.Request(
                    redir_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/pdf,application/octet-stream,*/*",
                        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                        "Referer": clean_url,
                    },
                )
                with urllib.request.urlopen(req_redir, timeout=timeout) as resp_redir:
                    redir_bytes = resp_redir.read()
                    if redir_bytes.startswith(b"%PDF-") or len(redir_bytes) > len(raw_bytes):
                        raw_bytes = redir_bytes
                        clean_url = redir_url
                        status_code = resp_redir.status
                        content_type = str(resp_redir.headers.get("content-type") or "").lower()
            except Exception:
                pass

    is_pdf = raw_bytes.startswith(b"%PDF-")
    head_low = raw_bytes.lstrip()[:200].lower()
    is_html = (not is_pdf) and (
        head_low.startswith((b"<!doctype", b"<html")) or "text/html" in content_type
    )
    if reject_html and is_html:
        return {
            "status": "failed",
            "url": clean_url,
            "status_code": status_code,
            "content_type": content_type,
            "size_bytes": len(raw_bytes),
            "verification": {"valid": False},
            "error": "La réponse est une page HTML et non un document téléchargeable.",
        }

    # Extraction du contenu en mémoire (avant toute écriture sur le disque)
    excerpt = ""
    pages: int | None = None
    if is_pdf:
        excerpt, pages = _extract_pdf_info(raw_bytes)
    else:
        try:
            raw_bytes[:512].decode("utf-8")
            excerpt = raw_bytes[:4000].decode("utf-8", errors="replace")
        except Exception:
            excerpt = ""

    if relevance_query:
        probe = {
            "url": clean_url,
            "provenance": {"content_excerpt": excerpt or context_hint},
        }
        if not _relevant(probe, relevance_query):
            return {
                "status": "rejected",
                "url": clean_url,
                "status_code": status_code,
                "content_type": content_type,
                "size_bytes": len(raw_bytes),
                "verification": {"valid": False},
                "reason": "Contenu hors sujet : les mots-clés de la requête sont absents du document.",
                "error": "Document rejeté (hors sujet), non écrit sur le disque.",
            }

    fs = WorkspaceFilesystem(workspace)
    if output_path:
        rel_dest = output_path.replace("\\", "/").lstrip("/")
        # Si les octets reçus sont un PDF authentique, s'assurer que l'extension est bien .pdf
        if is_pdf and not rel_dest.lower().endswith(".pdf"):
            rel_dest = str(Path(rel_dest).with_suffix(".pdf")).replace("\\", "/")
    else:
        url_path = urllib.parse.urlparse(clean_url).path
        base_name = Path(url_path).name or ""
        clean_name = re.sub(r"[^a-zA-Z0-9._-]", "_", base_name)
        if is_pdf:
            stem = Path(clean_name).stem if clean_name else "document"
            clean_name = f"{stem}.pdf"
        elif not clean_name or len(clean_name) < 4:
            clean_name = f"document_{hashlib.md5(clean_url.encode()).hexdigest()[:6]}.pdf"
        rel_dest = f"downloads/{clean_name}"

    dest_file = fs.resolve(rel_dest)
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_file, "wb") as f_out:
        f_out.write(raw_bytes)

    # Vérification physique
    verif = verify_downloaded_file(dest_file)

    # Chaîne de provenance (Source Web -> URL -> Téléchargement -> Fichier -> Hash -> Magic Bytes -> Contenu -> Vérification)
    prov_data: dict[str, Any] = {}
    if verif["valid"]:
        from core.artifacts.provenance import ProvenanceLedger

        ledger = ProvenanceLedger(fs.root)
        prov_rec = ledger.record_download(
            origin_url=clean_url,
            local_path=rel_dest,
            raw_bytes=raw_bytes,
            content_excerpt=excerpt,
            page_count=pages,
            attempted_sources=attempted_sources or [],
            task_id=task_id,
        )
        prov_data = prov_rec.to_dict()

    return {
        "status": "success" if verif["valid"] else "failed",
        "url": clean_url,
        "status_code": status_code,
        "content_type": content_type,
        "saved_path": rel_dest,
        "relative_path": rel_dest,
        "size_bytes": len(raw_bytes),
        "verification": verif,
        "provenance": prov_data,
        "provenance_chain": prov_data,
    }


# ---------------------------------------------------------------------------
# Workflow autonome : recherche -> exploration -> téléchargement -> vérification
# ---------------------------------------------------------------------------

def autonomous_web_retrieve_and_download(
    query: str,
    workspace: str | Path = WORKSPACE_ROOT,
    target_filename: str = "",
    timeout: float = 12.0,
    max_attempts: int = 12,
    task_id: str = "",
    filesystem: Any = None,
    total_timeout: float = 150.0,
) -> dict[str, Any]:
    """Exécute le workflow complet d'autonomie Web :
    1. Recherche multi-sources (Bing, DDG, sites de cours ciblés, portails officiels).
    2. Filtrage des candidats hors sujet, puis navigation multi-niveaux dans les pages.
    3. Téléchargement réel et vérification physique stricte.
    4. Correspondance sémantique obligatoire (un document hors sujet n'est jamais écrit).
    5. Établissement de la chaîne de provenance associée au task_id.
    """
    if filesystem is not None and hasattr(filesystem, "root"):
        workspace = filesystem.root

    cleaned_query = _clean_download_query(query)
    clean_lower = cleaned_query.lower()
    clean_norm = _norm_txt(cleaned_query)
    deadline = time.monotonic() + total_timeout

    attempts_log: list[str] = []
    attempted_sources: list[dict[str, Any]] = []

    def _expired() -> bool:
        if time.monotonic() > deadline:
            if not attempts_log or "Délai global" not in attempts_log[-1]:
                attempts_log.append("Délai global dépassé : arrêt de l'exploration.")
            return True
        return False

    # Détection du nom de fichier cible si non spécifié
    if not target_filename:
        cerfa_m = re.search(r"(?:cerfa[_\s-]*)?(\d{5})(?:\*?(\d{2}))?", clean_lower)
        if "cerfa" in clean_lower and cerfa_m:
            c_num = cerfa_m.group(1)
            c_ext = cerfa_m.group(2) or "02"
            target_filename = f"downloads/cerfa_{c_num}_{c_ext}.pdf"
        elif "bac" in clean_lower and "2026" in clean_lower:
            target_filename = "downloads/bac_2026_maths_metropole_1.pdf"

    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # Accès direct si la requête est déjà une URL directe
    if cleaned_query.startswith(("http://", "https://")):
        if cleaned_query not in seen_urls:
            seen_urls.add(cleaned_query)
            candidates.append({"url": cleaned_query, "title": "Direct URL", "snippet": "Lien direct fourni"})

    # Accès direct aux formulaires officiels CERFA
    cerfa_num_match = re.search(r"(?:cerfa[_\s-]*)?(\d{5})(?:\*?(\d{2}))?", clean_lower)
    if "cerfa" in clean_lower and cerfa_num_match:
        c_num = cerfa_num_match.group(1)
        priority_urls = [
            f"https://www.formulaires.service-public.fr/gf/cerfa_{c_num}.do",
            f"https://www.service-public.gouv.fr/simulateur/calcul/{c_num}",
            "https://immatriculation.ants.gouv.fr/services-et-formulaires/telecharger-un-formulaire-cerfa",
        ]
        for pu in priority_urls:
            if pu not in seen_urls:
                seen_urls.add(pu)
                candidates.append({"url": pu, "title": f"CERFA {c_num} - Formulaire officiel", "snippet": "Portail officiel service-public.fr"})

    # --- 1. Recherches -----------------------------------------------------
    topic = " ".join(re.sub(r"(?i)\b(cours|pdf)\b", " ", cleaned_query).split())
    search_queries: list[str] = []
    if any(k in clean_norm for k in ("cours", "math", "seconde", "premiere", "terminale", "exercice", "lecon")):
        search_queries += [
            f"{topic} site:maths-et-tiques.fr",
            f"{topic} site:methodemaths.fr",
            f"{topic} site:pimath.fr",
        ]
    search_queries.append(cleaned_query)
    if "filetype" not in clean_lower:
        search_queries.append(f"{cleaned_query} filetype:pdf")

    for sq in search_queries:
        if _expired():
            break
        found: list[dict[str, Any]] = []
        errs: list[str] = []
        try:
            ws_res = web_search(sq, timeout=min(timeout, 8.0))
            if isinstance(ws_res, dict):
                found = list(ws_res.get("results") or ws_res.get("sources") or [])
            elif isinstance(ws_res, list):
                found = list(ws_res)
        except Exception as e:
            errs.append(f"web_search: {type(e).__name__}: {e}")
            found = []
        if not found:
            for name, engine in (("bing", _search_bing), ("duckduckgo_lite", _search_duckduckgo_lite)):
                try:
                    found = engine(sq, timeout=min(timeout, 8.0))
                except Exception as e:
                    errs.append(f"{name}: {type(e).__name__}: {e}")
                    found = []
                if found:
                    break
        new = 0
        for item in found:
            u = item.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                candidates.append(item)
                new += 1
        attempts_log.append(f"Recherche {sq!r} : {len(found)} résultats, {new} nouveaux" + (f", erreurs : {errs}" if errs else ""))
        if len(candidates) >= 20:
            break
        time.sleep(0.4)  # évite la limitation de débit des moteurs

    # --- 2. Classement et filtrage ----------------------------------------
    stems3 = _query_stems(cleaned_query, min_len=3)

    def _score(text: str) -> int:
        t = _norm_txt(text)
        return sum(1 for k in stems3 if k in t)

    official_domains = ("service-public.fr", "service-public.gouv.fr", "ants.gouv.fr", "sujetdebac.fr",
                        "apmep.fr", "eduscol.education.gouv.fr", "education.gouv.fr")
    trusted_edu = ("maths-et-tiques.fr", "methodemaths.fr", "pimath.fr", "tiplanet.org", "annales", "bipm.org", "obspm.fr")

    def _rank_candidate(c: dict[str, Any]) -> tuple[int, int]:
        u = str(c.get("url") or "").lower()
        full_text = f"{u} {c.get('title') or ''} {c.get('snippet') or ''}"
        matches = _score(full_text)
        is_official = any(dom in u for dom in official_domains)
        path = urllib.parse.urlparse(u).path
        if is_official and matches >= 2:
            tier = 0
        elif is_official:
            tier = 1
        elif path.endswith(".pdf") and matches >= 2:
            tier = 2
        elif any(dom in u for dom in trusted_edu):
            tier = 3
        elif path.endswith(".pdf"):
            tier = 4
        else:
            tier = 5
        return (tier, -matches)

    candidates.sort(key=_rank_candidate)
    attempts_log.append(f"Candidats avant filtre : {len(candidates)}")
    kept: list[dict[str, Any]] = []
    for c in candidates:
        probe = {
            "url": c.get("url", ""),
            "provenance": {"content_excerpt": f"{c.get('title', '')} {c.get('snippet', '')}"},
        }
        if _relevant(probe, cleaned_query):
            kept.append(c)
        else:
            attempts_log.append(f"  écarté (hors sujet) : {c.get('url', '')}")
    candidates = kept
    attempts_log.append(f"Candidats après filtre : {len(candidates)}")

    fs = WorkspaceFilesystem(workspace)
    from core.artifacts.provenance import ProvenanceLedger
    ledger = ProvenanceLedger(fs.root)

    # --- 3. Téléchargement et vérification --------------------------------
    def _semantic_ok(rel_path: str) -> tuple[bool, dict[str, Any]]:
        try:
            sem = ledger.verify_semantic_match(rel_path, cleaned_query, fs)
        except Exception as err:  # la vérification du ledger ne doit pas bloquer à elle seule
            return True, {"match": True, "reason": f"vérification ledger indisponible : {err}"}
        if not isinstance(sem, dict):
            return True, {"match": True}
        return bool(sem.get("match", True)), sem

    def _try_download(dl_url: str, strategy: str, parent: str = "", hint: str = "") -> dict[str, Any] | None:
        attempts_log.append(f"  -> Téléchargement ({strategy}) : {dl_url}")
        attempted_sources.append({
            "url": dl_url,
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        try:
            dl = download_resource(
                dl_url,
                output_path=target_filename,
                workspace=workspace,
                timeout=timeout,
                attempted_sources=attempted_sources,
                task_id=task_id,
                relevance_query=cleaned_query,
                reject_html=True,
                context_hint=hint,
            )
        except Exception as err:
            attempts_log.append(f"     échec : {type(err).__name__}: {err}")
            attempted_sources[-1]["error"] = str(err)
            return None

        if dl.get("status") != "success":
            reason = dl.get("reason") or dl.get("error") or dl.get("status")
            attempts_log.append(f"     rejeté : {reason}")
            attempted_sources[-1]["error"] = str(reason)
            return None

        ok, sem = _semantic_ok(dl["relative_path"])
        if not ok:
            fs.resolve(dl["relative_path"]).unlink(missing_ok=True)
            attempts_log.append(f"     rejet sémantique : {sem.get('reason')}")
            attempted_sources[-1]["error"] = "rejet sémantique"
            return None

        summary = (
            f"Document téléchargé et vérifié physiquement dans {dl['relative_path']} "
            f"({dl['size_bytes']} octets) depuis {dl['url']}"
        )
        if parent:
            summary += f" (trouvé sur {parent})"
        result = {
            "status": "success",
            "downloaded_file": dl,
            "relative_path": dl["relative_path"],
            "source_url": dl["url"],
            "attempts": attempts_log,
            "attempted_sources": attempted_sources,
            "verification": dl["verification"],
            "semantic_match": sem,
            "provenance": dl.get("provenance", {}),
            "provenance_chain": dl.get("provenance_chain", {}),
            "summary": summary,
        }
        if parent:
            result["parent_page"] = parent
        return result

    cerfa_query = "cerfa" in clean_norm
    sujet_query = "sujet" in clean_norm
    corrige_query = "corrig" in clean_norm

    def _is_doc_link(link: dict[str, str]) -> bool:
        path = urllib.parse.urlparse(link["url"]).path.lower()
        if path.endswith((".pdf", ".docx", ".zip", ".do")):
            return True
        anchor = _norm_txt(link.get("text", ""))
        return any(k in anchor for k in ("telecharger", "download", "exemplaire", "cerfa", "sujet", "pdf"))

    def _score_link(link: dict[str, str]) -> int:
        text = _norm_txt(f"{link['url']} {link.get('text', '')}")
        score = 2 * _score(text)
        if urllib.parse.urlparse(link["url"]).path.lower().endswith(".pdf"):
            score += 3
        if cerfa_query and "cerfa" in text:
            score += 5
        if cerfa_query and ("exemplaire" in text or "vierge" in text):
            score += 4
        if sujet_query and "sujet" in text:
            score += 3
        if not corrige_query and ("corrige" in text or "correction" in text):
            score -= 3
        return score

    visited_pages: set[str] = set()
    sub_need = max(1, min(2, len(stems3)))

    def _explore(page_url: str, depth: int) -> dict[str, Any] | None:
        if page_url in visited_pages or depth > 3 or _expired():
            return None
        visited_pages.add(page_url)
        indent = "  " * depth
        attempts_log.append(f"{indent}-> Exploration niveau {depth} : {page_url}")
        try:
            page = fetch_url(page_url, timeout=timeout)
        except Exception as err:
            attempts_log.append(f"{indent}   échec navigation : {type(err).__name__}: {err}")
            return None

        page_hint = f"{page.get('title', '')} {(page.get('text') or '')[:300]}"
        doc_links = [l for l in (page.get("download_links") or []) if _is_doc_link(l)]
        doc_links.sort(key=_score_link, reverse=True)
        for link in doc_links[: 4 if depth == 1 else 2]:
            if _expired():
                return None
            res = _try_download(
                link["url"],
                f"page_niveau_{depth}",
                parent=page_url,
                hint=f"{link.get('text', '')} {page_hint}",
            )
            if res:
                return res

        if depth < 3:
            domain = urllib.parse.urlparse(page_url).netloc.lower()
            subs = []
            for l in (page.get("links") or []):
                parsed = urllib.parse.urlparse(l["url"])
                if parsed.netloc.lower() != domain:
                    continue
                if parsed.path.lower().endswith(_SKIP_SUBPAGE_EXTS):
                    continue
                if l["url"] in visited_pages:
                    continue
                if _score(f"{l['url']} {l.get('text', '')}") >= sub_need:
                    subs.append(l)
            subs.sort(key=lambda l: _score(f"{l['url']} {l.get('text', '')}"), reverse=True)
            for sub in subs[: 3 if depth == 1 else 2]:
                res = _explore(sub["url"], depth + 1)
                if res:
                    return res
        return None

    for idx, cand in enumerate(candidates[:max_attempts], start=1):
        if _expired():
            break
        cand_url = cand.get("url", "")
        if not cand_url:
            continue
        path = urllib.parse.urlparse(cand_url).path.lower()
        hint = f"{cand.get('title', '')} {cand.get('snippet', '')}"
        attempts_log.append(f"Tentative {idx} : {cand_url}")

        if path.endswith(_DIRECT_FILE_EXTS + (".do",)):
            res = _try_download(cand_url, "direct", hint=hint)
            if res:
                return res
            if path.endswith(_DIRECT_FILE_EXTS):
                continue  # inutile d'explorer un fichier comme une page

        res = _explore(cand_url, 1)
        if res:
            return res

    # Échec honnête : aucune fabrication locale
    return {
        "status": "failed",
        "attempts": attempts_log,
        "attempted_sources": attempted_sources,
        "sources_checked": [c.get("url") for c in candidates[:max_attempts]],
        "downloaded_file": None,
        "provenance_chain": None,
        "error": "Aucun document physique valide n'a pu être téléchargé après exploration autonome de plusieurs sources et méthodes. Aucun document de substitution n'a été fabriqué.",
    }


# ---------------------------------------------------------------------------
# Récupération de pages et recherche Web
# ---------------------------------------------------------------------------

def fetch_url(
    url: str,
    output_path: str = "",
    workspace: str | Path = WORKSPACE_ROOT,
    timeout: float = 12.0,
    max_chars: int = 4000,
) -> dict[str, Any]:
    """Récupère réellement le contenu d'une URL Web distante (HTML, texte, PDF, etc.)."""
    clean_url = (url or "").strip()
    if not clean_url.startswith(("http://", "https://")):
        raise ValueError(f"URL invalide : {url!r}")

    req = urllib.request.Request(
        clean_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf,application/json,*/*",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status_code = resp.status
        content_type = str(resp.headers.get("content-type") or "").lower()
        raw_bytes = resp.read()

    fs = WorkspaceFilesystem(workspace)
    saved_path = ""
    if output_path:
        saved_path = fs.write_file(output_path, raw_bytes.decode("utf-8", errors="replace"))

    is_html = "html" in content_type or raw_bytes.startswith(b"<!DOCTYPE") or b"<html" in raw_bytes[:500].lower()
    title = ""
    clean_text = ""
    download_links: list[dict[str, str]] = []
    all_links: list[dict[str, str]] = []

    if is_html:
        decoded_html = raw_bytes.decode("utf-8", errors="replace")
        m_title = re.search(r"<title[^>]*>(.*?)</title>", decoded_html, re.I | re.S)
        if m_title:
            title = _clean_html(m_title.group(1))
        download_links = _extract_download_links(decoded_html, clean_url)
        all_links = _extract_all_links(decoded_html, clean_url)
        clean_text = _clean_html_main(decoded_html) or _clean_html(decoded_html)
    else:
        clean_text = raw_bytes[:10000].decode("utf-8", errors="replace")

    return {
        "url": clean_url,
        "status_code": status_code,
        "content_type": content_type,
        "title": title,
        "download_links": download_links,
        "download_links_count": len(download_links),
        "links": all_links,
        "text": clean_text[:max_chars],
        "size_bytes": len(raw_bytes),
        "saved_path": saved_path,
    }


def web_search(
    query: str,
    max_results: int = 5,
    *,
    timeout: float = 10.0,
    backend_enabled: bool = True,
    download: bool = True,
    output_path: str = "",
    workspace: str | Path = WORKSPACE_ROOT,
    task_id: str = "",
    **ignored: Any,
) -> dict[str, Any]:
    """Exécute une recherche Internet réelle et retourne des sources vérifiables.

    Si output_path est fourni (ou si la requête demande un téléchargement), tente aussi de
    télécharger un document pertinent dans le workspace. Les arguments inattendus envoyés
    par le LLM sont ignorés (alias acceptés : outputpath, target_filename, filename).
    """
    output_path = (
        output_path
        or ignored.pop("outputpath", "")
        or ignored.pop("target_filename", "")
        or ignored.pop("filename", "")
    )
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Une requête Web non vide est requise.")
    cleaned_query = " ".join(query.strip().split())
    search_terms = _extract_search_keywords(cleaned_query)
    limit = max(1, min(int(max_results or 5), 10))

    disabled_env = os.environ.get("NEOHARNESS_DISABLE_WEB_SEARCH", "").strip().casefold()
    if not backend_enabled or disabled_env in {"1", "true", "yes", "off"}:
        raise RuntimeError(
            "Aucun backend de recherche Web n'est configuré ou actif; "
            "aucune source distante n'a été consultée."
        )

    # 1. Demande explicite de téléchargement (ou chemin de sortie fourni)
    asks_download = download and (
        bool(output_path)
        or any(
            kw in cleaned_query.casefold()
            for kw in ("télécharge", "telecharge", "télécharger", "telecharger", "download", "récupère", "recupere", "trouve sur internet", "trouver sur internet")
        )
    )
    download_result: dict[str, Any] | None = None
    download_error = ""
    if asks_download:
        try:
            download_result = autonomous_web_retrieve_and_download(
                search_terms,
                workspace=workspace,
                target_filename=output_path,
                timeout=timeout,
                task_id=task_id,
            )
        except Exception as error:
            download_error = f"{type(error).__name__}: {error}"

    lowered = cleaned_query.casefold()
    is_news_query = any(
        marker in lowered
        for marker in (
            "actualité", "actualite", "actualités", "actualites", "news",
            "aujourd'hui", "aujourd hui", "récent", "recent",
            "dernière", "derniere", "dernières", "dernieres",
            "2025", "2026",
        )
    )

    bing_results: list[dict[str, Any]] = []
    ddgs_results: list[dict[str, Any]] = []
    bing_results: list[dict[str, Any]] = []
    ddg_results: list[dict[str, Any]] = []
    news_results: list[dict[str, Any]] = []
    wiki_results: list[dict[str, Any]] = []
    errors: list[str] = []
    backends_used: list[str] = []

    direct_url_candidate: dict[str, Any] | None = None
    if cleaned_query.startswith(("http://", "https://")):
        try:
            dp = fetch_url(cleaned_query, timeout=timeout)
            if dp and dp.get("status_code") == 200:
                direct_url_candidate = {
                    "title": dp.get("title") or cleaned_query,
                    "url": cleaned_query,
                    "snippet": (dp.get("text") or "")[:350],
                    "source": urllib.parse.urlparse(cleaned_query).netloc or "Web",
                    "published_at": "",
                    "provider": "direct_url",
                }
                backends_used.append("direct_url")
        except Exception as error:
            errors.append(f"direct_url: {type(error).__name__}: {error}")

    try:
        ddgs_results = _search_ddgs(search_terms, timeout=min(timeout, 8.0))
        if ddgs_results:
            backends_used.append("ddgs")
    except Exception as error:
        errors.append(f"ddgs: {type(error).__name__}: {error}")

    try:
        bing_results = _search_bing(search_terms, timeout=min(timeout, 6.0))
        # Bing sert parfois une page de remplissage hors sujet : on ne garde que le pertinent
        bing_results = [
            r for r in bing_results
            if _relevant(
                {"url": r["url"], "provenance": {"content_excerpt": f"{r['title']} {r['snippet']}"}},
                search_terms,
            )
        ]
        if bing_results:
            backends_used.append("bing")
    except Exception as error:
        errors.append(f"bing: {type(error).__name__}: {error}")

    try:
        ddg_results = _search_duckduckgo_lite(search_terms, timeout=timeout)
        if ddg_results:
            backends_used.append("duckduckgo_lite")
    except Exception as error:
        errors.append(f"duckduckgo_lite: {type(error).__name__}: {error}")

    try:
        news_results = _search_google_news_rss(search_terms, timeout=timeout)
        if news_results:
            backends_used.append("google_news_rss")
    except Exception as error:
        errors.append(f"google_news_rss: {type(error).__name__}: {error}")

    if len(ddgs_results) + len(bing_results) + len(ddg_results) + len(news_results) < limit:
        try:
            wiki_results = _search_wikipedia_fr(search_terms, timeout=timeout)
            if wiki_results:
                backends_used.append("wikipedia_api")
        except Exception as error:
            errors.append(f"wikipedia_api: {type(error).__name__}: {error}")

    ordered_candidates: list[dict[str, Any]] = []
    if direct_url_candidate:
        ordered_candidates.append(direct_url_candidate)
    if is_news_query:
        max_len = max(len(news_results), len(ddgs_results), len(bing_results), len(ddg_results))
        for idx in range(max_len):
            if idx < len(news_results):
                ordered_candidates.append(news_results[idx])
            if idx < len(ddgs_results):
                ordered_candidates.append(ddgs_results[idx])
            if idx < len(bing_results):
                ordered_candidates.append(bing_results[idx])
            if idx < len(ddg_results):
                ordered_candidates.append(ddg_results[idx])
        ordered_candidates.extend(wiki_results)
    else:
        ordered_candidates.extend(ddgs_results)
        ordered_candidates.extend(bing_results)
        ordered_candidates.extend(ddg_results)
        ordered_candidates.extend(news_results)
        ordered_candidates.extend(wiki_results)

    deduped: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in ordered_candidates:
        url = str(item.get("url") or "").strip()
        if not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)
        if len(deduped) >= limit:
            break

    if not deduped and errors:
        raise RuntimeError(
            "La recherche Web réelle a échoué ("
            + " ; ".join(errors)
            + ") ; aucune source distante n'a pu être consultée."
        )

    formatted_lines = [f"Résultats de recherche Internet pour « {cleaned_query} » :"]
    for index, item in enumerate(deduped, start=1):
        date_str = f" ({item['published_at']})" if item.get("published_at") else ""
        source_str = f" [{item['source']}]" if item.get("source") else ""
        formatted_lines.append(
            f"{index}. {item['title']}{source_str}{date_str}\n"
            f"   URL : {item['url']}\n"
            f"   Extrait : {item.get('snippet') or 'Aucun extrait texte.'}"
        )

    result_payload: dict[str, Any] = {
        "query": cleaned_query,
        "backend": "+".join(backends_used) if backends_used else "none",
        "count": len(deduped),
        "results": deduped,
        "sources": [
            {
                "title": item["title"],
                "url": item["url"],
                "snippet": item.get("snippet", ""),
                "source": item.get("source", ""),
                "published_at": item.get("published_at", ""),
            }
            for item in deduped
        ],
        "formatted": "\n".join(formatted_lines),
        "errors": errors,
    }

    if download_result is not None:
        result_payload["download_attempts"] = download_result.get("attempts", [])
    if download_error:
        result_payload["download_error"] = download_error
    if download_result and download_result.get("status") == "failed":
        result_payload["download_error"] = download_result.get("error", "")
    if download_result and download_result.get("status") == "success":
        result_payload["downloaded_file"] = download_result["downloaded_file"]
        result_payload["provenance"] = download_result.get("provenance")
        result_payload["provenance_chain"] = download_result.get("provenance_chain")
        result_payload["formatted"] += (
            f"\n\n[DOCUMENT TÉLÉCHARGÉ ET VÉRIFIÉ PHYSQUEMENT]\n"
            f"Fichier local : {download_result['relative_path']}\n"
            f"Source URL : {download_result['source_url']}\n"
            f"Taille : {download_result['downloaded_file']['size_bytes']} octets\n"
            f"Intégrité : {download_result['verification']['summary']}"
        )
    elif result_payload.get("download_error"):
        tail = "\n".join((result_payload.get("download_attempts") or [])[-12:])
        result_payload["formatted"] += (
            "\n\n[TÉLÉCHARGEMENT NON RÉALISÉ]\n"
            f"Raison : {result_payload['download_error']}\n"
            + (f"Dernières tentatives :\n{tail}" if tail else "")
        )
    return result_payload


def search(query: str, workspace: str | Path = WORKSPACE_ROOT) -> str:
    """Compatibilité historique, maintenant reliée à une vraie recherche locale."""
    matches = WorkspaceFilesystem(workspace).search_files(query)
    if not matches:
        return f"Aucune occurrence de {query!r} dans le workspace."
    return "\n".join(
        f"{item['path']}:{item['line']}: {item['text']}" for item in matches
    )


def search_web(query: str, *, backend_enabled: bool = False) -> str:
    """Point d'entrée legacy exigeant un backend explicitement activé."""
    if not query.strip():
        raise ValueError("Une requête Web est requise.")
    if not backend_enabled:
        raise RuntimeError(
            "Aucun backend de recherche Web n'est configuré; aucune source distante "
            "n'a été consultée."
        )
    payload = web_search(query, backend_enabled=True)
    return str(payload.get("formatted", ""))


# ---------------------------------------------------------------------------
# CHANTIER 4 : MOTEUR DEEP RESEARCH (ESSAIM PARALLÈLE + LECTURE PROFONDE + VÉRIFICATION CROISÉE)
# ---------------------------------------------------------------------------

from concurrent.futures import ThreadPoolExecutor, as_completed


def _classify_domain_authority(url: str) -> tuple[str, int]:
    """Évalue le niveau d'autorité d'une source Web (3 = Institutionnel/Académique, 2 = Référence/Presse, 1 = Web spécialisé)."""
    dom = urllib.parse.urlparse(url).netloc.lower()
    if "news.google.com" in dom:
        return "Agrégateur d'actualités", 0
    if any(
        dom.endswith(ext) or ext in dom
        for ext in (
            ".gouv.fr", ".gov", ".edu", "europa.eu", "insee.fr", "legifrance.gouv.fr",
            "service-public.fr", "eduscol.education.gouv.fr", "arxiv.org", "hal.science",
            "cnrs.fr", "inria.fr", "cea.fr", "inserm.fr", "banque-france.fr", "ocde.org", "oecd.org", "who.int",
        )
    ):
        return "Institutionnel / Académique (Haute autorité)", 3
    if any(
        ext in dom
        for ext in (
            "wikipedia.org", "lemonde.fr", "lesechos.fr", "lefigaro.fr", "francetvinfo.fr",
            "reuters.com", "bbc.com", "nature.com", "science.org", "ieee.org", "acm.org",
            "github.com", "python.org", "microsoft.com", "google.com", "openai.com", "anthropic.com",
        )
    ):
        return "Source de référence / Presse établie", 2
    return "Source Web spécialisée", 1


_FRENCH_QUESTION_SCAFFOLDING = {
    "quel", "quelle", "quels", "quelles", "comment", "pourquoi", "combien", "quand",
    "est", "sont", "etre", "avoir", "faire", "peut", "faut", "doit", "vaut",
    "ce", "cet", "cette", "ces", "cela", "ca", "il", "elle", "ils", "elles", "on",
    "un", "une", "le", "la", "les", "de", "du", "des", "au", "aux", "en", "dans",
    "sur", "avec", "pour", "par", "sans", "sous", "vers", "chez", "plus", "moins",
    "tres", "vraiment", "bien", "bon", "bonne", "meilleur", "meilleure",
    "fais", "faire", "recherche", "avancee", "approfondie", "complete", "analyse",
    "explique", "donne", "trouve", "cherche", "dis", "moi", "nous", "vous",
}

# Mots qui expriment ce que l'utilisateur veut savoir, pas le sujet lui-même
_INTENT_WORDS = {
    "avis", "prix", "tarif", "tarifs", "occasion", "occasions", "reconditionne", "reconditionnes",
    "test", "tests", "comparatif", "comparaison", "promo", "promos", "soldes", "acheter", "achat",
}


def _deterministic_parse_query(raw_query: str) -> dict[str, Any]:
    """Analyse grammaticale déterministe de la demande utilisateur :
    1. Extrait le Groupe Nominal Sujet (pivot) sans les verbes/auxiliaires interrogatifs.
    2. Identifie l'intention syntaxique (évaluation 'est-il...', choix 'quel...', mécanisme 'comment...').
    3. Isole les mots-ancres obligatoires (les termes les plus spécifiques du sujet).
    """
    raw = " ".join((raw_query or "").strip().split())
    # 1. Retrait déterministe des préfixes de commande et d'interrogation
    clean = re.sub(
        r"(?i)^(?:/research\s+)?(?:(?:fais|effectue|lance)(?:-moi)?\s+une\s+recherche\s+"
        r"(?:avancée|avancee|approfondie|complète|complete)?\s*(?:sur\s+|concernant\s+)?|"
        r"(?:cherche|recherche|trouve|analyse|explique)(?:-moi)?\s+)",
        "",
        raw,
    ).strip()

    # Détection de la structure interrogative avant nettoyage
    low_clean = _norm_txt(clean)
    is_evaluation = bool(
        re.search(r"\b(?:est[- ]il|est[- ]elle|sont[- ]ils|vaut[- ]il|efficace|puissant|fiable|dangereux|avis)\b", low_clean)
    )
    is_choice = bool(
        re.search(r"^(?:quel|quelle|quels|quelles|que\s+faire| comment\s+choisir)\b", low_clean)
    )

    # Extraction du pivot nominal (sujet pur) et du prédicat évaluatif éventuel
    eval_predicate = ""
    m_eval = re.search(
        r"(?i)^(.+?)\s+(?:est[- ]il|est[- ]elle|sont[- ]ils|sont[- ]elles|est\s+il|est\s+elle)\s+(.+?)\s*[?!.]*$",
        clean,
    )
    if m_eval:
        pivot = m_eval.group(1).strip(" ?.!,:;-")
        eval_predicate = m_eval.group(2).strip(" ?.!,:;-")
    else:
        pivot = re.sub(
            r"(?i)^(?:quel(?:le)?s?\s+|comment\s+|pourquoi\s+|qu['’]est[- ]ce\s+qu(?:e|')\s*|est[- ]ce\s+qu(?:e|')\s*)",
            "",
            clean,
        )
        pivot = re.sub(r"(?i)\b(?:faire\s+après|faire\s+avec|faire\s+pour)\b", lambda m: m.group(0).split()[-1], pivot)
        pivot = pivot.strip(" ?.!,:;-")

    # Extraction déterministe des tokens substantifs du pivot (mots >= 3 lettres hors mots-outils)
    pivot_words_raw = re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", pivot)
    content_tokens: list[str] = []
    for w in pivot_words_raw:
        w_norm = _norm_txt(w)
        if (
            w_norm not in _FRENCH_QUESTION_SCAFFOLDING
            and w_norm not in _INTENT_WORDS
            and w_norm not in content_tokens
        ):
            content_tokens.append(w)

    if not content_tokens:
        content_tokens = [w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", clean) if _norm_txt(w) not in _FRENCH_QUESTION_SCAFFOLDING][:4]

    short_subject = " ".join(content_tokens[:4]) if content_tokens else pivot[:50]
    has_intent_words = bool(set(re.findall(r"[a-z0-9]+", low_clean)) & _INTENT_WORDS)
    display_subject = short_subject if (has_intent_words and short_subject) else (pivot if len(pivot) <= 55 else short_subject)

    # Les racines d'ancrage obligatoires (au moins 1 de ces racines DOIT figurer dans toute page retenue)
    anchor_stems = [_norm_txt(w).rstrip("s") for w in content_tokens if len(_norm_txt(w)) >= 3][:4]

    return {
        "raw": raw,
        "display_subject": display_subject,
        "short_keywords": short_subject,
        "eval_predicate": eval_predicate,
        "is_evaluation": is_evaluation,
        "is_choice": is_choice,
        "anchor_stems": anchor_stems,
        "wants_used": bool(re.search(r"occasion|seconde\s+main|reconditionn", low_clean)),
        "wants_price": bool(re.search(r"\b(?:prix|tarifs?|cout|combien|promo\w*|solde\w*)\b", low_clean)),
    }


def _build_human_research_axes(core_topic: str) -> list[dict[str, str]]:
    """Axes de base + axes ciblés selon l'intention détectée (occasion, prix, fiche technique)."""
    parsed = _deterministic_parse_query(core_topic)
    axes = _build_base_research_axes(core_topic)
    subj, kw = parsed["display_subject"], parsed["short_keywords"]
    if parsed["wants_used"]:
        axes.append({
            "title": f"6. Marché de l'occasion et du reconditionné : prix constatés ({subj})",
            "pill": "Occasion",
            "query": f"{kw} occasion reconditionné prix leboncoin back market",
        })
        axes.append({
            "title": f"7. Cote, décote et points à vérifier avant d'acheter d'occasion ({subj})",
            "pill": "Achat occasion",
            "query": f"{kw} occasion que vérifier garantie batterie",
        })
    elif parsed["wants_price"]:
        axes.append({
            "title": f"6. Prix actuels, historique et promotions ({subj})",
            "pill": "Prix",
            "query": f"{kw} prix comparateur promotion",
        })
    axes.append({
        "title": f"{len(axes) + 1}. Fiche technique et caractéristiques ({subj})",
        "pill": "Fiche technique",
        "query": f"{kw} fiche technique caractéristiques",
    })
    return axes


def _build_base_research_axes(core_topic: str) -> list[dict[str, str]]:
    """Génère de façon 100% déterministe 5 axes de recherche lisibles par un humain
    avec des requêtes moteurs courtes (3 à 5 mots) centrées sur le sujet réel."""
    parsed = _deterministic_parse_query(core_topic)
    subj = parsed["display_subject"]
    kw = parsed["short_keywords"]
    pred = parsed["eval_predicate"]

    if parsed["is_evaluation"]:
        crit = pred if (pred and len(pred) <= 35) else "efficacité et performances"
        return [
            {
                "title": f"1. Présentation, nature et fonctionnement de « {subj} »",
                "pill": "Fonctionnement",
                "query": f"{kw} fonctionnement composition",
            },
            {
                "title": f"2. Évaluation directe : {subj} ({crit})",
                "pill": "Évaluation & Preuves",
                "query": f"{kw} efficacité test puissance",
            },
            {
                "title": f"3. Avis vérifiés et retours d'expérience sur « {subj} »",
                "pill": "Retours & Avis",
                "query": f"{kw} avis résultats",
            },
            {
                "title": f"4. Utilisation pratique, cadre d'usage et précautions ({subj})",
                "pill": "Usage & Limites",
                "query": f"{kw} utilisation conseils limites",
            },
            {
                "title": f"5. Comparaison, alternatives et rapport qualité/efficacité ({subj})",
                "pill": "Comparatif",
                "query": f"{kw} comparatif alternatives",
            },
        ]

    if parsed["is_choice"]:
        return [
            {
                "title": f"1. Panorama complet des options possibles : {subj}",
                "pill": "Options principales",
                "query": f"{kw} options filières principales",
            },
            {
                "title": f"2. Comparatif détaillé des différentes voies ({subj})",
                "pill": "Comparatif",
                "query": f"{kw} comparatif différences",
            },
            {
                "title": f"3. Débouchés concrets, résultats et perspectives ({subj})",
                "pill": "Débouchés & Résultats",
                "query": f"{kw} débouchés métiers perspectives",
            },
            {
                "title": f"4. Critères de sélection, prérequis et chiffres clés ({subj})",
                "pill": "Chiffres & Critères",
                "query": f"{kw} critères statistiques admission",
            },
            {
                "title": f"5. Conseils pratiques pour faire le bon choix ({subj})",
                "pill": "Conseils de choix",
                "query": f"{kw} conseils comment choisir",
            },
        ]

    return [
        {
            "title": f"1. Définition, principes clés et fonctionnement : {subj}",
            "pill": "Principes clés",
            "query": f"{kw} définition fonctionnement",
        },
        {
            "title": f"2. Données factuelles, chiffres clés et constats sur « {subj} »",
            "pill": "Faits & Chiffres",
            "query": f"{kw} chiffres statistiques étude",
        },
        {
            "title": f"3. Applications concrètes, avantages et exemples ({subj})",
            "pill": "Applications & Avantages",
            "query": f"{kw} avantages applications exemples",
        },
        {
            "title": f"4. Comparatif des solutions et acteurs de référence ({subj})",
            "pill": "Comparatif",
            "query": f"{kw} comparatif référence",
        },
        {
            "title": f"5. Limites, points de vigilance et évolutions ({subj})",
            "pill": "Limites & Perspectives",
            "query": f"{kw} limites risques perspectives",
        },
    ]


def _build_default_subqueries(core_topic: str) -> list[str]:
    return [ax["query"] for ax in _build_human_research_axes(core_topic)]


def _extract_key_facts(text: str, max_facts: int = 5) -> list[str]:
    """Extrait les phrases denses contenant des faits chiffrés, dates, pourcentages ou constats."""
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored: list[tuple[int, str]] = []
    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 45 or len(s_clean) > 320:
            continue
        score = 0
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|Md€|M€|milliards?|millions?|ans?|km|Go|To|ms|ml|L)\b", s_clean, re.I):
            score += 4
        if re.search(r"\b202[3-9]\b", s_clean):
            score += 2
        if re.search(r"\b(?:selon|d'après|étude|rapport|officiel|mesure|hausse|baisse|résultat|efficace|odeur|bactérie|enzyme)\b", s_clean, re.I):
            score += 2
        if score > 0:
            scored.append((score, s_clean))
    scored.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    out: list[str] = []
    for _, fact in scored:
        norm = fact[:60].lower()
        if norm not in seen:
            seen.add(norm)
            out.append(fact)
            if len(out) >= max_facts:
                break
    return out


_USED_MARKET_HINTS = (
    "leboncoin.", "backmarket.", "rakuten.com", "ebay.", "vinted.", "cashconverters.",
    "easycash.", "recommerce", "refurb", "reconditionn", "occasion",
)


def _is_used_market(url: str, title: str = "") -> bool:
    """Source orientée occasion / reconditionné (domaine ou titre)."""
    hay = _norm_txt(f"{url} {title}")
    return any(h in hay for h in _USED_MARKET_HINTS)


def _clean_html_main(raw: str) -> str:
    """Texte principal d'une page : retire menus, en-têtes, pieds de page et encarts."""
    if not raw:
        return ""
    m = re.search(r"<(article|main)[^>]*>([\s\S]*?)</\1>", raw, re.I)
    body = m.group(2) if (m and len(m.group(2)) > 1500) else raw
    body = re.sub(r"<(nav|header|footer|aside|form|iframe)[^>]*>[\s\S]*?</\1>", " ", body, flags=re.I)
    return _clean_html(body)


def _select_relevant_passages(text: str, anchor_stems: list[str], max_chars: int = 3500) -> str:
    """Garde les phrases utiles (mots-clés du sujet, chiffres, prix, specs) au lieu du début de page."""
    scored: list[tuple[int, int, str]] = []
    for idx, sent in enumerate(re.split(r"(?<=[.!?])\s+", text or "")):
        s = sent.strip()
        if len(s) < 40 or len(s) > 400:
            continue
        n = _norm_txt(s)
        score = sum(2 for k in anchor_stems if k in n)
        if re.search(r"\d", s):
            score += 1
        if re.search(r"€|\beuros?\b", s, re.I):
            score += 2
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:W|AW|Wh|dB|kg|min|L|mAh|cm|ans?|%)\b", s):
            score += 2
        if score >= 2:
            scored.append((score, idx, s))
    top = sorted(scored, key=lambda t: t[0], reverse=True)[:14]
    top.sort(key=lambda t: t[1])  # retour à l'ordre de lecture
    return " ".join(s for _, _, s in top)[:max_chars]


def _extract_price_points(text: str, anchor_stems: list[str], max_items: int = 6) -> list[dict[str, Any]]:
    """Relève les prix en € proches d'un mot-clé du sujet (évite les prix d'accessoires sans rapport)."""
    flat = re.sub(r"(?<![\d.,])(\d{1,3})[\u202f\u00a0 ](\d{3})(?!\d)", r"\1\2", text or "")
    out: list[dict[str, Any]] = []
    seen: set[float] = set()
    for m in re.finditer(r"(\d{1,5}(?:[.,]\d{1,2})?)\s*(?:€|euros?\b)", flat, re.I):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if value < 5 or value > 20000 or value in seen:
            continue
        ctx = flat[max(0, m.start() - 110): m.end() + 60]
        if anchor_stems and not any(k in _norm_txt(ctx) for k in anchor_stems):
            continue
        seen.add(value)
        out.append({"value": value, "context": " ".join(ctx.split())})
        if len(out) >= max_items:
            break
    return out


def deep_research(
    query: str,
    sub_queries: list[str] | None = None,
    max_sources: int = 12,
    read_full_pages: bool = True,
    workspace: str | Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    """Exécute une recherche profonde en essaim parallèle (Deep Research style GPT) avec filtrage déterministe."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Une requête principale 'query' non vide est requise pour deep_research.")

    started = time.monotonic()
    clean_main = " ".join(query.strip().split())
    parsed_q = _deterministic_parse_query(clean_main)
    anchor_stems = parsed_q["anchor_stems"]
    primary_anchor = anchor_stems[0] if anchor_stems else ""

    human_axes = _build_human_research_axes(clean_main)
    queries_list = [q.strip() for q in (sub_queries or []) if isinstance(q, str) and q.strip()]
    if not queries_list:
        queries_list = [ax["query"] for ax in human_axes]
    else:
        queries_list = list(dict.fromkeys(queries_list))[:5]
        human_axes = [
            {"title": f"{i+1}. {q}", "pill": f"Axe {i+1}", "query": q}
            for i, q in enumerate(queries_list)
        ]

    cap_sources = max(3, min(int(max_sources or 12), 16))
    raw_candidates: list[dict[str, Any]] = []
    search_errors: list[str] = []

    # Phase 1 : Recherche Web en essaim parallèle sur les requêtes courtes
    def _run_subquery(sq: str) -> tuple[str, list[dict[str, Any]], str]:
        try:
            res = web_search(sq, max_results=8, download=False, timeout=8.0, workspace=workspace)            
            return sq, list(res.get("results") or []), ""
        except Exception as exc:
            return sq, [], f"{sq}: {exc}"

    with ThreadPoolExecutor(max_workers=min(len(queries_list), 5)) as pool:
        futs = [pool.submit(_run_subquery, sq) for sq in queries_list]
        for fut in as_completed(futs):
            sq, items, err = fut.result()
            if err:
                search_errors.append(err)
            for it in items:
                it_copy = dict(it)
                it_copy["matched_subquery"] = sq
                raw_candidates.append(it_copy)

    # Porte de pertinence déterministe : rejet strict de tout résultat hors-sujet
    def _relevance_tuple(c: dict[str, Any]) -> tuple[int, int, int]:
        url = str(c.get("url") or "")
        hay = _norm_txt(f"{c.get('title', '')} {c.get('snippet', '')} {url}")
        has_primary = 1 if (primary_anchor and primary_anchor in hay) else 0
        kw_hits = sum(1 for k in anchor_stems if k in hay)
        _, auth_tier = _classify_domain_authority(url)
        # Priorité absolue : 1) Présence de l'ancre principale, 2) Nombre de mots-clés du sujet, 3) Autorité
        return (has_primary, kw_hits, auth_tier)

    # Filtrer les pages qui n'ont AUCUN mot-clé du sujet (élimine Pont Neuf, Pornichet, etc.)
    filtered_candidates = [
        c for c in raw_candidates
        if not anchor_stems or _relevance_tuple(c)[1] > 0
    ]
    if not filtered_candidates:
        filtered_candidates = raw_candidates

    filtered_candidates.sort(key=_relevance_tuple, reverse=True)
    seen_urls: set[str] = set()
    domain_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for cand in filtered_candidates:
        u = str(cand.get("url") or "").strip()
        if not u.startswith(("http://", "https://")) or u in seen_urls:
            continue
        dom = urllib.parse.urlparse(u).netloc.lower()
        if domain_counts.get(dom, 0) >= 2:
            continue
        seen_urls.add(u)
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
        selected.append(cand)
        if len(selected) >= cap_sources:
            break

    # Si l'utilisateur parle d'occasion, réserver quelques places aux sources de seconde main
    if parsed_q.get("wants_used"):
        extra_used = [
            c for c in filtered_candidates
            if str(c.get("url") or "").startswith(("http://", "https://"))
            and str(c.get("url")) not in seen_urls
            and _is_used_market(str(c.get("url") or ""), str(c.get("title") or ""))
        ]
        for cand in extra_used[:3]:
            seen_urls.add(str(cand.get("url")))
            selected.append(cand)

    # Phase 2 : Lecture parallèle en profondeur des pages sélectionnées
    def _enrich_source(idx_and_item: tuple[int, dict[str, Any]]) -> dict[str, Any]:
        idx, item = idx_and_item
        url = str(item.get("url") or "")
        auth_label, auth_score = _classify_domain_authority(url)
        full_text = ""
        facts: list[str] = []
        price_points: list[dict[str, Any]] = []
        if read_full_pages:
            try:
                page = fetch_url(url, timeout=9.0, workspace=workspace, max_chars=60000)
                raw_text = str(page.get("text") or "").strip()
                full_text = _select_relevant_passages(raw_text, anchor_stems) or raw_text[:3500]
                facts = _extract_key_facts(raw_text, max_facts=8)
                price_points = _extract_price_points(raw_text, anchor_stems)
            except Exception:
                full_text = ""
        if not facts and item.get("snippet"):
            facts = _extract_key_facts(str(item.get("snippet")), max_facts=2)
        return {
            "citation_id": idx,
            "citation_tag": f"[{idx}]",
            "markdown_citation": f"[[{idx}]]({url})",
            "title": str(item.get("title") or url),
            "url": url,
            "domain": urllib.parse.urlparse(url).netloc,
            "authority_label": auth_label,
            "authority_tier": auth_score,
            "published_at": str(item.get("published_at") or ""),
            "matched_subquery": str(item.get("matched_subquery") or clean_main),
            "snippet": str(item.get("snippet") or ""),
            "extracted_content": full_text[:3500] if full_text else str(item.get("snippet") or ""),
            "key_facts": facts,
            "price_points": price_points,
            "is_used_market": _is_used_market(url, str(item.get("title") or "")),
        }
    enriched_sources: list[dict[str, Any]] = []
    if selected:
        with ThreadPoolExecutor(max_workers=min(len(selected), 6)) as pool:
            enriched_sources = list(pool.map(_enrich_source, enumerate(selected, start=1)))

    # Phase 3 : Matrice de vérification croisée (détection des concepts corroborés par >= 2 domaines distincts)
    term_domains: dict[str, set[str]] = {}
    for src in enriched_sources:
        dom = src["domain"]
        words = set(re.findall(r"[a-z0-9]{5,}", _norm_txt(f"{src['title']} {src['extracted_content']}")))
        for w in words - _SEM_STOP:
            term_domains.setdefault(w, set()).add(dom)

    corroborated_terms = sorted(
        [(term, len(doms)) for term, doms in term_domains.items() if len(doms) >= 2],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    elapsed_s = round(time.monotonic() - started, 2)
    report_lines = [
        f"=== DOSSIER DEEP RESEARCH : « {clean_main} » ===",
        f"Axes explorés en parallèle ({len(queries_list)}) : " + " | ".join(queries_list),
        f"Sources lues en profondeur : {len(enriched_sources)} domaines distincts en {elapsed_s}s",
        "Concepts corroborés par sources multiples : "
        + (", ".join(f"{t} ({c} sources)" for t, c in corroborated_terms[:10]) or "analyse directe"),
        "",
        "--- SOURCES VÉRIFIÉES & EXTRAITS PROFONDS ---",
    ]
    for src in enriched_sources:
        prices_txt = ", ".join(f"{p['value']:.0f} €" for p in src["price_points"])
        report_lines.append(
            f"\n{src['citation_tag']} {src['title']} ({src['domain']} — {src['authority_label']})"
            + (" [MARCHÉ OCCASION]" if src["is_used_market"] else "")
            + f"\nURL : {src['url']}\n"
            f"Axe : {src['matched_subquery']}\n"
            + (f"Faits clés extraits : {' ; '.join(src['key_facts'])}\n" if src["key_facts"] else "")
            + (f"Prix relevés : {prices_txt}\n" if prices_txt else "")
            + f"Contenu extrait : {src['extracted_content'][:2500]}"
        )

    def _price_stats(vals: list[float]) -> str:
        vals = sorted(vals)
        return f"min {vals[0]:.0f} € · médiane {vals[len(vals) // 2]:.0f} € · max {vals[-1]:.0f} € ({len(vals)} relevés)"

    new_prices = [p["value"] for s in enriched_sources if not s["is_used_market"] for p in s["price_points"]]
    used_prices = [p["value"] for s in enriched_sources if s["is_used_market"] for p in s["price_points"]]
    report_lines += [
        "",
        "--- PRIX RELEVÉS DANS LES SOURCES (extraction automatique, à recouper) ---",
        "Neuf : " + (_price_stats(new_prices) if new_prices else "aucun prix relevé"),
        "Occasion / reconditionné : "
        + (_price_stats(used_prices) if used_prices else "AUCUN prix d'occasion relevé dans les sources, ne rien estimer"),
    ]
    covered_queries = {s["matched_subquery"] for s in enriched_sources}
    missing_axes = [ax["pill"] for ax in human_axes if ax["query"] not in covered_queries]
    if missing_axes:
        report_lines += [
            "",
            "--- AXES SANS SOURCE (le signaler explicitement, ne rien extrapoler) ---",
            ", ".join(missing_axes),
        ]
    return {
        "status": "success",
        "verified": len(enriched_sources) > 0,
        "query": clean_main,
        "sub_queries": queries_list,
        "research_axes": human_axes,
        "sources_count": len(enriched_sources),
        "distinct_domains": len(domain_counts),
        "elapsed_seconds": elapsed_s,
        "corroborated_terms": [{"term": t, "sources_count": c} for t, c in corroborated_terms],
        "sources": enriched_sources,
        "results": enriched_sources,
        "formatted": "\n".join(report_lines),
        "errors": search_errors,
    }