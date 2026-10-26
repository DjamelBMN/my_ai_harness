from pathlib import Path

server_path = Path("ui/server.py")
content = server_path.read_text(encoding="utf-8")

old_def_start = "def is_conversational_query(prompt: str) -> bool:"
old_def_end = "    return False\r\n" if "\r\n" in content else "    return False\n"
newline = "\r\n" if "\r\n" in content else "\n"

idx_start = content.find(old_def_start)
idx_end = content.find(old_def_end, idx_start) + len(old_def_end)

new_code = (
    f"def is_conversational_query(prompt: str) -> bool:{newline}"
    f"    \"\"\"Détecte si une requête est une discussion, salutation, question ou explication{newline}"
    f"    ne devant JAMAIS générer automatiquement de fichier/PDF/document (Principe : Chat ≠ Artefact).\"\"\"{newline}"
    f"    p = (prompt or '').strip().casefold(){newline}"
    f"    if not p:{newline}"
    f"        return True{newline}"
    f"    explicit_file_triggers = ({newline}"
    f"        'fichier', 'document', 'pdf', 'docx', 'word', 'latex', '.tex', '.html',{newline}"
    f"        'sujet de bac', 'bac blanc', 'devoir maison', 'livrable', 'exporte', 'exporter',{newline}"
    f"        'crée un pdf', 'cree un pdf', 'génère un pdf', 'genere un pdf',{newline}"
    f"        'crée un exercice', 'cree un exercice', 'fais-moi un sujet', 'génère un document',{newline}"
    f"        'télécharge', 'telecharge', 'compile', 'compilation',{newline}"
    f"    ){newline}"
    f"    if any(k in p for k in explicit_file_triggers):{newline}"
    f"        return False{newline}"
    f"    return True{newline}"
)

content = content[:idx_start] + new_code + content[idx_end:]
server_path.write_text(content, encoding="utf-8")
print("Updated is_conversational_query cleanly!")

