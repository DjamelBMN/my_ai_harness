# RÔLE DE CE FICHIER :
# Définit la classe commune Agent, qui représente un programme construit dans ce
# harness. L'Orchestrator lui attribue un provider LLM via le ModelRouter.

import re

from core.task import Task
from providers.base_provider import BaseProvider


class Agent:
    """Contrat commun des agents chargeables par le runtime.

    Un plugin peut déclarer ses métadonnées comme attributs de classe et fournir
    un constructeur sans argument. Les agents historiques qui transmettent
    explicitement name/role/routing_key restent compatibles.
    """

    name = ""
    role = "agent spécialisé"
    routing_key = ""
    description = "Agent spécialisé du harness."
    capabilities: tuple[str, ...] = ()
    supported_intents: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] | None = None

    def __init__(
        self,
        name: str | None = None,
        role: str | None = None,
        routing_key: str | None = None,
        *,
        description: str | None = None,
        capabilities=None,
        supported_intents=None,
        allowed_tools=None,
    ) -> None:
        self.name = name or type(self).name or type(self).__name__
        self.role = role or type(self).role
        self.routing_key = routing_key or type(self).routing_key or self._default_routing_key()
        self.description = description or type(self).description
        self.capabilities = tuple(capabilities if capabilities is not None else type(self).capabilities)
        self.supported_intents = tuple(
            supported_intents
            if supported_intents is not None
            else type(self).supported_intents
        )
        self.allowed_tools = (
            tuple(allowed_tools)
            if allowed_tools is not None
            else type(self).allowed_tools
        )
        self.provider: BaseProvider | None = None
        self.last_prompt = ""
        self.last_llm_response = ""

    def _default_routing_key(self) -> str:
        slug = re.sub(r"(?<!^)(?=[A-Z])", "_", type(self).__name__).casefold()
        return slug[:-6] if slug.endswith("_agent") else slug

    def set_provider(self, provider: BaseProvider) -> None:
        """Reçoit le provider sélectionné par ModelRouter."""
        self.provider = provider

    def build_prompt(self, task: Task) -> str:
        """Construit le prompt de base envoyé au moteur de raisonnement."""
        parts = [
            f"Tu es {self.name}, un agent dont le rôle est : {self.role}.",
            f"Tâche à accomplir : {task.description}",
        ]
        if task.context is not None:
            context_description = task.context.describe()
            if context_description:
                parts.append(f"Contexte de session : {context_description}")
        return "\n".join(parts)

    def interpret_response(self, llm_response: str) -> str:
        """Point d'extension pour interpréter la réponse du LLM."""
        return llm_response.strip()

    def run(self, task: Task) -> str:
        """Construit le prompt, appelle le provider puis interprète sa réponse."""
        if self.provider is None:
            raise RuntimeError(
                f"Aucun provider n'a été attribué à {self.name}. "
                "L'Orchestrator doit d'abord appeler le ModelRouter."
            )

        self.last_prompt = self.build_prompt(task)
        self.last_llm_response = self.provider.generate(self.last_prompt)
        return self.interpret_response(self.last_llm_response)


# Nom de contrat explicite pour les nouveaux plugins; l'alias conserve toute
# la compatibilité avec les imports historiques de ``Agent``.
BaseAgent = Agent
