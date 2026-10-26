# RÔLE DE CE FICHIER :
# Registre déclaratif et vérifié des capacités réelles des providers et modèles
# du projet NeoHarness AI. N'altère aucun contrat existant de ModelRouter ou BaseProvider.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any

from core.router import ModelRouter, load_config
from providers.claude import ClaudeProvider
from providers.gemini import GeminiProvider
from providers.local import LocalProvider
from providers.mistral import MistralProvider
from providers.ollama import OllamaProvider, OllamaProviderError
from providers.openai import OpenAIProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUSTOM_MODELS_PATH = PROJECT_ROOT / "config" / "custom_models.json"


ENV_KEYS_BY_FAMILY: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


@dataclass
class ModelCapabilities:
    reasoning: bool = False
    tools: bool = False
    vision: bool = False
    long_context: bool = False
    structured_output: bool = False
    streaming: bool = False
    web_grounding: bool = False
    temperature: bool = False
    max_output_tokens: bool = False
    context: int | str = "Non disponible"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def enabled_labels(self) -> list[str]:
        labels: list[str] = []
        if self.vision:
            labels.append("Vision")
        if self.long_context:
            labels.append("Long Context")
        if self.tools:
            labels.append("Function Calling")
        if self.structured_output:
            labels.append("Structured Output")
        if self.web_grounding:
            labels.append("Google Search Grounding")
        if self.streaming:
            labels.append("Streaming")
        if self.reasoning:
            labels.append("Raisonnement")
        return labels


@dataclass
class ModelDescriptor:
    id: str
    model_name: str
    display_name: str
    provider_key: str
    provider_family: str
    provider_class: str
    speed_tier: str
    status: str
    status_label: str
    status_detail: str
    connected: bool
    configured_in_session: bool
    api_key_env: str | None
    api_key_present: bool | None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    supported_parameters: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = self.capabilities.to_dict()
        payload["capability_labels"] = self.capabilities.enabled_labels()
        return payload


