"""Vérification end-to-end du Mode Sans Agent (Chat direct) et de la synchronisation bidirectionnelle."""

import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8765"


def safe_str(val):
    return str(val).encode("ascii", errors="replace").decode("ascii")


def test_api():
    print("=== Test 1: Configuration du mode d'execution via API ===")
    
    # 1. Test POST /api/execution/mode -> multi
    req = urllib.request.Request(
        f"{BASE_URL}/api/execution/mode",
        data=json.dumps({"mode": "multi", "max_parallel_agents": 2}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Reponse mode multi:", data.get("ok"), data.get("execution", {}).get("mode"))
        assert data.get("ok") is True, "Mode multi doit reussir"
        assert data.get("execution", {}).get("mode") == "multi", "Mode doit etre multi"
        assert data.get("execution", {}).get("max_parallel_agents") == 2

    # 2. Test POST /api/execution/mode -> chat (Sans agent)
    req = urllib.request.Request(
        f"{BASE_URL}/api/execution/mode",
        data=json.dumps({"mode": "chat", "max_parallel_agents": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Reponse mode chat:", data.get("ok"), data.get("execution", {}).get("mode"))
        assert data.get("ok") is True, "Mode chat doit reussir"
        assert data.get("execution", {}).get("mode") == "chat", "Mode doit etre chat"
        assert data.get("execution", {}).get("max_parallel_agents") == 1

    # 3. Test POST /api/execution/mode -> mono (Par defaut)
    req = urllib.request.Request(
        f"{BASE_URL}/api/execution/mode",
        data=json.dumps({"mode": "mono", "max_parallel_agents": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Reponse mode mono:", data.get("ok"), data.get("execution", {}).get("mode"))
        assert data.get("ok") is True, "Mode mono doit reussir"
        assert data.get("execution", {}).get("mode") == "mono", "Mode doit etre mono"

    print("\n=== Test 2: Execution en Mode Sans Agent (Chat direct) ===")
    req = urllib.request.Request(
        f"{BASE_URL}/api/tasks/run",
        data=json.dumps({
            "prompt": "Bonjour Gemini, comment vas-tu ?",
            "execution_mode": "chat",
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Statut tache chat:", data.get("status"))
        print("Agent utilise:", safe_str(data.get("used_agent")))
        print("Verification summary:", safe_str(data.get("verification", {}).get("summary")))
        ans = data.get("answer", "")
        print("Extrait reponse chat:", safe_str(ans[:100]), "...")
        assert data.get("status") in {"Termine", "completed", "Termin\u00e9"}
        assert "Sans agent" in data.get("used_agent", "")
        assert len(data.get("used_tools", [])) == 0, "Aucun outil ne doit etre injecte en mode chat direct"

    print("\n=== Test 3: Verification de l'etat complet de l'UI (/api/state) ===")
    req = urllib.request.Request(f"{BASE_URL}/api/state")
    with urllib.request.urlopen(req) as resp:
        st = json.loads(resp.read().decode("utf-8"))
        exec_st = st.get("execution", {})
        print("Etat d'execution expose a l'UI:", exec_st.get("mode"), "Max agents:", exec_st.get("max_parallel_agents"))
        assert "mode" in exec_st
        assert "max_parallel_agents" in exec_st

    print("\n=== Test 4: Re-bascule en Mode Mono-Agent par defaut ===")
    req = urllib.request.Request(
        f"{BASE_URL}/api/execution/mode",
        data=json.dumps({"mode": "mono", "max_parallel_agents": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("execution", {}).get("mode") == "mono"
        print("Re-bascule reussie en mode:", data.get("execution", {}).get("mode"))

    print("\n[OK] TOUS LES TESTS E2E (Multi / Chat direct / Mono) ONT REUSSI !")


if __name__ == "__main__":
    test_api()

