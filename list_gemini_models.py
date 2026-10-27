"""Liste les modèles Gemini utilisables avec la clé API (generateContent)."""
import os
from pathlib import Path


def _load_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env = Path(__file__).parent / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


def main() -> None:
    key = _load_key()
    if not key:
        print("GEMINI_API_KEY introuvable (variable d'environnement ou .env).")
        return
    from google import genai

    client = genai.Client(api_key=key)
    rows = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if actions and "generateContent" not in actions:
            continue
        name = (getattr(m, "name", "") or "").removeprefix("models/")
        rows.append((name, getattr(m, "display_name", "") or ""))
    for name, display in sorted(rows):
        print(f"{name:45s} {display}")
    print(f"\n{len(rows)} modèle(s) utilisable(s).")


main()