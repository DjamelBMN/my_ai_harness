# RÔLE DE CE FICHIER : commande /model. Elle lit l'état du routeur et épingle un provider sans afficher de clés.
from __future__ import annotations
import os
from providers.ollama import OllamaProvider, OllamaProviderError

ENV_KEYS={"openai":"OPENAI_API_KEY","gemini":"GEMINI_API_KEY","mistral":"MISTRAL_API_KEY","claude":"ANTHROPIC_API_KEY"}
def _family(key):
    return "gemini" if key.startswith("gemini") else key

def _status(runtime):
    router=runtime.orchestrator.router
    config=runtime.settings.get("providers",{})
    print("PROVIDER | MODÈLE | DISPONIBILITÉ | CLÉ API | ACTIF / DERNIER UTILISÉ")
    seen=set()
    for key,provider in router.providers.items():
        identity=(key,provider.get_model_name())
        if identity in seen: continue
        seen.add(identity)
        family=_family(key); env=ENV_KEYS.get(family)
        key_status="sans clé requise" if family=="ollama" else ("présente" if env and os.environ.get(env,"").strip() else "absente")
        if family == "ollama":
            try:
                provider.check_available()
                availability = "disponible (Ollama et modèle vérifiés)"
            except OllamaProviderError as error:
                availability = f"indisponible : {error}"
        elif env and not os.environ.get(env, "").strip():
            availability = "indisponible — clé API absente"
        else:
            # La clé présente et l'instance chargée ne prouvent pas que l'API
            # répond; aucun appel distant n'est déclenché par cette commande.
            availability = "configuré en session (API non sondée)"
        if not router.automatic_routing and key == router.session_provider_key:
            active = "oui (épinglé)"
        elif router.automatic_routing and key == router.last_provider_key:
            active = "dernier utilisé"
        else:
            active = "non"
        print(f"{family} | {provider.get_model_name()} | {availability} | {key_status} | {active}")
    for family in ("openai","gemini","mistral","claude","ollama"):
        if any(_family(key)==family for key in router.providers): continue
        env=ENV_KEYS.get(family); present=bool(os.environ.get(env,"").strip()) if env else False
        provider_config=config.get(family,{})
        if family=="claude": reason="provider API non connecté"
        elif family=="ollama": reason="non chargé dans cette session"
        elif not present: reason="clé API absente"
        elif not provider_config.get("enabled",False): reason="désactivé dans la configuration"
        else: reason="credentials présentes, instance non chargée"
        model=provider_config.get("model","—")
        key_status="présente" if present else "absente" if env else "non requise"
        print(f"{family} | {model} | indisponible : {reason} | {key_status} | non")
    print(f"Mode de routage : {'automatique' if router.automatic_routing else 'provider épinglé'}")
    print(f"Provider de session : {router.session_provider_key}")

def handle(runtime,mission,skill):
    parts=mission.strip().split()
    if not parts or parts[0].casefold()=="status":
        _status(runtime); return
    requested=parts[0].casefold()
    router=runtime.orchestrator.router
    if requested=="auto":
        router.enable_automatic_routing()
        print("[MODEL] Routage automatique réactivé."); return
    aliases={"gpt":"openai","openai":"openai","gemini":"gemini","mistral":"mistral","ollama":"ollama","claude":"claude"}
    family=aliases.get(requested,requested); key=family
    if key not in router.providers and family=="gemini" and "gemini_flash_lite" in router.providers:
        key="gemini_flash_lite"
    if family=="ollama" and key not in router.providers:
        options=runtime.settings.get("providers",{}).get("ollama",{})
        try:
            candidate=OllamaProvider(model=options.get("model") or OllamaProvider.DEFAULT_MODEL)
            candidate.check_available()
        except OllamaProviderError as error:
            print(f"[MODEL ERROR] Ollama indisponible : {error}"); return
        router.providers["ollama"]=candidate; key="ollama"
    if key not in router.providers:
        reason="Claude n'est pas connecté." if family=="claude" else f"{family} n'est pas disponible dans cette session."
        print(f"[MODEL ERROR] {reason} Consulte /model status."); return
    provider=router.providers[key]
    if len(parts)>1:
        model=" ".join(parts[1:])
        select=getattr(provider,"select_model",None)
        try:
            if callable(select): select(model)
            elif family=="openai":
                configured=runtime.settings.get("providers",{}).get("openai",{}).get("model")
                if model!=configured: raise ValueError("Modèle OpenAI différent du modèle configuré; modifie config/config.yaml.")
                provider.model=model
            elif family=="ollama" and hasattr(provider,"model"):
                old_model=provider.model
                provider.model=model
                provider._verified=False
                try: provider.check_available()
                except Exception:
                    provider.model=old_model
                    raise
            elif hasattr(provider,"model"): provider.model=model
            else: raise ValueError("Ce provider ne permet pas de sélectionner un modèle à chaud.")
        except Exception as error:
            print(f"[MODEL ERROR] Modèle indisponible : {type(error).__name__}: {error}"); return
    try: router.set_active_provider(key)
    except ValueError as error:
        print(f"[MODEL ERROR] {error}"); return
    print(f"[MODEL] Provider épinglé : {family} / {provider.get_model_name()}")
