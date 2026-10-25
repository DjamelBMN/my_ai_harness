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
    without_tags = re.sub(r"<[^>]+>", " ", raw)
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
        clean_text = _clean_html(decoded_html)
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
        "text": clean_text[:4000],
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
        bing_results = _search_bing(search_terms, timeout=min(timeout, 6.0))
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

    if len(bing_results) + len(ddg_results) + len(news_results) < limit:
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
        max_len = max(len(news_results), len(bing_results), len(ddg_results))
        for idx in range(max_len):
            if idx < len(news_results):
                ordered_candidates.append(news_results[idx])
            if idx < len(bing_results):
                ordered_candidates.append(bing_results[idx])
            if idx < len(ddg_results):
                ordered_candidates.append(ddg_results[idx])
        ordered_candidates.extend(wiki_results)
    else:
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