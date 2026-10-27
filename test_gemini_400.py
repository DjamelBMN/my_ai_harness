import os, re
from pathlib import Path


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    env = Path(".env")
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return ""


from google import genai
from google.genai import types

client = genai.Client(api_key=_key())
MODEL = "gemini-3.5-flash-lite"
tests = {
    "sans config": None,
    "thinking_budget=0": types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    ),
    "timeout 25s seul": types.GenerateContentConfig(
        http_options=types.HttpOptions(timeout=25_000)
    ),
    "timeout + thinking_budget=0": types.GenerateContentConfig(
        http_options=types.HttpOptions(timeout=25_000),
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    ),
}
for name, cfg in tests.items():
    try:
        kwargs = {"model": MODEL, "contents": "Réponds uniquement : ok"}
        if cfg is not None:
            kwargs["config"] = cfg
        r = client.models.generate_content(**kwargs)
        print(f"[OK ] {name}: {(r.text or '').strip()[:40]!r}")
    except Exception as e:
        msg = re.sub(r"AIza[0-9A-Za-z_\-]+", "***", str(e))
        print(f"[ERR] {name}: {msg[:300]}")