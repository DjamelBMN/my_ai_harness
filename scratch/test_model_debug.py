import json, os, sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.model_registry import ModelCapabilityRegistry, ModelCapabilities, ModelDescriptor

custom_models_path = Path('config/custom_models.json')
custom_raw = json.loads(custom_models_path.read_text(encoding='utf-8'))
print("Read custom_raw:", len(custom_raw))
reg = ModelCapabilityRegistry()

models = reg.list_models()
print("reg.list_models() count:", len(models))
for m in models:
    if "custom" in m.id:
        print("ModelRegistry returned:", m.id, m.display_name)

