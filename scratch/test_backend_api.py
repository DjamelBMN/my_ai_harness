import urllib.request
import json
import time

time.sleep(1)

def test_api():
    base = "http://127.0.0.1:8765"
    
    # 1. Test GET /api/library
    req = urllib.request.Request(f"{base}/api/library")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("GET /api/library -> OK! Item count:", len(data.get("items", [])))
        print("Counts:", data.get("counts"))

    # 2. Test GET /api/memory/persistent
    req = urllib.request.Request(f"{base}/api/memory/persistent")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("GET /api/memory/persistent -> OK! Memory items:", len(data.get("items", [])))

    # 3. Test POST /api/models/custom/add
    custom_model_payload = {
        "provider_name": "Anthropic",
        "model_name": "claude-3-7-sonnet-20250219",
        "display_name": "Claude 3.7 Sonnet (Thinking)",
        "endpoint": "https://api.anthropic.com/v1",
        "api_key": "test-key-mock",
        "context": 200000,
        "speed_tier": "Raisonnement",
        "capabilities": {
            "reasoning": True,
            "tools": True,
            "vision": True,
            "long_context": True,
            "streaming": True,
        }
    }
    req = urllib.request.Request(
        f"{base}/api/models/custom/add",
        data=json.dumps(custom_model_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("POST /api/models/custom/add -> OK! Model added:", data.get("model", {}).get("display_name"))

    # 4. Verify GET /api/models returns custom model
    req = urllib.request.Request(f"{base}/api/models")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        custom_matches = [m for m in models if "claude-3-7-sonnet" in m.get("id", "")]
        print("GET /api/models -> OK! Custom model found:", len(custom_matches) > 0)

    print("All backend tests PASSED!")

if __name__ == "__main__":
    test_api()

