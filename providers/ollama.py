# RÔLE DE CE FICHIER :
# Vérifie l'installation Ollama, le serveur local et le modèle disponible, puis
# envoie réellement les prompts des Agents à l'API locale Ollama.

import json
import shutil
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from providers.base_provider import AgentTurn, BaseProvider, ProviderToolCall


class OllamaProviderError(RuntimeError):
    """Erreur d'installation, de disponibilité ou de génération Ollama."""


class OllamaProvider(BaseProvider):
    DEFAULT_MODEL = "qwen3:1.7b"
    DEFAULT_URL = "http://127.0.0.1:11434"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_URL,
    ) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self._verified = False
        self.max_output_tokens: int | None = None
        if not self.model:
            raise ValueError("Le nom du modèle Ollama doit être renseigné.")
        parsed_url = urlsplit(self.base_url)
        if parsed_url.scheme != "http" or parsed_url.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("OllamaProvider n'autorise que le serveur local.")

    def check_available(self) -> None:
        """Vérifie Ollama, le serveur local et la présence du modèle sans le tirer."""
        executable = shutil.which("ollama")
        if executable is None:
            raise OllamaProviderError(
                "Ollama n'est pas installé ou ollama.exe est absent du PATH. "
                "Installe Ollama puis relance le harness."
            )

        try:
            version_result = subprocess.run(
                [executable, "--version"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise OllamaProviderError(
                "Ollama est détecté mais ne répond pas à la commande de version."
            ) from None
        if version_result.returncode != 0:
            raise OllamaProviderError(
                "Ollama est détecté mais sa commande de version a échoué."
            )

        request = Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=5) as response:
                tags_data = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError):
            raise OllamaProviderError(
                "Le serveur Ollama local ne répond pas sur 127.0.0.1:11434. "
                "Ouvre Ollama puis réessaie. Aucun modèle n'a été téléchargé."
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OllamaProviderError(
                "Ollama a répondu, mais sa liste de modèles est illisible."
            ) from None

        if not isinstance(tags_data, dict) or not isinstance(
            tags_data.get("models"), list
        ):
            raise OllamaProviderError(
                "Ollama a répondu avec une liste de modèles invalide."
            )

        available_models = {
            item.get("name")
            for item in tags_data.get("models", [])
            if isinstance(item, dict)
        }
        if self.model not in available_models:
            raise OllamaProviderError(
                f"Le modèle Ollama '{self.model}' n'est pas installé. "
                "Aucun téléchargement automatique n'a été effectué."
            )

        self._verified = True

    def generate(self, prompt: str = "") -> str:
        """Envoie un prompt à l'API de chat locale et retourne le texte de Qwen."""
        if not prompt.strip():
            raise OllamaProviderError("Le prompt transmis à Ollama est vide.")
        if not self._verified:
            self.check_available()

        body = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=300) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                raise OllamaProviderError(
                    f"Ollama ne trouve plus le modèle '{self.model}'. "
                    "Vérifie qu'il est toujours installé."
                ) from None
            raise OllamaProviderError(
                f"Erreur du serveur Ollama (HTTP {error.code})."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise OllamaProviderError(
                "La requête vers Ollama a échoué. Vérifie que le serveur local "
                "est toujours démarré."
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OllamaProviderError(
                "Ollama a retourné une réponse illisible."
            ) from None

        message = result.get("message", {})
        answer = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(answer, str) or not answer.strip():
            raise OllamaProviderError(
                "Ollama n'a retourné aucun texte pour le prompt."
            )
        return answer.strip()

    def generate_agent_turn(
        self,
        prompt: str | None,
        tools: list[dict[str, Any]],
        continuation: Any = None,
        tool_results: list[dict[str, Any]] | None = None,
        *,
        stream_callback: Any = None,
    ) -> AgentTurn:
        """Appelle l'API Ollama chat avec ses déclarations d'outils natives et streaming réel."""
        if not self._verified:
            self.check_available()
        messages = list(continuation) if isinstance(continuation, list) else []
        if prompt:
            messages.append({"role": "user", "content": prompt})
        for item in tool_results or []:
            messages.append(
                {
                    "role": "tool",
                    "name": item.get("name", ""),
                    "content": json.dumps(item, ensure_ascii=False, default=str),
                }
            )

        ollama_tools = [
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item["description"],
                    "parameters": item["parameters"],
                },
            }
            for item in tools
        ]
        use_stream = callable(stream_callback)
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": use_stream}
        if self.max_output_tokens:
            body["options"] = {"num_predict": self.max_output_tokens}
        if ollama_tools:
            body["tools"] = ollama_tools
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=300) as response:
                if use_stream:
                    acc_text: list[str] = []
                    collected_tool_calls: list[dict[str, Any]] = []
                    done_reason = ""
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        chunk_obj = json.loads(line)
                        if not isinstance(chunk_obj, dict):
                            continue
                        msg_part = chunk_obj.get("message")
                        if isinstance(msg_part, dict):
                            delta = msg_part.get("content")
                            if isinstance(delta, str) and delta:
                                acc_text.append(delta)
                                try:
                                    stream_callback(delta, "".join(acc_text))
                                except Exception:
                                    pass
                            tcs = msg_part.get("tool_calls")
                            if isinstance(tcs, list) and tcs:
                                collected_tool_calls.extend(tcs)
                        if chunk_obj.get("done"):
                            done_reason = str(chunk_obj.get("done_reason") or "")
                    result = {
                        "message": {
                            "role": "assistant",
                            "content": "".join(acc_text),
                            "tool_calls": collected_tool_calls,
                        },
                        "done_reason": done_reason,
                    }
                else:
                    result = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise OllamaProviderError(
                f"Erreur du serveur Ollama pendant le tour agentique (HTTP {error.code})."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise OllamaProviderError(
                "La requête agentique vers Ollama a échoué; vérifie le serveur local."
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OllamaProviderError("Ollama a retourné une réponse illisible.") from None

        message = result.get("message", {})
        if not isinstance(message, dict):
            raise OllamaProviderError("Ollama n'a pas retourné de message valide.")
        messages.append(message)
        calls: list[ProviderToolCall] = []
        for index, call in enumerate(message.get("tool_calls", []) or []):
            if not isinstance(call, dict):
                continue
            function = call.get("function", {})
            if not isinstance(function, dict):
                continue
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ProviderToolCall(
                    name=function.get("name", ""),
                    arguments=arguments,
                    call_id=str(call.get("id", f"ollama-call-{index}")),
                )
            )
        content = message.get("content", "")
        return AgentTurn(
            text=content.strip() if isinstance(content, str) else "",
            tool_calls=calls,
            continuation=messages,
            partial=bool(result.get("done_reason") == "length"),
        )

    def execute(self, instruction: str = "") -> str:
        return "OllamaProvider génère du texte et n'exécute pas de commandes."

    def get_name(self) -> str:
        return "OllamaProvider"

    def get_model_name(self) -> str:
        return self.model

    def get_status_label(self) -> str:
        return "[RÉEL]"
