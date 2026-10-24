# RÔLE DE CE FICHIER : exporte le dernier résultat dans le workspace après autorisation.
from __future__ import annotations
import html,textwrap
from io import BytesIO
from zipfile import ZIP_DEFLATED,ZipFile
from core.permissions import RiskLevel

def _latex(text):
    replacements={"\\":r"\textbackslash{}","&":r"\&","%":r"\%","$":r"\$","#":r"\#","_":r"\_","{":r"\{","}":r"\}","~":r"\textasciitilde{}","^":r"\textasciicircum{}"}
    body="\n".join(" \\\\ ".join("".join(replacements.get(c,c) for c in line) for line in paragraph.splitlines()) for paragraph in text.split("\n\n"))
    return "\\documentclass{article}\n\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n\\usepackage[margin=2cm]{geometry}\n\\begin{document}\n"+body+"\n\\end{document}\n"

def _docx(text):
    paragraphs="".join('<w:p><w:r><w:t xml:space="preserve">'+html.escape(line,quote=False)+'</w:t></w:r></w:p>' for line in (text.splitlines() or [""]))
    document='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+paragraphs+'<w:sectPr/></w:body></w:document>'
    types='<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels='<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    output=BytesIO()
    with ZipFile(output,"w",ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",types); archive.writestr("_rels/.rels",rels); archive.writestr("word/document.xml",document)
    return output.getvalue()

def _pdf(text):
    import fitz
    lines=[]
    for line in text.splitlines() or [""]: lines.extend(textwrap.wrap(line,width=96,break_long_words=True) or [""])
    doc=fitz.open()
    for start in range(0,max(len(lines),1),48):
        page=doc.new_page(); page.insert_text((48,48),"\n".join(lines[start:start+48]),fontsize=10,fontname="helv")
    data=doc.tobytes(); doc.close(); return data

def handle(runtime,mission,skill):
    fmt=mission.strip().casefold().split(maxsplit=1)[0] if mission.strip() else ""
    if fmt not in {"markdown","md","latex","tex","pdf","docx"}:
        print("Utilisation : /export pdf|docx|latex|markdown"); return
    source=runtime.orchestrator.context.last_result
    if not source.strip(): print("[EXPORT ERROR] Aucun résultat précédent à exporter."); return
    filesystem=runtime.agent_loop.tools.filesystem
    if filesystem.contains_secret_text(source):
        print("[EXPORT ERROR] Le résultat semble contenir un secret; export refusé."); return
    if fmt in {"markdown","md"}: payload=source.encode("utf-8"); extension="md"
    elif fmt in {"latex","tex"}: payload=_latex(source).encode("utf-8"); extension="tex"
    elif fmt=="docx": payload=_docx(source); extension="docx"
    else:
        try: payload=_pdf(source); extension="pdf"
        except ImportError: print("[EXPORT ERROR] PyMuPDF absent; installe les dépendances du projet."); return
    try:
        relative=next(f"exports/last_result_{i:03d}.{extension}" for i in range(1,10000) if not filesystem.resolve(f"exports/last_result_{i:03d}.{extension}").exists())
    except StopIteration: print("[EXPORT ERROR] Aucun nom de fichier disponible."); return
    allowed,reason=runtime.agent_loop.tools.permissions.authorize("write_file",RiskLevel.MODERATE,True)
    if not allowed: print(f"[EXPORT REFUSÉ] {reason}"); return
    try:
        result=filesystem.write_bytes(relative,payload); written=filesystem.read_bytes(relative)
    except Exception as error: print(f"[EXPORT ERROR] {type(error).__name__}: {error}"); return
    if len(written)!=len(payload): print("[EXPORT ERROR] Taille incorrecte après écriture."); return
    print(f"[EXPORT OK] {result['path']} | {result['bytes']} octets | SHA-256 {result['sha256']}")
