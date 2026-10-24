# RÔLE DE CE FICHIER :
# Connecte les agents du harness aux modèles de chat Mistral via le SDK officiel.
# Il découvre les modèles accessibles avec MISTRAL_API_KEY et adapte les appels
# texte et outils au contrat commun des providers.

from __future__ import annotations

import json
import os
import re
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall


class MistralProviderError(RuntimeError):
    """Erreur Mistral sûre à présenter sans exposer la clé ou la réponse brute."""

    def __init__(self, message: str, *, category: str = "provider") -> None:
        super().__init__(message)
        self.category = category


class MistralProvider(BaseProvider):
    """Provider Mistral avec découverte des modèles autorisés par la clé API."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model.strip() if isinstance(model, str) and model.strip() else None
        self.max_output_tokens: int | None = None
        self._client = None
        self._available_models: dict[str, dict[str, Any]] = {}

    def _get_client(self):
        api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
        if not api_key:
            raise MistralProviderError(
                "MISTRAL_API_KEY n'est pas configurée.", category="configuration"
            )
        if self._client is None:
            try:
                sdk_version = version("mistralai")
            except PackageNotFoundError:
                raise MistralProviderError(
                    "Le SDK officiel mistralai n'est pas installé. Lance : "
                    "python -m pip install --upgrade -r requirements.txt",
                    category="configuration",
                ) from None
            version_parts = tuple(
                int(part) for part in re.findall(r"\d+", sdk_version)[:3]
            )
            if version_parts < (3, 2, 0):
                raise MistralProviderError(
                    f"SDK Mistral {sdk_version} trop ancien ou incompatible. "
                    "Mets-le à jour avec : python -m pip install --upgrade "
                    "'mistralai>=3.2.0'.",
                    category="configuration",
                )
            try:
                brotli_version = version("Brotli")
            except PackageNotFoundError:
                # HTTPX2 ne sélectionne pas le décodeur Brotli s'il est absent.
                brotli_version = None
            if brotli_version is not None:
                brotli_parts = tuple(
                    int(part) for part in re.findall(r"\d+", brotli_version)[:3]
                )
                if brotli_parts < (1, 2, 0):
                    raise MistralProviderError(
                        f"Brotli {brotli_version} est incompatible avec le transport "
                        "HTTP utilisé par Mistral. La version 1.2.0 minimum est "
                        "requise. Mets les dépendances à jour avec : "
                        "python -m pip install --upgrade -r requirements.txt",
                        category="configuration",
                    )
            try:
                from mistralai.client import Mistral
            except ImportError:
                raise MistralProviderError(
                    "Le SDK officiel mistralai est absent ou incompatible. Lance : "
                    "python -m pip install --upgrade -r requirements.txt",
                    category="configuration",
                ) from None
            self._client = Mistral(api_key=api_key)
        return self._client

    @staticmethod
    def _field(value: Any, key: str, default=None):
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    @classmethod
    def _capability(cls, capabilities: Any, key: str) -> bool:
        value = cls._field(capabilities, key, False)
        if isinstance(value, str):
            return value.casefold() in {"true", "1", "yes"}
        return value is True

    @staticmethod
    def _safe_error_detail(error: Exception) -> str:
        """Garde un détail de diagnostic en masquant toute valeur de credential."""
        detail = str(error).strip()
        api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
        if api_key:
            detail = detail.replace(api_key, "[masqué]")
        detail = re.sub(
            r"(?i)(authorization\s*[:=]\s*bearer\s+)\S+",
            r"\1[masqué]",
            detail,
        )
        detail = re.sub(
            r"(?i)(api[_ -]?key\s*[:=]\s*)\S+",
            r"\1[masqué]",
            detail,
        )
        return " ".join(detail.split())[:240]

    @staticmethod
    def _api_error(error: Exception, *, operation: str) -> MistralProviderError:
        detail = MistralProvider._safe_error_detail(error)
        error_text = detail.casefold()
        if (
            isinstance(error, TypeError)
            and "process() takes no keyword arguments" in error_text
        ):
            return MistralProviderError(
                "Le décodeur Brotli installé est incompatible avec le transport "
                "HTTP Mistral. Mets les dépendances à jour avec : "
                "python -m pip install --upgrade -r requirements.txt "
                "(Brotli>=1.2.0).",
                category="configuration",
            )
        status = getattr(error, "status_code", None)
        if status is None:
            status = getattr(error, "status", None)
        try:
            status = int(status) if status is not None else None
        except (TypeError, ValueError):
            status = None

        if status in {401, 403}:
            return MistralProviderError(
                "Mistral a refusé la clé ou l'accès au modèle. Vérifie MISTRAL_API_KEY.",
                category="authentication",
            )
        if status == 402 or "payment required" in error_text:
            return MistralProviderError(
                "Le compte Mistral doit activer ou rétablir son accès API (HTTP 402).",
                category="quota",
            )
        if status == 429 or any(
            marker in error_text
            for marker in ("rate limit", "ratelimit", "quota", "resource exhausted", "http 429")
        ):
            return MistralProviderError(
                "La limite de requêtes ou le quota Mistral est atteint (HTTP 429).",
                category="quota",
            )
        if status == 404:
            return MistralProviderError(
                "Le modèle Mistral sélectionné est indisponible pour cette clé (HTTP 404).",
                category="configuration",
            )
        if isinstance(error, (TimeoutError, ConnectionError)):
            return MistralProviderError(
                f"Délai dépassé ou connexion impossible pendant {operation} Mistral.",
                category="network",
            )
        if status is not None:
            return MistralProviderError(
                f"Erreur de l'API Mistral pendant {operation} (HTTP {status}).",
                category="provider",
            )
        reason = f"Erreur Mistral pendant {operation} ({type(error).__name__})"
        if detail:
            reason += f" : {detail}"
        return MistralProviderError(reason + ".", category="network")

    def list_available_models(self) -> list[dict[str, str]]:
        """Retourne uniquement les modèles accessibles qui acceptent le chat."""
        try:
            response = self._get_client().models.list()
            entries = self._field(response, "data", response) or []
            available: dict[str, dict[str, Any]] = {}
            for item in entries:
                model_id = self._field(item, "id") or self._field(item, "name")
                if not isinstance(model_id, str) or not model_id.strip():
                    continue
                capabilities = self._field(item, "capabilities", {}) or {}
                archived = self._field(item, "archived", False)
                if isinstance(archived, str):
                    archived = archived.casefold() in {"true", "1", "yes"}
                if archived or not self._capability(capabilities, "completion_chat"):
                    continue
                available[model_id] = {
                    "model": model_id,
                    "display_name": model_id,
                    "function_calling": self._capability(
                        capabilities, "function_calling"
                    ),
                }
            if not available:
                raise MistralProviderError(
                    "Mistral n'a retourné aucun modèle de chat utilisable pour cette clé.",
                    category="configuration",
                )
            self._available_models = available
            return [
                {"model": item["model"], "display_name": item["display_name"]}
                for item in available.values()
            ]
        except MistralProviderError:
            raise
        except Exception as error:
            raise self._api_error(error, operation="la détection des modèles") from None

    def select_model(self, model: str) -> None:
        """Sélectionne un modèle réellement listé par l'API pour cette clé."""
        if not self._available_models:
            self.list_available_models()
        if model not in self._available_models:
            raise MistralProviderError(
                "Le modèle demandé n'est pas disponible dans la liste Mistral de cette clé.",
                category="configuration",
            )
        self.model = model

    def _model_info(self) -> dict[str, Any] | None:
        if self.model is None:
            return None
        return self._available_models.get(self.model)

    def _complete(self, messages: list[dict[str, Any]], tools=None):
        if not self.model:
            raise MistralProviderError(
                "Aucun modèle Mistral n'est sélectionné.", category="configuration"
            )
        request: dict[str, Any] = {"model": self.model, "messages": messages}
        if self.max_output_tokens:
            request["max_tokens"] = self.max_output_tokens
        if tools:
            request["tools"] = tools
            request["parallel_tool_calls"] = False
        try:
            return self._get_client().chat.complete(**request)
        except MistralProviderError:
            raise
        except Exception as error:
            raise self._api_error(error, operation="la génération") from None

    @classmethod
    def _message_text(cls, message: Any) -> str:
        content = cls._field(message, "content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for part in content:
                text = cls._field(part, "text")
                if isinstance(text, str):
                    parts.append(text)
            return "".join(parts).strip()
        return ""

    def generate(self, prompt: str = "") -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise MistralProviderError("Le prompt transmis à Mistral est vide.")
        response = self._complete([{"role": "user", "content": prompt}])
        choices = self._field(response, "choices", []) or []
        message = self._field(choices[0], "message") if choices else None
        answer = self._message_text(message) if message is not None else ""
        if not answer:
            raise MistralProviderError("Mistral a retourné une réponse vide.")
        return answer

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        """Gère les appels d'outils natifs et conserve l'historique entre tours."""
        model_info = self._model_info()
        if tools and model_info and not model_info.get("function_calling", False):
            return super().generate_agent_turn(
                prompt, tools, continuation=continuation, tool_results=tool_results
            )

        messages = [dict(item) for item in continuation or [] if isinstance(item, dict)]
        if prompt:
            messages.append({"role": "user", "content": prompt})
        for result in tool_results or []:
            call_id = str(result.get("call_id", ""))
            messages.append(
                {
                    "role": "tool",
                    "name": str(result.get("name", "tool")),
                    "tool_call_id": call_id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        if not messages:
            raise MistralProviderError("Aucun message n'a été transmis à Mistral.")

        api_tools = []
        for tool in tools:
            api_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    },
                }
            )
        response = self._complete(messages, api_tools if api_tools else None)
        choices = self._field(response, "choices", []) or []
        if not choices:
            raise MistralProviderError("Mistral n'a retourné aucun choix de réponse.")

        choice = choices[0]
        message = self._field(choice, "message")
        if message is None:
            raise MistralProviderError("Mistral n'a retourné aucun message.")
        text = self._message_text(message)
        tool_calls = self._field(message, "tool_calls", []) or []
        parsed_calls: list[ProviderToolCall] = []
        serialized_calls = []
        for index, item in enumerate(tool_calls):
            function = self._field(item, "function", {}) or {}
            name = self._field(function, "name", "")
            raw_arguments = self._field(function, "arguments", "{}") or "{}"
            try:
                arguments = (
                    json.loads(raw_arguments)
                    if isinstance(raw_arguments, str)
                    else raw_arguments
                )
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            call_id = str(self._field(item, "id", "") or f"mistral-call-{index}")
            if isinstance(name, str) and name:
                parsed_calls.append(
                    ProviderToolCall(name=name, arguments=arguments, call_id=call_id)
                )
                argument_json = (
                    raw_arguments
                    if isinstance(raw_arguments, str)
                    else json.dumps(raw_arguments, ensure_ascii=False)
                )
                serialized_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": name, "arguments": argument_json},
                    }
                )

        next_messages = list(messages)
        if parsed_calls:
            next_messages.append(
                {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": serialized_calls,
                }
            )
        finish_reason = str(self._field(choice, "finish_reason", "") or "").casefold()
        partial = finish_reason in {"length", "max_tokens"}
        return AgentTurn(
            text=text,
            tool_calls=parsed_calls,
            continuation=next_messages,
            partial=partial,
        )

    def execute(self, instruction: str = "") -> str:
        return "MistralProvider n'exécute aucune commande; il transmet des prompts au LLM."

    def get_name(self) -> str:
        return "MistralProvider"

    def get_model_name(self) -> str:
        return self.model or "Mistral (aucun modèle sélectionné)"

    def get_status_label(self) -> str:
        return "[RÉEL]"
