# RÔLE DE CE FICHIER :
# Vérifie le provider Mistral, sa sélection de modèles et son intégration au menu
# distant sans utiliser Internet ni une véritable clé API.

from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

import main
from core.router import load_config
from providers.mistral import MistralProvider, MistralProviderError


class MistralProviderTests(unittest.TestCase):
    def test_missing_key_fails_before_sdk_or_network(self) -> None:
        provider = MistralProvider("mistral-small-latest")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(MistralProviderError, "MISTRAL_API_KEY"):
                provider.list_available_models()
        self.assertIsNone(provider._client)

    def test_lists_only_accessible_chat_models_and_selects_one(self) -> None:
        response = SimpleNamespace(
            data=[
                SimpleNamespace(
                    id="mistral-small-latest",
                    capabilities={"completion_chat": True, "function_calling": True},
                    archived=False,
                ),
                SimpleNamespace(
                    id="mistral-embed",
                    capabilities={"completion_chat": False},
                    archived=False,
                ),
                SimpleNamespace(
                    id="retired-chat",
                    capabilities={"completion_chat": True},
                    archived=True,
                ),
            ]
        )
        provider = MistralProvider()
        provider._client = SimpleNamespace(
            models=SimpleNamespace(list=lambda: response)
        )
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-only"}):
            models = provider.list_available_models()
            provider.select_model("mistral-small-latest")
        self.assertEqual(
            models,
            [{"model": "mistral-small-latest", "display_name": "mistral-small-latest"}],
        )
        self.assertEqual(provider.get_model_name(), "mistral-small-latest")

    def test_native_tool_call_round_trip_preserves_mistral_messages(self) -> None:
        tool_message = SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call-1",
                    function=SimpleNamespace(
                        name="read_file", arguments='{"path":"notes.md"}'
                    ),
                )
            ],
        )
        final_message = SimpleNamespace(content="Le fichier contient des notes.", tool_calls=[])
        responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(message=tool_message, finish_reason="tool_calls")]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=final_message, finish_reason="stop")]
            ),
        ]
        requests = []

        def complete(**kwargs):
            requests.append(kwargs)
            return responses.pop(0)

        provider = MistralProvider("mistral-small-latest")
        provider._available_models = {
            "mistral-small-latest": {"function_calling": True}
        }
        provider._client = SimpleNamespace(chat=SimpleNamespace(complete=complete))
        tools = [{
            "name": "read_file",
            "description": "Read a workspace file",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }]
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "test-only"}):
            first = provider.generate_agent_turn("Lis notes.md", tools)
            self.assertEqual(first.tool_calls[0].name, "read_file")
            final = provider.generate_agent_turn(
                None,
                tools,
                continuation=first.continuation,
                tool_results=[{
                    "call_id": "call-1",
                    "name": "read_file",
                    "status": "success",
                    "output": "Notes réelles",
                }],
            )
        self.assertEqual(final.text, "Le fichier contient des notes.")
        self.assertEqual(requests[0]["tools"][0]["function"]["name"], "read_file")
        self.assertEqual(requests[1]["messages"][-2]["role"], "assistant")
        self.assertEqual(requests[1]["messages"][-1]["role"], "tool")
        self.assertEqual(requests[1]["messages"][-1]["tool_call_id"], "call-1")

    def test_models_without_native_function_calling_keep_text_fallback(self) -> None:
        provider = MistralProvider("chat-only")
        provider._available_models = {"chat-only": {"function_calling": False}}
        provider.generate = lambda prompt: '{"final":"Réponse outil compatible"}'
        turn = provider.generate_agent_turn(
            "question",
            [{
                "name": "read_file",
                "description": "read",
                "parameters": {"type": "object", "properties": {}},
            }],
        )
        self.assertEqual(turn.text, "Réponse outil compatible")

    def test_sdk_error_does_not_leak_raw_error_text(self) -> None:
        class ApiError(RuntimeError):
            status_code = 429

        error = MistralProvider._api_error(
            ApiError("key=should-not-appear"), operation="la génération"
        )
        self.assertEqual(error.category, "quota")
        self.assertIn("429", str(error))
        self.assertNotIn("should-not-appear", str(error))

    def test_type_error_keeps_safe_diagnostic_detail(self) -> None:
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "secret-test-key"}):
            error = MistralProvider._api_error(
                TypeError("invalid model list response; api_key=secret-test-key"),
                operation="la détection des modèles",
            )
        self.assertIn("invalid model list response", str(error))
        self.assertNotIn("secret-test-key", str(error))

    def test_model_discovery_reports_safe_type_error_detail(self) -> None:
        provider = MistralProvider()

        def fail_list():
            raise TypeError("unsupported model-list response; api_key=secret-test-key")

        provider._client = SimpleNamespace(models=SimpleNamespace(list=fail_list))
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "secret-test-key"}):
            with self.assertRaisesRegex(
                MistralProviderError, "unsupported model-list response"
            ) as raised:
                provider.list_available_models()
        self.assertNotIn("secret-test-key", str(raised.exception))

    def test_outdated_sdk_gets_clear_upgrade_message(self) -> None:
        provider = MistralProvider()
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-only"}),
            patch("providers.mistral.version", return_value="2.4.6"),
        ):
            with self.assertRaisesRegex(MistralProviderError, "trop ancien"):
                provider.list_available_models()
        self.assertIsNone(provider._client)

    def test_outdated_brotli_is_detected_before_creating_client(self) -> None:
        provider = MistralProvider()

        def fake_version(package: str) -> str:
            return {"mistralai": "3.3.0", "Brotli": "1.1.0"}[package]

        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-only"}),
            patch("providers.mistral.version", side_effect=fake_version),
        ):
            with self.assertRaisesRegex(
                MistralProviderError, "Brotli 1.1.0 est incompatible"
            ) as raised:
                provider.list_available_models()
        self.assertEqual(raised.exception.category, "configuration")
        self.assertIn("requirements.txt", str(raised.exception))
        self.assertIsNone(provider._client)

    def test_reported_brotli_type_error_has_targeted_remedy(self) -> None:
        error = MistralProvider._api_error(
            TypeError("process() takes no keyword arguments"),
            operation="la détection des modèles",
        )
        self.assertEqual(error.category, "configuration")
        self.assertIn("Brotli>=1.2.0", str(error))
        self.assertIn("requirements.txt", str(error))


