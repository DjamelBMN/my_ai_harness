import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

def scan(filename):
    p = Path(filename)
    if not p.is_file():
        return
    text = p.read_text(encoding='utf-8')
    lines = text.splitlines()
    print(f"=== {filename} ===")
    accents = set('éèêëàâäôöûüùïîçÉÈÊËÀÂÄÔÖÛÜÙÏÎÇ«»—–’°€•…\xa0\u202f')
    count = 0
    for i, line in enumerate(lines, 1):
        found = [ch for ch in line if ord(ch) > 127 and ch not in accents]
        if found:
            count += len(found)
            hex_list = [f"U+{ord(c):04X} ({repr(c)})" for c in found]
            print(f"L{i}: {', '.join(hex_list)} -> {line.strip()[:80]}")
    print(f"Total found in {filename}: {count}\n")

scan('ui/static/index.html')
scan('ui/static/app.js')
scan('ui/static/styles.css')

