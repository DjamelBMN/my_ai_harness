from pathlib import Path

content = Path("ui/static/app.js").read_text(encoding="utf-8")
for i, line in enumerate(content.splitlines(), 1):
    if "doc.type === \"docx\"" in line or "viewMode === \"word\"" in line or "word-preview" in line:
        print(f"L{i}: {line.strip()[:100]}")

