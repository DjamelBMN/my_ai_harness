# RÔLE DE CE FICHIER :
# Découvre, valide et expose les agents disponibles. L'Orchestrator et le
# DelegationEngine utilisent ce registre sans importer directement les agents.

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
from types import ModuleType
from typing import Mapping

from core.agent import Agent


class AgentPluginAdapter(Agent):
    """Adapts metadata-only plugins to the normal Agent runtime contract."""

    def __init__(self, plugin_class: type) -> None:
        plugin = plugin_class()
        name = getattr(plugin, "name", None) or plugin_class.__name__
        role = getattr(plugin, "role", None) or "agent spécialisé"
        route = getattr(plugin, "routing_key", None) or ""
        if not route:
            route = re.sub(r"(?<!^)(?=[A-Z])", "_", plugin_class.__name__).casefold()
            if route.endswith("_agent"):
                route = route[:-6]
        super().__init__(
            name=name,
            role=role,
            routing_key=route,
            description=getattr(plugin, "description", None) or "Plugin spécialisé du harness.",
            capabilities=getattr(plugin, "capabilities", ()),
            supported_intents=getattr(plugin, "supported_intents", ()),
            allowed_tools=getattr(plugin, "allowed_tools", None),
        )
        self.plugin_descriptor = plugin


class AgentRegistry:
    """Registre d'agents découvert par paquet ou alimenté manuellement."""

    def __init__(
        self,
        agents: Mapping[str, Agent] | None = None,
        *,
        package: str | ModuleType | None = None,
        discover: bool = False,
    ) -> None:
        self._agents: dict[str, Agent] = {}
        self._aliases: dict[str, str] = {}
        self.unavailable: dict[str, str] = {}
        if agents:
            for key, agent in agents.items():
                self.register(agent, key=key)
        if discover and package is not None:
            self.discover(package)

    @classmethod
    def from_package(cls, package: str | ModuleType = "agents") -> "AgentRegistry":
        registry = cls()
        registry.discover(package)
        return registry

    @staticmethod
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", value.strip().casefold()).strip("_")

    @staticmethod
    def _validate(agent: Agent) -> None:
        if not isinstance(agent, Agent):
            raise TypeError("Un agent doit hériter de core.agent.BaseAgent.")
        if not isinstance(agent.name, str) or not agent.name.strip():
            raise ValueError("L'agent doit déclarer un nom non vide.")
        if not isinstance(agent.description, str) or not agent.description.strip():
            raise ValueError(f"{agent.name} doit déclarer une description.")
        if not isinstance(agent.routing_key, str) or not agent.routing_key.strip():
            raise ValueError(f"{agent.name} doit déclarer une routing_key non vide.")
        for field_name in ("capabilities", "supported_intents"):
            value = getattr(agent, field_name, None)
            if not isinstance(value, (tuple, list)) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ValueError(f"{agent.name}.{field_name} doit être une liste de chaînes.")
        if agent.allowed_tools is not None and not isinstance(
            agent.allowed_tools, (tuple, list)
        ):
            raise ValueError(f"{agent.name}.allowed_tools doit être une liste ou None.")

    def register(self, agent: Agent, *, key: str | None = None) -> Agent:
        self._validate(agent)
        primary = self.normalize(key or agent.routing_key)
        if not primary:
            raise ValueError("La clé d'un agent ne peut pas être vide.")
        if primary in self._agents:
            raise ValueError(f"Agent déjà enregistré : {primary}.")
        self._agents[primary] = agent
        candidates = {
            primary,
            self.normalize(agent.routing_key),
            self.normalize(agent.name),
            self.normalize(type(agent).__name__),
        }
        for alias in list(candidates):
            if alias.endswith("_agent"):
                candidates.add(alias[:-6])
        for alias in candidates:
            if alias and alias not in self._aliases:
                self._aliases[alias] = primary
        return agent

    def discover(self, package: str | ModuleType = "agents") -> list[Agent]:
        """Charge les classes Agent définies par chaque module du paquet.

        Une erreur d'import ou de construction désactive uniquement ce plugin;
        les autres agents restent disponibles et la raison est consultable.
        """
        try:
            root = importlib.import_module(package) if isinstance(package, str) else package
            package_path = getattr(root, "__path__", None)
            if package_path is None:
                raise ValueError("Le paquet d'agents ne possède pas de chemin de modules.")
        except Exception as error:
            self.unavailable[getattr(package, "__name__", str(package))] = (
                f"{type(error).__name__}: {error}"
            )
            return []

        discovered: list[Agent] = []
        for item in pkgutil.iter_modules(package_path, root.__name__ + "."):
            module_name = item.name
            leaf = module_name.rsplit(".", 1)[-1]
            if leaf.startswith("_") or leaf in {"base", "__init__"}:
                continue
            try:
                module = importlib.import_module(module_name)
            except Exception as error:
                self.unavailable[leaf] = f"{type(error).__name__}: {error}"
                continue
            classes = [
                candidate
                for _, candidate in inspect.getmembers(module, inspect.isclass)
                if candidate.__module__ == module.__name__
                and not inspect.isabstract(candidate)
                and (
                    (candidate is not Agent and issubclass(candidate, Agent))
                    or (hasattr(candidate, "name") and hasattr(candidate, "capabilities"))
                )
            ]
            for agent_class in classes:
                try:
                    agent = (
                        agent_class()
                        if issubclass(agent_class, Agent)
                        else AgentPluginAdapter(agent_class)
                    )
                    self.register(agent)
                    discovered.append(agent)
                except Exception as error:
                    self.unavailable[agent_class.__name__] = (
                        f"{type(error).__name__}: {error}"
                    )
        return discovered

    def get(self, key: str) -> Agent | None:
        normalized = self.normalize(key)
        primary = self._aliases.get(normalized, normalized)
        return self._agents.get(primary)

    def list_agents(self) -> list[Agent]:
        """Retourne les agents actifs sans exposer leurs alias internes."""
        return list(self._agents.values())

    def find_by_capability(self, capability: str) -> list[Agent]:
        normalized = self.normalize(capability)
        return [
            agent for agent in self._agents.values()
            if normalized in {self.normalize(item) for item in agent.capabilities}
        ]

    def resolve(self, key: str) -> tuple[str, Agent]:
        normalized = self.normalize(key)
        primary = self._aliases.get(normalized, normalized)
        agent = self._agents.get(primary)
        if agent is None:
            if normalized in self.unavailable:
                raise KeyError(f"Agent indisponible '{key}' : {self.unavailable[normalized]}")
            available = ", ".join(sorted(self._agents)) or "aucun"
            raise KeyError(f"Agent inconnu '{key}'. Agents disponibles : {available}.")
        return primary, agent

    @property
    def agents(self) -> dict[str, Agent]:
        return dict(self._agents)

    @property
    def aliases(self) -> dict[str, str]:
        return dict(self._aliases)

    def available(self) -> list[dict[str, object]]:
        return [
            {
                "key": key,
                "name": agent.name,
                "description": agent.description,
                "capabilities": list(agent.capabilities),
                "supported_intents": list(agent.supported_intents),
            }
            for key, agent in sorted(self._agents.items())
        ]
