import re
import urllib.parse
import urllib.request

from tools.search import _clean_html, _search_bing

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
BASE = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"}
FULL = dict(BASE, **{
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
})
COOKIE = {"Cookie": "SRCHHPGUSR=SRCHLANG=fr&ADLT=MODERATE; _EDGE_S=F=1;"}

VARIANTS = {
    "A minimal (UA + langue)": BASE,
    "B + Accept + Sec-Fetch, SANS cookie": FULL,
    "C + Accept + Sec-Fetch + cookie (= ton code)": dict(FULL, **COOKIE),
}


def titles(headers, q):
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&cc=fr&setlang=fr"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        page = r.read().decode("utf-8", errors="replace")
    blocks = re.findall(r'<li[^>]*class=["\'][^"\']*b_algo[^"\']*["\'][^>]*>(.*?)</li>', page, re.S | re.I)
    out = []
    for b in blocks[:3]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*>(.*?)</a>', b, re.S | re.I)
        out.append(_clean_html(m.group(1))[:70] if m else "?")
    return len(blocks), out


q = "bactador anti odeur"
for name, h in VARIANTS.items():
    n, t = titles(h, q)
    print(f"\n[{name}] {n} blocs")
    for x in t:
        print("   -", x)

print("\n[_search_bing réel]")
for r in _search_bing(q)[:3]:
    print("   -", r["title"][:70], "|", r["url"][:60])