# RÔLE DE CE FICHIER :
# Envoie le prompt d'un agent à un modèle GPT via l'API OpenAI et retourne uniquement
# son texte. La clé vient de OPENAI_API_KEY ; elle n'est jamais affichée ni enregistrée.

import os
import json
from typing import Any

from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall


class OpenAIProviderError(RuntimeError):
    """Erreur OpenAI présentée proprement à l'utilisateur."""


class OpenAIProvider(BaseProvider):
    def __init__(self, model: str) -> None:
        self.model = model.strip()
        self._client = None
        self.max_output_tokens: int | None = None
        if not self.model:
            raise ValueError("Le modèle OpenAI doit être renseigné dans config.yaml.")

    def generate(self, prompt: str = "") -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise OpenAIProviderError(
                "OPENAI_API_KEY n'est pas configurée. "
                "Dans PowerShell, saisis-la sans l'afficher avec les commandes "
                "indiquées au démarrage du programme ou dans README.md."
            )

        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                AuthenticationError,
                OpenAI,
                OpenAIError,
            )
        except ImportError:
            raise OpenAIProviderError(
                "Le SDK OpenAI n'est pas installé. Lance : "
                "python -m pip install -r requirements.txt"
            ) from None

        try:
            if self._client is None:
                self._client = OpenAI(api_key=api_key, max_retries=2, timeout=90.0)
            client = self._client
            request = {"model": self.model, "input": prompt}
            if self.max_output_tokens:
                request["max_output_tokens"] = self.max_output_tokens
            response = client.responses.create(**request)
        except AuthenticationError:
            raise OpenAIProviderError(
                "Authentification OpenAI refusée. Vérifie la variable "
                "OPENAI_API_KEY."
            ) from None
        except APIConnectionError:
            raise OpenAIProviderError(
                "Impossible de joindre l'API OpenAI. Vérifie ta connexion réseau."
            ) from None
        except APIStatusError as error:
            status_code = getattr(error, "status_code", None)
            error_code = getattr(error, "code", None)

            if status_code == 404 or error_code == "model_not_found":
                raise OpenAIProviderError(
                    f"Le modèle '{self.model}' est indisponible pour cette API. "
                    "Vérifie son nom et son accès dans config/config.yaml."
                ) from None
            if status_code in {401, 403}:
                raise OpenAIProviderError(
                    "OpenAI a refusé l'authentification ou l'accès au modèle. "
                    "Vérifie OPENAI_API_KEY et les droits de ton compte."
                ) from None
            if status_code == 429:
                raise OpenAIProviderError(
                    "La limite ou le quota OpenAI est atteint. Vérifie ton compte "
                    "et réessaie plus tard."
                ) from None

            raise OpenAIProviderError(
                f"Erreur de l'API OpenAI (HTTP {status_code})."
            ) from None
        except OpenAIError:
            raise OpenAIProviderError(
                "Le client OpenAI a rencontré une erreur pendant la requête."
            ) from None

        answer = getattr(response, "output_text", "")
        if not isinstance(answer, str) or not answer.strip():
            raise OpenAIProviderError(
                "Le modèle GPT a retourné une réponse vide."
            )

        return answer.strip()

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        """Appelle Responses function-calling et conserve la chaîne via response id."""
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise OpenAIProviderError("OPENAI_API_KEY n'est pas configurée.")
        try:
            from openai import (
                APIConnectionError,
                APIStatusError,
                AuthenticationError,
                OpenAI,
                OpenAIError,
            )
        except ImportError:
            raise OpenAIProviderError(
                "Le SDK OpenAI n'est pas installé. Lance : "
                "python -m pip install -r requirements.txt"
            ) from None

        api_tools = [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
                "strict": False,
            }
            for tool in tools
        ]
        request_input: Any
        if tool_results:
            request_input = [
                {
                    "type": "function_call_output",
                    "call_id": str(item.get("call_id", "")),
                    "output": json.dumps(item, ensure_ascii=False, default=str),
                }
                for item in tool_results
            ]
        else:
            request_input = prompt or ""

        try:
            if self._client is None:
                self._client = OpenAI(api_key=api_key, max_retries=2, timeout=90.0)
            request: dict[str, Any] = {
                "model": self.model,
                "input": request_input,
                "parallel_tool_calls": False,
            }
            if api_tools:
                request["tools"] = api_tools
            if continuation:
                request["previous_response_id"] = continuation
            if self.max_output_tokens:
                request["max_output_tokens"] = self.max_output_tokens
            response = self._client.responses.create(**request)
        except AuthenticationError:
            raise OpenAIProviderError(
                "Authentification OpenAI refusée. Vérifie OPENAI_API_KEY."
            ) from None
        except APIConnectionError:
            raise OpenAIProviderError(
                "Impossible de joindre l'API OpenAI. Vérifie la connexion réseau."
            ) from None
        except APIStatusError as error:
            status_code = getattr(error, "status_code", None)
            if status_code == 404:
                raise OpenAIProviderError(
                    f"Le modèle '{self.model}' est indisponible pour cette API."
                ) from None
            if status_code == 429:
                raise OpenAIProviderError(
                    "La limite ou le quota OpenAI est atteint."
                ) from None
            raise OpenAIProviderError(
                f"Erreur de l'API OpenAI (HTTP {status_code})."
            ) from None
        except OpenAIError:
            raise OpenAIProviderError(
                "Le client OpenAI a rencontré une erreur pendant la requête."
            ) from None

        calls = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") != "function_call":
                continue
            raw_arguments = getattr(item, "arguments", "{}") or "{}"
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ProviderToolCall(
                    name=getattr(item, "name", ""),
                    arguments=arguments,
                    call_id=getattr(item, "call_id", "") or getattr(item, "id", ""),
                )
            )
        answer = getattr(response, "output_text", "") or ""
        incomplete = getattr(response, "status", "") == "incomplete"
        return AgentTurn(
            text=answer.strip(),
            tool_calls=calls,
            continuation=getattr(response, "id", continuation),
            partial=incomplete,
        )

    def execute(self, instruction: str = "") -> str:
        return (
            "OpenAIProvider n'exécute aucune commande. "
            "Il transmet uniquement du texte au modèle GPT."
        )

    def get_name(self) -> str:
        return "OpenAIProvider"

    def get_model_name(self) -> str:
        return self.model.replace("gpt-", "GPT-")

    def get_status_label(self) -> str:
        return "[RÉEL]"
