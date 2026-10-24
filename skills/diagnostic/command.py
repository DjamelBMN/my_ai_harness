# RÔLE DE CE FICHIER : inspecte localement les composants sans appeler les LLM
# distants ni prétendre avoir exécuté la suite de tests.

from __future__ import annotations

import os
from pathlib import Path

from providers.ollama import OllamaProviderError
from tools.registry import ToolCall


ENVIRONMENT_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
}


def _line(mark: str, text: str) -> None:
    print(f"{mark} {text}")


def _provider_diagnostics(runtime) -> None:
    print("\nProviders")
    router = runtime.orchestrator.router
    config = runtime.settings.get("providers", {})
    for family in ("gemini", "mistral", "openai", "claude", "ollama"):
        keys = [
            key for key in router.providers
            if key == family or (family == "gemini" and key.startswith("gemini"))
        ]
        env_name = ENVIRONMENT_KEYS.get(family)
        has_key = bool(os.environ.get(env_name, "").strip()) if env_name else False
        if keys:
            provider = router.providers[keys[0]]
            if family == "ollama":
                try:
                    provider.check_available()
                except OllamaProviderError as error:
                    _line("✗", f"Ollama / {provider.get_model_name()} — {error}")
                else:
                    _line("✓", f"Ollama / {provider.get_model_name()} — service et modèle vérifiés")
            elif env_name and not has_key:
                _line("✗", f"{family} / {provider.get_model_name()} — clé API absente maintenant")
            else:
                _line(
                    "✓",
                    f"{family} / {provider.get_model_name()} — instance et credentials présents; API distante non sondée",
                )
            continue

        provider_config = config.get(family, {})
        model = provider_config.get("model", "modèle non configuré")
        if family == "claude":
            _line("⚠", "Claude — provider API non connecté")
        elif family == "ollama":
            _line("⚠", f"Ollama / {model} — non chargé dans cette session")
        elif not provider_config.get("enabled", False):
            _line("⚠", f"{family} / {model} — désactivé dans config/config.yaml")
        elif not has_key:
            _line("✗", f"{family} / {model} — clé API absente")
        else:
            _line("⚠", f"{family} / {model} — clé présente, provider non initialisé")


def _skill_diagnostics(runtime):
    print("\nSkills")
    registry = getattr(runtime.orchestrator, "skill_registry", None)
    loader = getattr(runtime.orchestrator, "skill_loader", None)
    if registry is None or loader is None:
        _line("✗", "Registre ou SkillLoader absent")
        return []

    for name, reason in registry.invalid.items():
        _line("⚠", f"/{name} — non découvert : {reason}")

    loaded = []
    for descriptor in registry.list_skills():
        try:
            definition = loader.load(descriptor)
        except Exception as error:
            _line("✗", f"/{descriptor.name} — chargement impossible ({type(error).__name__})")
            continue
        loaded.append((descriptor, definition))
        _line("✓", f"/{descriptor.name} — {definition.display_name} chargé")
    return loaded


def handle(runtime, mission, skill):
    print("MY AI HARNESS — DIAGNOSTIC")
    _provider_diagnostics(runtime)

    loaded_skills = _skill_diagnostics(runtime)

    print("\nAgents")
    for agent in runtime.orchestrator.agent_registry.list_agents():
        _line("✓", agent.name)

    print("\nTools")
    for tool in runtime.agent_loop.tools.discover():
        _line("✓", tool.name)

    print("\nRAG et templates")
    for descriptor, definition in loaded_skills:
        _line(
            "✓",
            f"/{descriptor.name} — RAG {len(definition.rag_resources)}, "
            f"templates {len(definition.available_templates)}",
        )

    print("\nWorkspace / configuration")
    workspace = runtime.workspace
    _line("✓" if workspace.is_dir() else "✗", f"Workspace : {workspace}")
    _line(
        "✓" if runtime.settings else "⚠",
        "Configuration chargée" if runtime.settings else "Configuration absente de la session",
    )

    print("\nTests")
    test_root = Path(__file__).resolve().parents[2] / "tests"
    test_files = list(test_root.glob("test_*.py")) if test_root.is_dir() else []
    _line("⚠", f"{len(test_files)} fichiers de tests trouvés; aucun test exécuté par /diagnostic")

    print("\nGit")
    result = runtime.agent_loop.tools.execute(ToolCall("git_status", {}))
    _line(
        "✓" if result.status == "success" else "⚠",
        "Dépôt interrogé" if result.status == "success" else "Statut indisponible : " + result.summary,
    )
    router = runtime.orchestrator.router
    print(
        f"\nRoutage : {'automatique' if router.automatic_routing else 'provider épinglé'}; "
        f"dernier provider : {router.last_provider_key}"
    )
