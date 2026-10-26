import json, os, sys, traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.model_registry import ModelCapabilityRegistry, ModelCapabilities, ModelDescriptor

custom_models_path = Path('config/custom_models.json')
custom_raw = json.loads(custom_models_path.read_text(encoding='utf-8'))
reg = ModelCapabilityRegistry()
seen_ids = set()

for cm in custom_raw:
    try:
        m_id = cm.get("id") or f"custom:{cm['model_name']}"
        m_name = str(cm["model_name"]).strip()
        prov_name = str(cm.get("provider_name") or "Personnalisé").strip()
        disp_name = str(cm.get("display_name") or f"{prov_name} {m_name}").strip()
        fam = reg._family_for_key(str(cm.get("provider_family") or prov_name))
        p_key = cm.get("provider_key") or f"custom_{fam}_{m_name.replace('-', '_').replace('.', '_')}"
        
        caps_dict = cm.get("capabilities", {}) if isinstance(cm.get("capabilities"), dict) else {}
        caps = ModelCapabilities(
            reasoning=bool(caps_dict.get("reasoning", True)),
            tools=bool(caps_dict.get("tools", True)),
            vision=bool(caps_dict.get("vision", False)),
            long_context=bool(caps_dict.get("long_context", True)),
            structured_output=bool(caps_dict.get("structured_output", False)),
            streaming=bool(caps_dict.get("streaming", True)),
            web_grounding=bool(caps_dict.get("web_grounding", False)),
            temperature=bool(caps_dict.get("temperature", True)),
            max_output_tokens=bool(caps_dict.get("max_output_tokens", True)),
            context=cm.get("context") or 128000,
        )
        speed = cm.get("speed_tier") or "Équilibré"
        has_key = bool(cm.get("api_key") or os.environ.get(f"{fam.upper()}_API_KEY", ""))
        
        desc = ModelDescriptor(
            id=m_id,
            model_name=m_name,
            display_name=disp_name,
            provider_key=p_key,
            provider_family=fam,
            provider_class=f"{prov_name}Provider",
            speed_tier=speed,
            status="disponible" if has_key else "cle_requise",
            status_label="Prêt (Personnalisé)" if has_key else "Clé requise",
            status_detail=f"Modèle LLM extensible (Endpoint: {cm.get('endpoint') or 'API Standard'}, Contexte: {cm.get('context') or 128000} tokens).",
            connected=has_key,
            configured_in_session=True,
            api_key_env=cm.get("api_key_env") or f"{fam.upper()}_API_KEY",
            api_key_present=has_key,
            capabilities=caps,
            supported_parameters=["temperature", "max_output_tokens"],
            aliases=[m_id.casefold(), m_name.casefold(), disp_name.casefold(), prov_name.casefold()],
        )
        print("Successfully created desc:", desc.id)
    except Exception as e:
        traceback.print_exc()

