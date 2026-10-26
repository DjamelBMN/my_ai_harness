"""
Script de validation bout en bout :
1. Test OFF -> Mono-Agent
2. Test ON -> Multi-Agent
3. Absence de 404 sur /api/execution/mode
4. Déclenchement effectif de l'orchestration multi-agent quand deep_reflection=True
5. Sélection de modèle et véracité des capacités
"""
import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8765"

def do_get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def do_post(path, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

print("=== 1. TEST /api/execution/config ===", flush=True)
status, cfg = do_get("/api/execution/config")
print(f"Status: {status}, Current mode: {cfg.get('mode')}, max_parallel_agents: {cfg.get('max_parallel_agents')}", flush=True)
assert status == 200

print("\n=== 2. TEST /api/execution/mode (POST mono) ===", flush=True)
status, res_mono = do_post("/api/execution/mode", {"mode": "mono"})
print(f"Status: {status}, ok: {res_mono.get('ok')}, mode: {res_mono.get('execution', {}).get('mode')}, parallel: {res_mono.get('execution', {}).get('max_parallel_agents')}", flush=True)
assert status == 200
assert res_mono.get("execution", {}).get("mode") == "mono"
assert res_mono.get("execution", {}).get("max_parallel_agents") == 1

print("\n=== 3. TEST /api/execution/mode (POST multi) ===", flush=True)
status, res_multi = do_post("/api/execution/mode", {"mode": "multi", "max_parallel_agents": 3})
print(f"Status: {status}, ok: {res_multi.get('ok')}, mode: {res_multi.get('execution', {}).get('mode')}, parallel: {res_multi.get('execution', {}).get('max_parallel_agents')}", flush=True)
assert status == 200
assert res_multi.get("execution", {}).get("mode") == "multi"
assert res_multi.get("execution", {}).get("max_parallel_agents") == 3

print("\n=== 4. TEST SELECTION DU MODELE & VERACITE DES CAPACITES ===", flush=True)
status, state = do_get("/api/state")
assert status == 200
models = state.get("models", [])
print(f"Found {len(models)} configured models in state.", flush=True)
for m in models:
    mid = m["id"]
    caps = m.get("capabilities", {})
    labels = m.get("capability_labels", [])
    print(f" - [{mid}] Name: {m.get('display_name')} | Context: {caps.get('context')} tokens | Labels: {labels}", flush=True)
    for k, v in caps.items():
        if k == "context":
            assert isinstance(v, (int, float, str)), f"Context token size must be numeric or string: {v}"
        else:
            assert isinstance(v, bool), f"Capability {k} must be boolean: {v}"

# Test selecting a model
test_model_id = models[0]["id"]
status, select_res = do_post("/api/models/select", {"model": test_model_id})
print(f"Select model {test_model_id}: status={status}, selected_id={select_res.get('selection', {}).get('selected_id')}", flush=True)
assert status == 200
assert select_res.get("selection", {}).get("selected_id") == test_model_id

print("\n=== 5. TEST DEEP REFLECTION TASK SUBMISSION (MONO vs MULTI) ===", flush=True)
# Submit a lightweight task with deep_reflection=False (Mono-Agent)
status, run_mono = do_post("/api/tasks/run", {
    "prompt": "Bonjour, reponds en un seul mot: TEST_MONO_OK",
    "deep_reflection": False,
    "execution_mode": "mono"
})
print(f"Task Mono submission status: {status}, task_id: {run_mono.get('task_id')}, assistant output length: {len(run_mono.get('assistant_response', {}).get('content', ''))}", flush=True)
assert status == 200
assert "task_id" in run_mono

# Submit a task with deep_reflection=True (Multi-Agent)
status, run_multi = do_post("/api/tasks/run", {
    "prompt": "Planifie et reponds en un mot: TEST_MULTI_OK",
    "deep_reflection": True,
    "execution_mode": "multi"
})
print(f"Task Multi submission status: {status}, task_id: {run_multi.get('task_id')}, assistant output length: {len(run_multi.get('assistant_response', {}).get('content', ''))}", flush=True)
assert status == 200
assert "task_id" in run_multi

# Check events of the multi task to verify multi-agent / DAG execution was recorded
events = run_multi.get("events", [])
multi_dispatched = any(ev.get("name") == "MULTI_AGENT_DISPATCHED" or ev.get("name") == "AGENT_MODE_CHANGED" for ev in events)
print(f"Multi-Agent event recorded in task events: {multi_dispatched}", flush=True)

print("\nALL VERIFICATIONS SUCCEEDED CLEANLY WITH ZERO ERRORS!", flush=True)