class MistralMenuTests(unittest.TestCase):
    def test_api_menu_offers_each_accessible_mistral_model(self) -> None:
        class FakeMistralProvider:
            def __init__(self, model=None):
                self.model = model

            def list_available_models(self):
                return [
                    {"model": "mistral-small-latest", "display_name": "Small"},
                    {"model": "mistral-large-latest", "display_name": "Large"},
                ]

            def select_model(self, model):
                self.model = model

        settings = {
            "providers": {
                "openai": {"enabled": False},
                "gemini": {"enabled": False},
                "mistral": {"enabled": True, "model": "mistral-small-latest"},
            }
        }
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"MISTRAL_API_KEY": "test-only"}, clear=True),
            patch.object(main, "MistralProvider", FakeMistralProvider),
            patch.object(main.importlib.util, "find_spec", return_value=object()),
            patch("builtins.input", return_value="2"),
            redirect_stdout(output),
        ):
            selection = main.choisir_llm_api(settings)
        self.assertEqual(selection[0], "mistral")
        self.assertEqual(selection[1].model, "mistral-large-latest")
        self.assertIn("Mistral — mistral-small-latest", output.getvalue())
        self.assertIn("Mistral — mistral-large-latest", output.getvalue())

    def test_missing_mistral_key_is_not_selectable(self) -> None:
        settings = {
            "providers": {
                "openai": {"enabled": False},
                "gemini": {"enabled": False},
                "mistral": {"enabled": True, "model": "mistral-small-latest"},
            }
        }
        output = io.StringIO()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(main.importlib.util, "find_spec", return_value=object()),
            redirect_stdout(output),
        ):
            selection = main.choisir_llm_api(settings, requested_model="mistral-small-latest")
        self.assertIsNone(selection)
        self.assertIn("Mistral — clé API absente", output.getvalue())
        self.assertIn("Aucun LLM distant disponible", output.getvalue())

    def test_harness_registers_selected_mistral_provider(self) -> None:
        provider = MistralProvider("mistral-small-latest")
        orchestrator = main.construire_harness(
            provider,
            "mistral",
            {"providers": {"mistral": {"enabled": True}}},
            mode="api",
        )
        self.assertIs(orchestrator.router.providers["mistral"], provider)

    def test_mistral_config_is_parsed(self) -> None:
        from pathlib import Path

        config = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
        settings = load_config(config)
        self.assertTrue(settings["providers"]["mistral"]["enabled"])
        self.assertEqual(
            settings["providers"]["mistral"]["model"], "mistral-small-latest"
        )


if __name__ == "__main__":
    unittest.main()
