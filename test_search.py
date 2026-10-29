import urllib.request
import urllib.parse

q = urllib.parse.quote("bactador anti odeur")
ua = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/128.0",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

urls = [
    ("Brave", "https://search.brave.com/search?q=" + q),
    ("Startpage", "https://www.startpage.com/do/dsearch?query=" + q),
    ("DDG_HTML", "https://html.duckduckgo.com/html/?q=" + q),
    ("Mojeek", "https://www.mojeek.com/search?q=" + q),
    ("Ecosia", "https://www.ecosia.org/search?q=" + q),
]

for name, url in urls:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode("utf-8", "ignore")
        count = html.lower().count("bactador")
        print(f"{name:10} -> taille={len(html)} | occurrences de bactador={count}")
    except Exception as exc:
        print(f"{name:10} -> ERREUR: {exc}")
