# RÔLE DE CE FICHIER :
# Lit la configuration et choisit le provider LLM adapté à un agent. Il ne crée ni
# agent ni modèle : il retourne une instance de provider déjà enregistrée.
# Intègre le RateLimitManager pour réguler l'ensemble des appels LLM du système.

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from core.rate_limit_manager import RateLimitManager, is_free_tier_provider
from providers.base_provider import BaseProvider


def load_config(path: str | Path) -> dict:
    """Lit le sous-ensemble YAML ou le fichier complet utilisé dans config/config.yaml."""
    settings: dict[str, Any] = {
        "default_provider": "ollama",
        "providers": {
            "fallback_enabled": True,
            "cooldown_after_429": 60,
        },
        "agents": {},
        "routing": {},
        "execution": {
            "mode": "mono",
            "max_parallel_agents": 1,
        },
        "profiles": {
            "free": {
                "mode": "mono",
                "max_parallel_agents": 1,
                "max_retries": 3,
                "backoff": True,
                "circuit_breaker": True,
                "fallback_enabled": False,
                "cooldown_after_429": 60,
            },
            "balanced": {
                "mode": "multi",
                "max_parallel_agents": 2,
                "max_retries": 3,
                "backoff": True,
                "circuit_breaker": True,
                "fallback_enabled": True,
                "cooldown_after_429": 45,
            },
            "powerful": {
                "mode": "multi",
                "max_parallel_agents": 4,
                "max_retries": 4,
                "backoff": True,
                "circuit_breaker": True,
                "fallback_enabled": True,
                "cooldown_after_429": 30,
            },
        },
        "features": {
            "closed_loop_tdd": False,
            "independent_critic": False,
            "backtracking": False,
            "reflective_memory": False,
            "dynamic_browser": False,
            "multi_agent_hierarchy": False,
            "compile_autofix": False,
            "live_activity_panel": False,
            "math_tikz_figures": False,
        },
    }

    raw_text = Path(path).read_text(encoding="utf-8-sig")

    # Tentative de parsing via PyYAML si disponible
    try:
        import yaml
        parsed = yaml.safe_load(raw_text)
        if isinstance(parsed, dict):
            if "default_provider" in parsed and parsed["default_provider"]:
                settings["default_provider"] = str(parsed["default_provider"]).strip().lower()
            if "openai" in parsed and isinstance(parsed["openai"], dict):
                settings["providers"]["openai"] = dict(parsed["openai"])
            if "providers" in parsed and isinstance(parsed["providers"], dict):
                for pk, pv in parsed["providers"].items():
                    if isinstance(pv, dict):
                        settings["providers"][pk.lower()] = pv
                    elif pk in ("fallback_enabled", "cooldown_after_429"):
                        settings["providers"][pk] = pv
            if "agents" in parsed and isinstance(parsed["agents"], dict):
                for ak, av in parsed["agents"].items():
                    if isinstance(av, dict):
                        settings["agents"][ak.lower()] = {k.lower(): str(v).lower() for k, v in av.items()}
            if "routing" in parsed and isinstance(parsed["routing"], dict):
                for rk, rv in parsed["routing"].items():
                    settings["routing"][str(rk).lower()] = str(rv).lower()
            if "features" in parsed and isinstance(parsed["features"], dict):
                for fk, fv in parsed["features"].items():
                    settings["features"][str(fk).lower()] = bool(fv)
            if "execution" in parsed and isinstance(parsed["execution"], dict):
                settings["execution"].update(parsed["execution"])
            if "profiles" in parsed and isinstance(parsed["profiles"], dict):
                settings["profiles"].update(parsed["profiles"])
            return settings
    except Exception:
        pass

    # Parser de secours ligne par ligne pour environnements sans PyYAML
    section = None
    current_name = None

    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if section == "routing" and indent == 2:
            key, separator, value = stripped.rpartition(":")
        else:
            key, separator, value = stripped.partition(":")
        if not separator:
            continue

        if indent == 0:
            current_name = None
            if value.strip():
                if key == "default_provider":
                    settings["default_provider"] = value.strip().lower()
            else:
                section = key
                if section == "openai":
                    settings["providers"]["openai"] = {}
                    current_name = "openai"
            continue

        if section == "openai" and indent == 2 and current_name == "openai":
            option_value = value.strip()
            if key == "enabled" and option_value.lower() in {"true", "false"}:
                settings["providers"]["openai"][key] = (option_value.lower() == "true")
            elif key == "model" and option_value:
                settings["providers"]["openai"][key] = option_value.strip('"').strip("'")
        elif section == "providers" and indent == 2:
            current_name = key.lower()
            if value.strip():
                if key == "fallback_enabled":
                    settings["providers"]["fallback_enabled"] = (value.strip().lower() == "true")
                elif key == "cooldown_after_429":
                    settings["providers"]["cooldown_after_429"] = float(value.strip())
            else:
                settings["providers"][current_name] = {}
        elif section == "providers" and indent >= 4 and current_name:
            option_value = value.strip()
            if key == "enabled" and option_value.lower() in {"true", "false"}:
                settings["providers"][current_name][key] = (option_value.lower() == "true")
            elif key == "model" and option_value:
                settings["providers"][current_name][key] = option_value.strip('"').strip("'")
        elif section == "execution" and indent == 2:
            val = value.strip().lower()
            if key == "mode":
                settings["execution"]["mode"] = val
            elif key == "max_parallel_agents":
                try:
                    settings["execution"]["max_parallel_agents"] = int(val)
                except ValueError:
                    pass
        elif section == "agents" and indent == 2:
            current_name = key.lower()
            settings["agents"][current_name] = {}
        elif section == "agents" and indent >= 4 and current_name:
            if key == "provider" and value.strip():
                settings["agents"][current_name][key] = value.strip().lower()
        elif section == "routing" and indent == 2 and value.strip():
            settings["routing"][key.lower()] = value.strip().lower()
        elif section == "features" and indent == 2 and value.strip():
            settings["features"][key.lower()] = (value.strip().lower() == "true")

    return settings


