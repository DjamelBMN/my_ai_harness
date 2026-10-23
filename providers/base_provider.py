# RÔLE DE CE FICHIER :
# Définit le contrat commun des providers LLM. Les providers concrets partagent les
# méthodes de génération, d'identification et d'affichage de leur mode.

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import re
from typing import Any


@dataclass
class ProviderToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class AgentTurn:
    """Provider-neutral result of a model turn; native history stays opaque."""

    text: str = ""
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    continuation: Any = None
    partial: bool = False
    sources: list[dict[str, str]] = field(default_factory=list)


class BaseProvider(ABC):
    """Interface d'un moteur de raisonnement, indépendant des agents."""

    @abstractmethod
    def generate(self, prompt: str = "") -> str:
        """Génère une réponse à partir d'un prompt."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, instruction: str = "") -> str:
        """Interface préparée, sans exécuter de commande dans cette version."""
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        """Retourne le nom de la classe provider."""
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        """Retourne le nom du LLM représenté par ce provider."""
        raise NotImplementedError

    def get_status_label(self) -> str:
        """Indique qu'un provider préparé n'est pas encore relié à son LLM."""
        return "[NON CONNECTÉ]"

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        """Adaptateur JSON pour les providers sans fonction-native configurée.

        Les providers qui savent conserver leur propre historique peuvent
        surcharger cette méthode. ``generate`` reste inchangée pour compatibilité.
        """
        history = continuation if isinstance(continuation, str) else ""
        parts = []
        if prompt:
            parts.append(f"MESSAGE UTILISATEUR / CONTINUATION:\n{prompt}")
        for result in tool_results or []:
            parts.append(
                "RÉSULTAT D'OUTIL:\n" + json.dumps(result, ensure_ascii=False, default=str)
            )
        tool_contract = json.dumps(tools, ensure_ascii=False)
        instructions = (
            "Tu es un agent piloté par outils. Utilise uniquement les outils listés. "
            "Si une action locale est nécessaire, réponds par un objet JSON seul de la "
            "forme {\"tool_calls\":[{\"name\":\"nom\",\"arguments\":{}}]}. "
            "Quand le travail est terminé, réponds par {\"final\":\"réponse\"}. "
            "N'affirme pas qu'un outil a réussi sans son résultat.\n"
            f"OUTILS DISPONIBLES:\n{tool_contract}\n"
        )
        full_prompt = "\n\n".join([history, instructions, *parts]).strip()
        raw = self.generate(full_prompt)
        current_history = "\n".join(filter(None, (history, "MODEL RESPONSE:", raw)))[-40_000:]
        parsed = self._parse_agent_json(raw)
        if parsed is None:
            return AgentTurn(text=raw.strip(), continuation=current_history)
        calls = []
        for index, item in enumerate(parsed.get("tool_calls", [])):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            arguments = item.get("arguments", {})
            if isinstance(name, str) and isinstance(arguments, dict):
                calls.append(
                    ProviderToolCall(
                        name=name,
                        arguments=arguments,
                        call_id=str(item.get("id", f"call-{index}")),
                    )
                )
        if calls:
            return AgentTurn(tool_calls=calls, continuation=current_history)
        final = parsed.get("final")
        if isinstance(final, str):
            return AgentTurn(text=final.strip(), continuation=current_history)
        return AgentTurn(text=raw.strip(), continuation=current_history)

    @staticmethod
    def _parse_agent_json(raw: str) -> dict[str, Any] | None:
        candidates = [raw.strip()]
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.I | re.S)
        if fenced:
            candidates.insert(0, fenced.group(1))
        else:
            start, end = raw.find("{"), raw.rfind("}")
            if start >= 0 and end > start:
                candidates.append(raw[start : end + 1])
        for candidate in candidates:
            try:
                result = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(result, dict) and (
                isinstance(result.get("tool_calls"), list)
                or isinstance(result.get("final"), str)
            ):
                return result
        return None
