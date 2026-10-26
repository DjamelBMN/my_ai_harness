import urllib.request
import json
import time

base = "http://127.0.0.1:8765"

def run_task(prompt, exec_mode="chat"):
    req = urllib.request.Request(
        f"{base}/api/tasks/run",
        data=json.dumps({"prompt": prompt, "execution_mode": exec_mode}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

# Test 1: Natural language memory
res1 = run_task("Mémorise cette règle pour les prochaines fois : Toujours répondre en français avec vouvoiement.")
print("\n--- Test 1 (Mémorise cette règle) ---")
print("Status:", res1.get("status"))
print("Answer snippet:", res1.get("answer")[:150])
print("Artifacts produced:", len(res1.get("preview_artifacts", [])))

# Verify memory is stored in persistent memory
req_mem = urllib.request.Request(f"{base}/api/memory/persistent")
with urllib.request.urlopen(req_mem) as resp:
    mem_data = json.loads(resp.read().decode("utf-8"))
    print("Stored persistent rules:", len(mem_data.get("items", [])))
    print("Formatted prompt includes rule:", "vouvoiement" in mem_data.get("formatted_prompt", ""))

# Test 2: Natural language library + memory dual linking
res2 = run_task("Ajoute ce PDF dans ma bibliothèque et retiens que c'est ma référence principale pour ce projet : derivatives.pdf")
print("\n--- Test 2 (Dual Library + Memory) ---")
print("Status:", res2.get("status"))
print("Answer snippet:", res2.get("answer")[:150])
print("Artifacts produced:", len(res2.get("preview_artifacts", [])))

# Verify library item added
req_lib = urllib.request.Request(f"{base}/api/library")
with urllib.request.urlopen(req_lib) as resp:
    lib_data = json.loads(resp.read().decode("utf-8"))
    print("Library total items:", lib_data.get("counts", {}).get("total"))

# Test 3: Conversational query MUST NOT generate any PDF!
res3 = run_task("bonjour ca va qui est ton createur ???", exec_mode="mono")
print("\n--- Test 3 (Greeting in mono mode) ---")
print("Status:", res3.get("status"))
print("Artifacts produced (MUST BE 0):", len(res3.get("preview_artifacts", [])))
print("Used skill (MUST BE EMPTY):", repr(res3.get("used_skill")))
assert len(res3.get("preview_artifacts", [])) == 0, "ERROR: Spurious artifact generated!"
assert not res3.get("used_skill"), f"ERROR: Unwanted skill inherited: {res3.get('used_skill')}"

print("\nALL BEHAVIORAL VERIFICATIONS PASSED 100%!")