class ModelRouter:
    """Choisit un provider pour une clé d'agent, sans dépendre d'un agent concret.

    Régule tous les appels via le RateLimitManager central.
    """

    def __init__(
        self,
        providers: Mapping[str, BaseProvider],
        agent_provider_map: Mapping[str, str],
        default_provider: str = "ollama",
        task_provider_map: Mapping[str, str] | None = None,
        rate_limit_manager: RateLimitManager | None = None,
        execution_config: dict[str, Any] | None = None,
    ) -> None:
        self.providers = {name.lower(): provider for name, provider in providers.items()}
        self.agent_provider_map = {
            name.lower(): provider_name.lower()
            for name, provider_name in agent_provider_map.items()
        }
        self.default_provider = default_provider.lower()
        self.task_provider_map = {
            key.strip().lower(): provider_name.strip().lower()
            for key, provider_name in (task_provider_map or {}).items()
        }
        self.session_provider_key = self.default_provider
        self.last_provider_key = self.default_provider
        self.automatic_routing = True

        # Initialisation du RateLimitManager
        if rate_limit_manager is not None:
            self.rate_limit_manager = rate_limit_manager
        else:
            exec_cfg = execution_config or {}
            mode = exec_cfg.get("mode", "mono")
            max_parallel = exec_cfg.get("max_parallel_agents", 1 if str(mode).lower() == "mono" else 2)
            max_gemini = exec_cfg.get("max_parallel_gemini", 1 if str(mode).lower() == "mono" else 2)
            self.rate_limit_manager = RateLimitManager(
                mode=mode,
                max_parallel_agents=max_parallel,
                max_parallel_gemini=max_gemini,
                fallback_enabled=exec_cfg.get("fallback_enabled", True),
                fallback_provider_resolver=lambda: self.get_fallback_provider(self.providers.get(self.session_provider_key, self.default_provider)),
            )

        # Détection automatique de Free Tier au démarrage
        if is_free_tier_provider(self.default_provider):
            self.rate_limit_manager.configure(profile="free")

    def set_active_provider(self, provider_name: str) -> None:
        """Épingle le provider choisi par /model jusqu'à la commande /auto."""
        key = provider_name.strip().lower()
        if key not in self.providers:
            raise ValueError(f"Le provider '{provider_name}' n'est pas disponible.")
        self.session_provider_key = key
        self.last_provider_key = key
        self.automatic_routing = False

        # Si le provider sélectionné est Free Tier, recommander / appliquer profil free
        if is_free_tier_provider(key):
            target = self.providers.get(key)
            m_name = target.get_model_name() if target and hasattr(target, "get_model_name") else ""
            if is_free_tier_provider(key, model_name=m_name):
                # Protéger les quotas Free Tier
                self.rate_limit_manager.configure(profile="free")

    def enable_automatic_routing(self) -> None:
        """Réactive les routes configurées et les préférences par intention."""
        self.automatic_routing = True

    def get_fallback_provider(
        self,
        current_provider: BaseProvider | str,
        exclude: set[str] | None = None,
    ) -> tuple[str, BaseProvider] | None:
        """Trouve un autre provider disponible différent du provider en échec, sans boucle ni ping-pong."""
        if not getattr(self, "automatic_routing", True):
            return None

        excluded = {str(x).lower().strip() for x in (exclude or set())}
        curr_name = ""
        if isinstance(current_provider, str):
            curr_name = current_provider.lower().strip()
        elif hasattr(current_provider, "get_name"):
            curr_name = current_provider.get_name().lower().strip()

        for k, p in self.providers.items():
            if p == current_provider or (hasattr(p, "get_name") and p.get_name().lower().strip() == curr_name):
                excluded.add(k.lower().strip())

        # Développer automatiquement les familles complètes pour éviter le ping-pong
        if any("gemini" in ex for ex in list(excluded)) or "gemini" in curr_name:
            excluded.update({"gemini", "gemini_flash_lite", "gemini_pro", "geminiprovider"})
        if any("claude" in ex for ex in list(excluded)) or "claude" in curr_name:
            excluded.update({"claude", "claudeprovider"})
        if any("openai" in ex or "gpt" in ex for ex in list(excluded)) or "openai" in curr_name:
            excluded.update({"openai", "openaiprovider", "gpt-4o", "gpt-4o-mini"})
        if any("mistral" in ex for ex in list(excluded)) or "mistral" in curr_name:
            excluded.update({"mistral", "mistralprovider"})
        if any("ollama" in ex for ex in list(excluded)) or "ollama" in curr_name:
            excluded.update({"ollama", "ollamaprovider"})

        for k, p in self.providers.items():
            k_lower = k.lower().strip()
            p_name = p.get_name().lower().strip() if hasattr(p, "get_name") else ""
            if k_lower in excluded or p_name in excluded:
                continue

            # Vérifier l'éligibilité réelle du candidat
            if "claude" in k_lower or "claude" in p_name:
                continue
            if ("openai" in k_lower or "openai" in p_name) and not os.environ.get("OPENAI_API_KEY", "").strip():
                continue
            if ("mistral" in k_lower or "mistral" in p_name) and not os.environ.get("MISTRAL_API_KEY", "").strip():
                continue
            if ("gemini" in k_lower or "gemini" in p_name) and not os.environ.get("GEMINI_API_KEY", "").strip():
                continue

            return k, p

        return None

    def get_provider(
        self,
        agent_key: str,
        intent: str | None = None,
        complexity: str | None = None,
    ) -> BaseProvider:
        """Retourne un provider régulé par le RateLimitManager à partir d'une clé d'agent."""
        agent_key = agent_key.strip().lower()
        route_candidates = []
        if intent and complexity:
            route_candidates.append(f"{intent}:{complexity}".lower())
            route_candidates.append(f"{agent_key}:{intent}:{complexity}".lower())
        if intent:
            route_candidates.extend([f"{agent_key}:{intent}".lower(), intent.lower()])
        configured = next(
            (self.task_provider_map[key] for key in route_candidates if key in self.task_provider_map),
            None,
        )
        default_agent_route = self.agent_provider_map.get(agent_key, self.session_provider_key)
        provider_name = (
            (configured or default_agent_route)
            if self.automatic_routing
            else self.session_provider_key
        )
        provider = self.providers.get(provider_name)
        if provider is None and configured is not None:
            provider = self.providers.get(self.session_provider_key)
            provider_name = self.session_provider_key
        if provider is None:
            raise ValueError(
                f"Le provider '{provider_name}' de l'agent '{agent_key}' "
                "est absent ou désactivé."
            )
        self.last_provider_key = provider_name
        if hasattr(self, "rate_limit_manager") and self.rate_limit_manager is not None:
            return self.rate_limit_manager.wrap_provider(
                provider,
                agent_name=agent_key,
                fallback_provider_getter=lambda: self.get_fallback_provider(provider),
            )
        return provider
