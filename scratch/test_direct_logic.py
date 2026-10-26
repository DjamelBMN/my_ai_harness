import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.server import is_conversational_query
from core.memory import MemoryManager
from core.library import LibraryManager
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry
from core.permissions import PermissionPolicy

# 1. Test is_conversational_query
conversational_prompts = [
    "bonjour ca va qui est ton createur ???",
    "salut",
    "coucou !",
    "qui es-tu ?",
    "qui t'a créé ?",
    "merci beaucoup",
    "comment ça fonctionne ?",
    "peux-tu m'expliquer ce résultat",
]
for cp in conversational_prompts:
    res = is_conversational_query(cp)
    print(f"'{cp}' -> is_conversational={res}")
    assert res is True, f"Failed for '{cp}'"

artifact_prompts = [
    "crée un devoir maison en pdf",
    "génère un exercice de maths en latex",
    "exporte le document en word docx",
    "sujet de bac blanc officiel",
    "télécharge le sujet du bac 2024",
]
for ap in artifact_prompts:
    res = is_conversational_query(ap)
    print(f"'{ap}' -> is_conversational={res}")
    assert res is False, f"Failed for '{ap}'"

# 2. Test natural language memory & library parsing
ws = Path("workspace").resolve()
fs = WorkspaceFilesystem(ws)
tools = ToolRegistry(fs, permissions=PermissionPolicy())
mem = MemoryManager(tools)
lib = LibraryManager(ws, memory_manager=mem)

# Test rule memorization
r1 = mem.parse_and_store_natural_language(
    "Mémorise cette règle pour les prochaines fois : Toujours répondre en français avec vouvoiement.",
    library_manager=lib,
)
print("\nRule memorization matched:", r1["matched"])
print("Rule content:", r1["memory_item"]["content"])
print("Rule category:", r1["memory_item"]["category"])
assert r1["memory_item"]["category"] == "rule"

# Test dual library + memory linking
r2 = mem.parse_and_store_natural_language(
    "Ajoute ce PDF dans ma bibliothèque et retiens que c'est ma référence principale pour ce projet : derivatives.pdf",
    library_manager=lib,
)
print("\nDual matched:", r2["matched"])
print("Library item created:", r2["library_item"]["title"])
print("Memory rule created:", r2["memory_item"]["content"])
print("Linked IDs:", r2["library_item"]["linked_memory_id"] == r2["memory_item"]["id"])
assert r2["library_item"]["linked_memory_id"] == r2["memory_item"]["id"]

# Verify format_for_system_prompt
sys_prompt = mem.format_for_system_prompt()
print("\nSystem prompt preview:\n", sys_prompt[:300])
assert "vouvoiement" in sys_prompt

print("\nALL UNIT MEMORY & BEHAVIORAL TESTS PASSED!")