class ModelCapabilityRegistry:
    """Expose l'état réel et les capacités explicites des modèles du projet."""

    def __init__(
        self,
        router: ModelRouter | None = None,
        settings: dict[str, Any] | None = None,
        config_path: str | Path = "config/config.yaml",
    ) -> None:
        self.router = router
        if settings is not None:
            self.settings = settings
        else:
            try:
                self.settings = load_config(config_path)
            except Exception:
                self.settings = {}

    @staticmethod
    def _family_for_key(key: str) -> str:
        lowered = key.strip().casefold()
        if lowered.startswith("gemini"):
            return "gemini"
        if lowered.startswith("openai") or lowered.startswith("gpt"):
            return "openai"
        if lowered.startswith("mistral"):
            return "mistral"
        if lowered.startswith("ollama") or lowered.startswith("qwen"):
            return "ollama"
        if lowered.startswith("claude"):
            return "claude"
        if lowered.startswith("local"):
            return "local"
        return lowered

    @staticmethod
    def _capabilities_for(family: str, model_name: str) -> tuple[ModelCapabilities, list[str], str]:
        """Retourne uniquement les capacités réellement implémentées par le provider Python."""
        lowered_model = model_name.strip().casefold()
        if family == "gemini":
            is_lite = "lite" in lowered_model
            caps = ModelCapabilities(
                reasoning=True,
                tools=True,
                vision=True,
                long_context=True,
                structured_output=True,
                streaming=True,
                web_grounding=True,
                temperature=True,
                max_output_tokens=True,
                context=1048576,
            )
            params = ["temperature", "max_output_tokens"]
            speed = "Ultra-rapide" if is_lite else "Rapide"
            return caps, params, speed

        if family == "openai":
            caps = ModelCapabilities(
                reasoning=True,
                tools=True,
                vision=False,
                long_context=True,
                structured_output=False,
                streaming=False,
                web_grounding=False,
                temperature=False,
                max_output_tokens=True,
                context=128000,
            )
            params = ["max_output_tokens"]
            return caps, params, "Équilibré"

        if family == "mistral":
            caps = ModelCapabilities(
                reasoning=True,
                tools=True,
                vision=False,
                long_context=False,
                structured_output=False,
                streaming=False,
                web_grounding=False,
                temperature=True,
                max_output_tokens=True,
                context=32000,
            )
            params = ["max_output_tokens"]
            return caps, params, "Rapide"

        if family == "ollama":
            caps = ModelCapabilities(
                reasoning=True,
                tools=True,
                vision=False,
                long_context=False,
                structured_output=False,
                streaming=False,
                web_grounding=False,
                temperature=True,
                max_output_tokens=True,
                context=32768,
            )
            params = ["max_output_tokens"]
            return caps, params, "Local"

        # Providers non connectés (ClaudeProvider / LocalProvider)
        caps = ModelCapabilities(
            reasoning=False,
            tools=False,
            vision=False,
            long_context=False,
            structured_output=False,
            streaming=False,
            web_grounding=False,
            temperature=False,
            max_output_tokens=False,
            context="Non configuré",
        )
        return caps, [], "Non connecté"

    def _provider_status(
        self,
        family: str,
        provider_key: str,
        model_name: str,
        *,
        probe_ollama: bool = False,
    ) -> tuple[str, str, str, bool, bool, str | None, bool | None]:
        router_providers = self.router.providers if self.router is not None else {}
        in_session = provider_key in router_providers
        provider_instance = router_providers.get(provider_key)
        env_var = ENV_KEYS_BY_FAMILY.get(family)
        has_key = bool(os.environ.get(env_var, "").strip()) if env_var else None

        if family in {"claude", "local"} or isinstance(
            provider_instance, (ClaudeProvider, LocalProvider)
        ):
            return (
                "non_connecte",
                "Non connecté",
                (
                    "ClaudeProvider est un squelette préparé non relié à l'API Claude."
                    if family == "claude"
                    else "LocalProvider est un squelette préparé non configuré."
                ),
                False,
                in_session,
                env_var,
                has_key,
            )

        if family == "ollama":
            if in_session and probe_ollama and isinstance(provider_instance, OllamaProvider):
                try:
                    provider_instance.check_available()
                    return (
                        "disponible",
                        "Disponible (Local)",
                        f"Serveur Ollama local et modèle {model_name} vérifiés.",
                        True,
                        True,
                        None,
                        None,
                    )
                except OllamaProviderError as error:
                    return (
                        "indisponible",
                        "Serveur local arrêté",
                        str(error),
                        False,
                        True,
                        None,
                        None,
                    )
            if in_session:
                return (
                    "disponible",
                    "Chargé en session",
                    f"Ollama ({model_name}) chargé dans le routeur local.",
                    True,
                    True,
                    None,
                    None,
                )
            return (
                "configure",
                "Configuré (Local)",
                f"Modèle local {model_name} déclaré dans config.yaml (session non active).",
                True,
                False,
                None,
                None,
            )

        providers_cfg = self.settings.get("providers", {})
        family_cfg = providers_cfg.get(family, {}) if isinstance(providers_cfg, dict) else {}
        enabled_cfg = bool(family_cfg.get("enabled", True))

        if in_session and has_key:
            return (
                "disponible",
                "Disponible",
                f"Instance {family} chargée en session et {env_var} présente.",
                True,
                True,
                env_var,
                True,
            )
        if in_session and not has_key:
            return (
                "cle_absente",
                "Clé API absente",
                f"Provider chargé en session mais la variable {env_var} est absente.",
                True,
                True,
                env_var,
                False,
            )
        if has_key and enabled_cfg:
            return (
                "disponible",
                "Prêt (Clé présente)",
                f"{env_var} détectée et provider activé dans config/config.yaml.",
                True,
                False,
                env_var,
                True,
            )
        if not enabled_cfg:
            return (
                "desactive",
                "Désactivé",
                f"Désactivé dans config/config.yaml (enabled: false).",
                False,
                False,
                env_var,
                has_key,
            )
        return (
            "cle_requise",
            "Configuré (Clé requise)",
            f"Déclaré dans config/config.yaml ; renseigne {env_var} pour appeler l'API distante.",
            True,
            False,
            env_var,
            False,
        )

    def list_models(self, *, probe_ollama: bool = False) -> list[ModelDescriptor]:
        descriptors: list[ModelDescriptor] = []
        seen_ids: set[str] = set()
        providers_cfg = self.settings.get("providers", {})
        if not isinstance(providers_cfg, dict):
            providers_cfg = {}
        routing_cfg = self.settings.get("routing", {})
        if not isinstance(routing_cfg, dict):
            routing_cfg = {}

        router_providers = self.router.providers if self.router is not None else {}

        def _add_entry(
            entry_id: str,
            model_name: str,
            display_name: str,
            provider_key: str,
            family: str,
            provider_class: str,
            aliases: list[str],
        ) -> None:
            if entry_id in seen_ids:
                return
            seen_ids.add(entry_id)
            caps, params, speed = self._capabilities_for(family, model_name)
            (
                status,
                status_label,
                status_detail,
                connected,
                in_session,
                env_var,
                has_key,
            ) = self._provider_status(
                family,
                provider_key,
                model_name,
                probe_ollama=probe_ollama,
            )
            descriptors.append(
                ModelDescriptor(
                    id=entry_id,
                    model_name=model_name,
                    display_name=display_name,
                    provider_key=provider_key,
                    provider_family=family,
                    provider_class=provider_class,
                    speed_tier=speed,
                    status=status,
                    status_label=status_label,
                    status_detail=status_detail,
                    connected=connected,
                    configured_in_session=in_session,
                    api_key_env=env_var,
                    api_key_present=has_key,
                    capabilities=caps,
                    supported_parameters=params,
                    aliases=[alias.casefold() for alias in aliases],
                )
            )

        # 1. Gemini Flash (principal configuré)
        gemini_cfg = providers_cfg.get("gemini", {}) if isinstance(providers_cfg.get("gemini"), dict) else {}
        gemini_provider = router_providers.get("gemini")
        gemini_model = (
            gemini_provider.get_model_name()
            if isinstance(gemini_provider, GeminiProvider) and gemini_provider.model
            else str(gemini_cfg.get("model") or "gemini-3.6-flash")
        )
        _add_entry(
            entry_id="gemini",
            model_name=gemini_model,
            display_name=f"Gemini Flash ({gemini_model})",
            provider_key="gemini",
            family="gemini",
            provider_class="GeminiProvider",
            aliases=[
                "gemini",
                "gemini flash",
                "gemini-flash",
                gemini_model,
                "gemini 3.8 flash",
            ],
        )

        # 2. Gemini Flash Lite (route simple dans config.yaml)
        lite_model = str(routing_cfg.get("simple") or "gemini-3.5-flash-lite")
        if "gemini" in lite_model.casefold():
            lite_key = "gemini_flash_lite" if "gemini_flash_lite" in router_providers else "gemini"
            _add_entry(
                entry_id="gemini_flash_lite",
                model_name=lite_model,
                display_name=f"Gemini Flash Lite ({lite_model})",
                provider_key=lite_key,
                family="gemini",
                provider_class="GeminiProvider",
                aliases=[
                    "gemini_flash_lite",
                    "gemini flash lite",
                    "gemini-flash-lite",
                    lite_model,
                ],
            )

        # Modèles Gemini supplémentaires éventuellement découverts en session
        if isinstance(gemini_provider, GeminiProvider):
            for discovered_id, discovered_name in getattr(gemini_provider, "_available_models", {}).items():
                if discovered_id not in {gemini_model, lite_model}:
                    _add_entry(
                        entry_id=f"gemini:{discovered_id}",
                        model_name=discovered_id,
                        display_name=f"{discovered_name} ({discovered_id})",
                        provider_key="gemini",
                        family="gemini",
                        provider_class="GeminiProvider",
                        aliases=[discovered_id, discovered_name],
                    )

        # 3. OpenAI (GPT-5-mini)
        openai_cfg = providers_cfg.get("openai", {}) if isinstance(providers_cfg.get("openai"), dict) else {}
        openai_provider = router_providers.get("openai")
        openai_model = (
            openai_provider.model
            if isinstance(openai_provider, OpenAIProvider)
            else str(openai_cfg.get("model") or self.settings.get("openai", {}).get("model") or "gpt-5-mini")
        )
        _add_entry(
            entry_id="openai",
            model_name=openai_model,
            display_name=f"GPT-5-mini ({openai_model})" if openai_model == "gpt-5-mini" else f"OpenAI ({openai_model})",
            provider_key="openai",
            family="openai",
            provider_class="OpenAIProvider",
            aliases=["openai", "gpt", "gpt-5-mini", "gpt-5", openai_model],
        )

        # 4. Mistral (mistral-small-latest)
        mistral_cfg = providers_cfg.get("mistral", {}) if isinstance(providers_cfg.get("mistral"), dict) else {}
        mistral_provider = router_providers.get("mistral")
        mistral_model = (
            mistral_provider.model
            if isinstance(mistral_provider, MistralProvider) and mistral_provider.model
            else str(mistral_cfg.get("model") or "mistral-small-latest")
        )
        _add_entry(
            entry_id="mistral",
            model_name=mistral_model,
            display_name=f"Mistral Small ({mistral_model})",
            provider_key="mistral",
            family="mistral",
            provider_class="MistralProvider",
            aliases=["mistral", "mistral small", mistral_model],
        )

        # 5. Ollama (qwen3:1.7b)
        ollama_cfg = providers_cfg.get("ollama", {}) if isinstance(providers_cfg.get("ollama"), dict) else {}
        ollama_provider = router_providers.get("ollama")
        ollama_model = (
            ollama_provider.model
            if isinstance(ollama_provider, OllamaProvider)
            else str(ollama_cfg.get("model") or OllamaProvider.DEFAULT_MODEL)
        )
        _add_entry(
            entry_id="ollama",
            model_name=ollama_model,
            display_name=f"Ollama / Qwen3 ({ollama_model})",
            provider_key="ollama",
            family="ollama",
            provider_class="OllamaProvider",
            aliases=["ollama", "qwen", "qwen3", ollama_model],
        )

        # 6. Claude (Squelette non connecté présent dans providers/claude.py)
        _add_entry(
            entry_id="claude",
            model_name="Claude",
            display_name="Claude (Non connecté)",
            provider_key="claude",
            family="claude",
            provider_class="ClaudeProvider",
            aliases=["claude", "anthropic"],
        )

        # 7. Autres providers éventuellement injectés dans router.providers (tests/custom)
        for key, provider in router_providers.items():
            if key not in seen_ids and not any(d.provider_key == key for d in descriptors):
                family = self._family_for_key(key)
                m_name = provider.get_model_name()
                _add_entry(
                    entry_id=key,
                    model_name=m_name,
                    display_name=f"{provider.get_name()} ({m_name})",
                    provider_key=key,
                    family=family,
                    provider_class=provider.get_name(),
                    aliases=[key, m_name],
                )

        # 6. Modèles personnalisés ajoutés manuellement par l'utilisateur (config/custom_models.json)
        custom_models_path = CUSTOM_MODELS_PATH
        if custom_models_path.is_file():
            try:
                custom_raw = json.loads(custom_models_path.read_text(encoding="utf-8"))
                if isinstance(custom_raw, list):
                    for cm in custom_raw:
                        if isinstance(cm, dict) and cm.get("model_name"):
                            m_id = cm.get("id") or f"custom:{cm['model_name']}"
                            if m_id in seen_ids:
                                continue
                            seen_ids.add(m_id)
                            m_name = str(cm["model_name"]).strip()
                            prov_name = str(cm.get("provider_name") or "Personnalisé").strip()
                            disp_name = str(cm.get("display_name") or f"{prov_name} {m_name}").strip()
                            fam = self._family_for_key(str(cm.get("provider_family") or prov_name))
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
                            
                            descriptors.append(
                                ModelDescriptor(
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
                            )
            except Exception:
                pass

        return descriptors

    def resolve_model(self, identifier: str | None) -> ModelDescriptor | None:
        if not identifier:
            return None
        needle = identifier.strip().casefold()
        if needle == "auto":
            return None
        models = self.list_models()
        for descriptor in models:
            if (
                needle == descriptor.id.casefold()
                or needle == descriptor.model_name.casefold()
                or needle == descriptor.display_name.casefold()
                or needle in descriptor.aliases
            ):
                return descriptor
        for descriptor in models:
            if needle in descriptor.display_name.casefold() or needle in descriptor.model_name.casefold():
                return descriptor
        return None

    def active_selection_summary(self) -> dict[str, Any]:
        models = self.list_models()
        if self.router is None:
            default_desc = self.resolve_model("gemini") or (models[0] if models else None)
            return {
                "mode": "auto",
                "selected_id": "auto",
                "effective_model": default_desc.to_dict() if default_desc else None,
            }

        if self.router.automatic_routing:
            last_key = self.router.last_provider_key or self.router.session_provider_key or self.router.default_provider
            effective = self.resolve_model(last_key) or self.resolve_model("gemini") or (models[0] if models else None)
            return {
                "mode": "auto",
                "selected_id": "auto",
                "last_provider_key": last_key,
                "effective_model": effective.to_dict() if effective else None,
            }

        pinned_key = self.router.session_provider_key or self.router.default_provider
        pinned = self.resolve_model(pinned_key) or (models[0] if models else None)
        return {
            "mode": "manual",
            "selected_id": pinned.id if pinned else pinned_key,
            "last_provider_key": self.router.last_provider_key,
            "effective_model": pinned.to_dict() if pinned else None,
        }
