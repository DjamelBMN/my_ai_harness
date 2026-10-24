# RÔLE DE CE FICHIER :
# Exécute les recherches locales dans le workspace et la recherche Internet réelle
# (HTTP/HTTPS via DuckDuckGo Lite, Google News RSS et l'API Wikipédia).
# Aucune source n'est jamais simulée ou inventée en cas d'échec réseau.

from __future__ import annotations

import html
import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from tools.filesystem import WORKSPACE_ROOT, WorkspaceFilesystem

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
WIKI_USER_AGENT = "NeoHarnessAI/1.0 (Local Agentic Operating Environment)"


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    unescaped = html.unescape(without_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


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
        r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*class=[\"']result-link[\"'][^>]*>(.*?)</a>",
        page,
        flags=re.S | re.I,
    )
    if not links:
        links = re.findall(
            r"<a[^>]+class=[\"']result-link[\"'][^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
            page,
            flags=re.S | re.I,
        )
    snippets = re.findall(
        r"<td[^>]+class=[\"']result-snippet[\"'][^>]*>(.*?)</td>",
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
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "source": domain or "Web",
                "published_at": "",
                "provider": "duckduckgo_lite",
            }
        )
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
        results.append(
            {
                "title": title,
                "url": link,
                "snippet": description or title,
                "source": source_name or urllib.parse.urlparse(source_url or link).netloc or "Google News",
                "published_at": pub_date,
                "provider": "google_news_rss",
            }
        )
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
        results.append(
            {
                "title": f"{raw_title} — Wikipédia",
                "url": article_url,
                "snippet": snippet,
                "source": "fr.wikipedia.org",
                "published_at": timestamp,
                "provider": "wikipedia_api",
            }
        )
    return results


def _extract_search_keywords(raw_query: str) -> str:
    """Nettoie les formules conversationnelles autour d'une requête de recherche Web."""
    text = " ".join(raw_query.strip().split())
    patterns = [
        r"^(?:/research\s+)?(?:recherche|cherche|trouve|chercher|rechercher)\s+(?:sur\s+(?:internet|le\s+web)|en\s+ligne)\s+",
        r"^(?:/research\s+)?(?:fais|effectue)\s+une\s+recherche\s+(?:web|internet)\s+(?:sur\s+)?",
        r"^(?:les\s+|des\s+)?",
    ]
    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.I).strip()
    cleaned = re.sub(
        r"\s+(?:et\s+(?:résume|resume|explique|synthétise|synthetise|analyse|donne).*)$",
        "",
        cleaned,
        flags=re.I,
    ).strip(" .?!;:")
    return cleaned or text


def web_search(
    query: str,
    max_results: int = 5,
    *,
    timeout: float = 10.0,
    backend_enabled: bool = True,
) -> dict[str, Any]:
    """Exécute une recherche Internet réelle et retourne des sources vérifiables."""
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

    lowered = cleaned_query.casefold()
    is_news_query = any(
        marker in lowered
        for marker in (
            "actualité",
            "actualite",
            "actualités",
            "actualites",
            "news",
            "aujourd'hui",
            "aujourd hui",
            "récent",
            "recent",
            "dernière",
            "derniere",
            "dernières",
            "dernieres",
            "2025",
            "2026",
        )
    )

    ddg_results: list[dict[str, Any]] = []
    news_results: list[dict[str, Any]] = []
    wiki_results: list[dict[str, Any]] = []
    errors: list[str] = []
    backends_used: list[str] = []

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

    if len(ddg_results) + len(news_results) < limit:
        try:
            wiki_results = _search_wikipedia_fr(search_terms, timeout=timeout)
            if wiki_results:
                backends_used.append("wikipedia_api")
        except Exception as error:
            errors.append(f"wikipedia_api: {type(error).__name__}: {error}")

    ordered_candidates: list[dict[str, Any]] = []
    if is_news_query:
        # Alterne actualités datées et résultats Web généraux
        max_len = max(len(news_results), len(ddg_results))
        for idx in range(max_len):
            if idx < len(news_results):
                ordered_candidates.append(news_results[idx])
            if idx < len(ddg_results):
                ordered_candidates.append(ddg_results[idx])
        ordered_candidates.extend(wiki_results)
    else:
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

    return {
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
    }


def search(query: str, workspace: str | Path = WORKSPACE_ROOT) -> str:
    """Compatibilité historique, maintenant reliée à une vraie recherche locale."""
    matches = WorkspaceFilesystem(workspace).search_files(query)
    if not matches:
        return f"Aucune occurrence de {query!r} dans le workspace."
    return "\n".join(
        f"{item['path']}:{item['line']}: {item['text']}" for item in matches
    )


def search_web(query: str, *, backend_enabled: bool = False) -> str:
    """Point d'entrée legacy exigeant un backend explicitement activé.

    Par défaut (`backend_enabled=False`), lève une `RuntimeError` explicite afin
    de préserver le contrat des tests hors-ligne vérifiant qu'aucune source n'est
    inventée sans backend configuré. Lorsque `backend_enabled=True`, délègue à
    l'outil réel `web_search`.
    """
    if not query.strip():
        raise ValueError("Une requête Web est requise.")
    if not backend_enabled:
        raise RuntimeError(
            "Aucun backend de recherche Web n'est configuré; aucune source distante "
            "n'a été consultée."
        )
    payload = web_search(query, backend_enabled=True)
    return str(payload.get("formatted", ""))
