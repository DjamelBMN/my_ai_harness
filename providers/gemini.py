# RÔLE DE CE FICHIER :
# Vérifie l'accès au modèle Gemini avec le SDK officiel google-genai, transmet les
# prompts des Agents à l'API Gemini et retourne uniquement le texte généré.

import os
import json
import time
from typing import Any

from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall


class GeminiProviderError(RuntimeError):
    """Erreur de configuration, d'accès ou de génération Gemini."""

    def __init__(self, message: str, category: str = "provider") -> None:
        super().__init__(message)
        self.category = category


class GeminiProvider(BaseProvider):
    def __init__(self, model: str | None = None) -> None:
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise GeminiProviderError(
                "Gemini — configuration invalide : modèle vide.",
                category="configuration",
            )
        self.model = model.strip() if model else None
        self._client = None
        self._verified = False
        self._available_models: dict[str, str] = {}
        self.max_output_tokens: int | None = None
        self.max_retries = 2
        self.stream_callback: Any = None

    def _get_client(self):
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GeminiProviderError(
                "GEMINI_API_KEY n'est pas configurée.",
                category="missing_key",
            )
        if self._client is not None:
            return self._client

        try:
            from google import genai
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé. Lance : "
                "python -m pip install -r requirements.txt",
                category="sdk_missing",
            ) from None

        try:
            from google.genai import types

            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=90_000),
            )
        except Exception:
            raise GeminiProviderError(
                "Le client Google GenAI n'a pas pu être initialisé.",
                category="configuration",
            ) from None
        return self._client

    @staticmethod
    def _api_error(error: Exception, phase: str) -> GeminiProviderError:
        """Traduit les erreurs SDK sans renvoyer leurs détails ou une clé éventuelle."""
        error_type = type(error).__name__
        if error_type in {
            "ConnectError",
            "ConnectTimeout",
            "ReadTimeout",
            "TimeoutException",
        } or isinstance(error, (ConnectionError, TimeoutError)):
            return GeminiProviderError(
                f"Impossible de joindre l'API Gemini pendant {phase}.",
                category="unavailable",
            )

        status = getattr(error, "code", None)
        if not isinstance(status, int):
            status = getattr(error, "status_code", None)

        if status in {400, 404}:
            return GeminiProviderError(
                "Gemini — configuration invalide : modèle absent ou incompatible "
                "avec l'API.",
                category="configuration",
            )
        if status in {401, 403}:
            return GeminiProviderError(
                "La clé Gemini a été refusée. Vérifie GEMINI_API_KEY.",
                category="authentication",
            )
        if status == 429:
            return GeminiProviderError(
                "La limite ou le quota Gemini est atteint. Réessaie plus tard.",
                category="quota",
            )
        if status in {408, 500, 502, 503, 504}:
            return GeminiProviderError(
                f"L'API Gemini est temporairement indisponible pendant {phase} "
                f"(HTTP {status}).",
                category="unavailable",
            )
        return GeminiProviderError(
            f"La vérification Gemini a échoué pendant {phase}"
            + (f" (HTTP {status})." if status else "."),
            category="unavailable",
        )

    def list_available_models(self) -> list[dict[str, str]]:
        """Liste les modèles accessibles qui prennent en charge generateContent."""
        client = self._get_client()
        try:
            discovered = []
            for model_info in client.models.list():
                actions = getattr(model_info, "supported_actions", None) or []
                if "generateContent" not in actions:
                    continue
                resource_name = getattr(model_info, "name", "")
                if not isinstance(resource_name, str) or not resource_name.strip():
                    continue
                model_id = resource_name.strip()
                if model_id.startswith("models/"):
                    model_id = model_id.removeprefix("models/")
                display_name = getattr(model_info, "display_name", None)
                if not isinstance(display_name, str) or not display_name.strip():
                    display_name = model_id
                discovered.append(
                    {"model": model_id, "display_name": display_name.strip()}
                )
        except Exception as error:
            raise self._api_error(error, "la liste des modèles") from None

        # Certaines pages peuvent inclure un même identifiant sous plusieurs
        # variantes de métadonnées ; le menu ne doit proposer chaque modèle qu'une fois.
        unique_models = {item["model"]: item for item in discovered}
        discovered = list(unique_models.values())
        if not discovered:
            raise GeminiProviderError(
                "Gemini — configuration invalide : aucun modèle accessible ne "
                "prend en charge la génération de texte.",
                category="configuration",
            )
        self._available_models = {
            item["model"]: item["display_name"] for item in discovered
        }
        return discovered

    def select_model(self, model: str) -> None:
        """Sélectionne un modèle parmi ceux retournés par l'API Gemini."""
        if model not in self._available_models:
            raise GeminiProviderError(
                "Gemini — configuration invalide : le modèle choisi n'est pas "
                "dans la liste des modèles accessibles.",
                category="configuration",
            )
        self.model = model
        self._verified = True

    def with_model(self, model: str) -> "GeminiProvider":
        """Crée un provider pour un modèle déjà validé par la même liste API."""
        if model not in self._available_models:
            raise GeminiProviderError(
                "Gemini — configuration invalide : le modèle n'est pas accessible.",
                category="configuration",
            )
        provider = GeminiProvider(model=model)
        provider._client = self._client
        provider._available_models = dict(self._available_models)
        provider._verified = True
        provider.max_output_tokens = self.max_output_tokens
        return provider

    def supports_model(self, model: str) -> bool:
        """Indique si la liste vérifiée de l'API contient ce modèle."""
        return model in self._available_models

    def check_available(self) -> None:
        """Vérifie la clé, le SDK et l'accès au modèle configuré sans génération."""
        if self._verified:
            return
        self.list_available_models()
        if self.model is None:
            raise GeminiProviderError(
                "Gemini — configuration invalide : aucun modèle n'a été sélectionné.",
                category="configuration",
            )
        if self.model not in self._available_models:
            raise GeminiProviderError(
                "Gemini — configuration invalide : le modèle configuré "
                "n'est pas accessible.",
                category="configuration",
            )
        self._verified = True

    def generate(self, prompt: str = "") -> str:
        """Envoie le prompt à Gemini via google-genai et retourne son texte."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not self._verified:
            self.check_available()

        response = self._generate_content(prompt, phase="la génération")

        answer = getattr(response, "text", "")
        if not isinstance(answer, str) or not answer.strip():
            raise GeminiProviderError(
                "Gemini n'a retourné aucun texte pour le prompt."
            )
        return answer.strip()

    def _generate_content(self, contents: Any, *, config: Any = None, phase: str):
        """Appelle l'API avec délai borné et reprise seulement sur erreur transitoire."""
        for attempt in range(self.max_retries + 1):
            try:
                options = {"model": self.model, "contents": contents}
                if config is not None:
                    options["config"] = config
                return self._client.models.generate_content(**options)
            except Exception as error:
                mapped = self._api_error(error, phase)
                if mapped.category != "unavailable" or attempt >= self.max_retries:
                    raise mapped from None
                time.sleep(min(0.5 * (2 ** attempt), 2.0))

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Demande un objet JSON contraint par un schéma Gemini officiel."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError("Le schéma de sortie doit être un JSON Schema object.")
        if not self._verified:
            self.check_available()
        try:
            from google.genai import types
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé.", category="sdk_missing"
            ) from None
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "http_options": types.HttpOptions(timeout=90_000),
        }
        if self.max_output_tokens:
            config["max_output_tokens"] = self.max_output_tokens
        response = self._generate_content(
            prompt,
            config=types.GenerateContentConfig(**config),
            phase="la génération structurée",
        )
        raw = getattr(response, "text", "")
        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raise GeminiProviderError(
                "Gemini n'a pas retourné un JSON conforme à la réponse structurée."
            ) from None
        if not isinstance(result, dict):
            raise GeminiProviderError("La réponse structurée Gemini n'est pas un objet JSON.")
        return result

    def generate_stream(self, prompt: str):
        """Expose les fragments texte du SDK; cette voie n'est pas utilisée pour les tools."""
        if not prompt.strip():
            raise GeminiProviderError("Le prompt transmis à Gemini est vide.")
        if not self._verified:
            self.check_available()
        try:
            stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config={"http_options": {"timeout": 90_000}},
            )
            for chunk in stream:
                text = getattr(chunk, "text", "")
                if isinstance(text, str) and text:
                    yield text
        except Exception as error:
            raise self._api_error(error, "la génération en streaming") from None

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
    ) -> AgentTurn:
        """Utilise function calling natif et garde les Content/Part intacts.

        L'objet Content complet renvoyé par Gemini reste dans l'historique. Le SDK
        peut ainsi retransmettre les thought signatures à l'appel suivant, sans les
        convertir en texte ni les afficher à l'utilisateur.
        """
        if not self._verified:
            self.check_available()
        try:
            from google.genai import types
        except ImportError:
            raise GeminiProviderError(
                "Le SDK Google GenAI n'est pas installé.", category="sdk_missing"
            ) from None

        history = continuation.get("contents", []) if isinstance(continuation, dict) else []
        contents = list(history)
        if prompt:
            contents.append(
                types.Content(role="user", parts=[types.Part(text=prompt)])
            )
        if tool_results:
            function_parts = []
            for result in tool_results:
                response_payload = {
                    "status": result.get("status", "unknown"),
                    "summary": result.get("summary", ""),
                    "output": result.get("output", ""),
                }
                function_response = types.FunctionResponse(
                    id=result.get("call_id") or None,
                    name=result.get("name", ""),
                    response=response_payload,
                )
                function_parts.append(
                    types.Part(function_response=function_response)
                )
            contents.append(types.Content(role="user", parts=function_parts))

        builtin_google_search = any(
            item.get("builtin") == "google_search" for item in tools
        )
        declarations = [
            types.FunctionDeclaration(
                name=item["name"],
                description=item["description"],
                parameters_json_schema=item["parameters"],
            )
            for item in tools
            if not item.get("builtin")
        ]
        config: dict[str, Any] = {
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            "http_options": types.HttpOptions(timeout=90_000),
        }
        if self.max_output_tokens:
            config["max_output_tokens"] = self.max_output_tokens
        configured_tools = []
        # Search intégré et fonctions locales sont faits en tours distincts.
        # Cela évite de dépendre du mode combiné preview de Gemini 3.
        if builtin_google_search:
            configured_tools.append(types.Tool(google_search=types.GoogleSearch()))
        elif declarations:
            configured_tools.append(types.Tool(function_declarations=declarations))
        if configured_tools:
            config["tools"] = configured_tools

        from types import SimpleNamespace

        response = None
        if (
            callable(getattr(self, "stream_callback", None))
            and hasattr(self._client, "models")
            and hasattr(self._client.models, "generate_content_stream")
        ):
            streamed_text: list[str] = []
            try:
                stream = self._client.models.generate_content_stream(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(**config),
                )
                all_parts = []
                last_candidate = None
                stream_grounding = None
                for chunk in stream:
                    cands = getattr(chunk, "candidates", None) or []
                    if not cands:
                        continue
                    last_candidate = cands[0]
                    if getattr(last_candidate, "grounding_metadata", None):
                        stream_grounding = last_candidate.grounding_metadata
                    for part in getattr(getattr(last_candidate, "content", None), "parts", None) or []:
                        all_parts.append(part)
                        txt = getattr(part, "text", None)
                        if txt and not getattr(part, "thought", False):
                            streamed_text.append(txt)
                            try:
                                self.stream_callback(txt, "".join(streamed_text))
                            except Exception:
                                pass
                if all_parts:
                    response = SimpleNamespace(
                        text="".join(streamed_text),
                        candidates=[
                            SimpleNamespace(
                                content=types.Content(role="model", parts=all_parts),
                                finish_reason=getattr(last_candidate, "finish_reason", ""),
                                grounding_metadata=stream_grounding,
                            )
                        ],
                    )
            except Exception as error:
                if streamed_text:
                    raise self._api_error(error, "la génération en streaming") from None
                response = None

        try:
            response = response or self._generate_content(
                contents,
                config=types.GenerateContentConfig(**config),
                phase="la génération avec outils",
            )
        except GeminiProviderError as error:
            if builtin_google_search and declarations and error.category in {"quota", "configuration"}:
                fallback_config = dict(config)
                fallback_config["tools"] = [types.Tool(function_declarations=declarations)]
                response = self._generate_content(
                    contents,
                    config=types.GenerateContentConfig(**fallback_config),
                    phase="la génération avec outils",
                )
            else:
                raise

        candidates = getattr(response, "candidates", None) or []
        candidate = candidates[0] if candidates else None
        response_content = getattr(candidate, "content", None)
        if response_content is not None:
            # Garder l'objet original, notamment ses parts thought_signature.
            contents.append(response_content)

        calls: list[ProviderToolCall] = []
        text_parts: list[str] = []
        sources: list[dict[str, str]] = []
        for part in getattr(response_content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                arguments = getattr(function_call, "args", None) or {}
                calls.append(
                    ProviderToolCall(
                        name=getattr(function_call, "name", "") or "",
                        arguments=dict(arguments) if isinstance(arguments, dict) else {},
                        call_id=getattr(function_call, "id", "") or "",
                    )
                )
            elif getattr(part, "text", None) and not getattr(part, "thought", False):
                text_parts.append(part.text)

        grounding = getattr(candidate, "grounding_metadata", None)
        for chunk in getattr(grounding, "grounding_chunks", None) or []:
            web_source = getattr(chunk, "web", None)
            url = getattr(web_source, "uri", "") if web_source is not None else ""
            title = getattr(web_source, "title", "") if web_source is not None else ""
            if isinstance(url, str) and url.startswith("https://"):
                item = {"url": url, "title": title or url}
                if item not in sources:
                    sources.append(item)

        finish_reason = str(getattr(candidate, "finish_reason", ""))
        partial = "MAX_TOKENS" in finish_reason.upper()
        text = "".join(text_parts).strip()
        if not text and not calls and not partial:
            text = (getattr(response, "text", "") or "").strip()
        return AgentTurn(
            text=text,
            tool_calls=calls,
            continuation={"contents": contents},
            partial=partial,
            sources=sources,
        )

    def execute(self, instruction: str = "") -> str:
        return "GeminiProvider génère du texte et n'exécute pas de commandes."

    def get_name(self) -> str:
        return "GeminiProvider"

    def get_model_name(self) -> str:
        return self.model or "Gemini (aucun modèle sélectionné)"

    def get_status_label(self) -> str:
        return "[RÉEL]"
