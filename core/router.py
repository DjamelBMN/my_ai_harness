# RÔLE DE CE FICHIER :
# Lit la configuration et choisit le provider LLM adapté à un agent. Il ne crée ni
# agent ni modèle : il retourne une instance de provider déjà enregistrée.

from pathlib import Path
from typing import Mapping

from providers.base_provider import BaseProvider


def load_config(path: str | Path) -> dict:
    """Lit le sous-ensemble YAML simple utilisé dans config/config.yaml."""
    settings = {
        "default_provider": "ollama",
        "providers": {},
        "agents": {},
        "routing": {},
    }
    section = None
    current_name = None

    for raw_line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        # Les routes peuvent porter un niveau de complexité (ex. coding:complex),
        # alors que les valeurs de modèle peuvent elles-mêmes contenir des deux-points.
        if section == "routing" and indent == 2:
            key, separator, value = stripped.rpartition(":")
        else:
            key, separator, value = stripped.partition(":")
        if not separator:
            raise ValueError(f"Ligne de configuration invalide : {raw_line}")

        if indent == 0:
            current_name = None
            if value.strip():
                if key != "default_provider":
                    raise ValueError(f"Clé de configuration inconnue : {key}")
                settings["default_provider"] = value.strip().lower()
            else:
                section = key
                if section == "openai":
                    settings["providers"]["openai"] = {}
                    current_name = "openai"
                elif section not in {"providers", "agents", "routing"}:
                    raise ValueError(f"Section de configuration inconnue : {section}")
            continue

        if section == "openai" and indent == 2 and current_name == "openai":
            option_value = value.strip()
            if key == "enabled" and option_value.lower() in {"true", "false"}:
                settings["providers"]["openai"][key] = (
                    option_value.lower() == "true"
                )
            elif key == "model" and option_value:
                settings["providers"]["openai"][key] = (
                    option_value.strip('"').strip("'")
                )
            else:
                raise ValueError(f"Option OpenAI invalide : {raw_line}")
        elif section == "providers" and indent == 2:
            current_name = key.lower()
            settings["providers"][current_name] = {}
        elif section == "providers" and indent >= 4 and current_name:
            option_value = value.strip()
            if key == "enabled" and option_value.lower() in {"true", "false"}:
                settings["providers"][current_name][key] = (
                    option_value.lower() == "true"
                )
            elif key == "model" and option_value:
                settings["providers"][current_name][key] = (
                    option_value.strip('"').strip("'")
                )
            else:
                raise ValueError(f"Option provider invalide : {raw_line}")
        elif section == "agents" and indent == 2:
            current_name = key.lower()
            settings["agents"][current_name] = {}
        elif section == "agents" and indent >= 4 and current_name:
            if key != "provider" or not value.strip():
                raise ValueError(f"Option agent invalide : {raw_line}")
            settings["agents"][current_name][key] = value.strip().lower()
        elif section == "routing" and indent == 2 and value.strip():
            settings["routing"][key.lower()] = value.strip().lower()
        else:
            raise ValueError(f"Indentation ou option invalide : {raw_line}")

    return settings


class ModelRouter:
    """Choisit un provider pour une clé d'agent, sans dépendre d'un agent concret."""

    def __init__(
        self,
        providers: Mapping[str, BaseProvider],
        agent_provider_map: Mapping[str, str],
        default_provider: str = "ollama",
        task_provider_map: Mapping[str, str] | None = None,
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

    def set_active_provider(self, provider_name: str) -> None:
        """Épingle le provider choisi par /model jusqu'à la commande /auto."""
        key = provider_name.strip().lower()
        if key not in self.providers:
            raise ValueError(f"Le provider '{provider_name}' n'est pas disponible.")
        self.session_provider_key = key
        self.last_provider_key = key
        self.automatic_routing = False

    def enable_automatic_routing(self) -> None:
        """Réactive les routes configurées et les préférences par intention."""
        self.automatic_routing = True

    def get_provider(
        self,
        agent_key: str,
        intent: str | None = None,
        complexity: str | None = None,
    ) -> BaseProvider:
        """Retourne un provider à partir d'une clé d'agent, sans dépendre d'un agent."""
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
            # Une préférence de tâche indisponible retombe sur la route historique.
            provider = self.providers.get(self.session_provider_key)
            provider_name = self.session_provider_key
        if provider is None:
            raise ValueError(
                f"Le provider '{provider_name}' de l'agent '{agent_key}' "
                "est absent ou désactivé."
            )
        self.last_provider_key = provider_name
        return provider
