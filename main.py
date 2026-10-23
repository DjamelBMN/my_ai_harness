# RÔLE DE CE FICHIER :
# Point d'entrée interactif. Il demande le mode, détecte les providers réellement
# utilisables, laisse choisir le LLM puis le relie aux quatre Agents du harness.

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from core.context import Context
from core.agent_loop import AgentLoop
from core.agent_registry import AgentRegistry
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy, RiskLevel
from core.planner import ClarificationRequired
from core.router import ModelRouter, load_config
from core.task import Task
from providers.gemini import GeminiProvider, GeminiProviderError
from providers.ollama import OllamaProvider, OllamaProviderError
from providers.openai import OpenAIProvider, OpenAIProviderError
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from skills.router import SkillCommandError, SkillRouter
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parent


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime agentique My AI Harness")
    parser.add_argument("task", nargs="?", help="Mission à lancer après le choix du mode et du LLM")
    parser.add_argument("--agent", help="Clé d'un agent découvert dans le paquet agents/")
    parser.add_argument("--model", help="ID exact d'un modèle proposé")
    parser.add_argument("--workspace", help="Racine de fichiers autorisée pour cette exécution")
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--dry-run", action="store_true", help="Bloque écritures, déplacements, suppressions et tests")
    parser.add_argument("--autonomous", action="store_true", help="Autorise les outils mutateurs sans confirmation")
    parser.add_argument("--verbose", action="store_true", help="Affiche le détail structuré de la mission")
    args = parser.parse_args(argv)
    if args.max_iterations < 1 or args.max_iterations > 20:
        parser.error("--max-iterations doit être compris entre 1 et 20")
    if args.max_output_tokens < 128 or args.max_output_tokens > 32_768:
        parser.error("--max-output-tokens doit être compris entre 128 et 32768")
    return args


def charger_configuration() -> dict:
    """Charge les noms de modèles et les options depuis config/config.yaml."""
    return load_config(PROJECT_ROOT / "config" / "config.yaml")


def construire_harness(
    provider,
    provider_key: str,
    settings: dict | None = None,
    *,
    mode: str = "local",
) -> Orchestrator:
    """Construit les Agents et enregistre les providers réellement disponibles."""
    agents = AgentRegistry.from_package()
    providers = {provider_key: provider}
    settings = settings or {}
    if mode == "api":
        provider_options = settings.get("providers", {})

        openai_options = provider_options.get("openai", {})
        if (
            provider_key != "openai"
            and openai_options.get("enabled", False)
            and _credential_exists("OPENAI_API_KEY")
            and importlib.util.find_spec("openai") is not None
            and isinstance(openai_options.get("model"), str)
        ):
            providers["openai"] = OpenAIProvider(model=openai_options["model"])

        gemini_options = provider_options.get("gemini", {})
        if (
            provider_key == "gemini"
            and isinstance(provider, GeminiProvider)
        ):
            providers["gemini"] = provider
            if provider.supports_model("gemini-3.5-flash-lite"):
                providers["gemini_flash_lite"] = provider.with_model(
                    "gemini-3.5-flash-lite"
                )
        elif (
            gemini_options.get("enabled", False)
            and _credential_exists("GEMINI_API_KEY")
            and importlib.util.find_spec("google.genai") is not None
        ):
            candidate = GeminiProvider(model=gemini_options.get("model"))
            try:
                models = candidate.list_available_models()
                model_ids = {item["model"] for item in models}
                preferred = gemini_options.get("model")
                selected = preferred if preferred in model_ids else None
                if selected is None and "gemini-3.5-flash-lite" in model_ids:
                    selected = "gemini-3.5-flash-lite"
                if selected is None:
                    selected = sorted(model_ids, key=str.casefold)[0]
                candidate.select_model(selected)
                providers["gemini"] = candidate
                if candidate.supports_model("gemini-3.5-flash-lite"):
                    providers["gemini_flash_lite"] = candidate.with_model(
                        "gemini-3.5-flash-lite"
                    )
            except GeminiProviderError as error:
                print(f"[ROUTER] Gemini non enregistré : {error}")

    agent_provider_map = {
        agent.routing_key: provider_key for agent in agents.agents.values()
    }
    router = ModelRouter(
        providers=providers,
        agent_provider_map=agent_provider_map,
        default_provider=provider_key,
        task_provider_map=settings.get("routing", {}),
    )
    orchestrator = Orchestrator(agents=agents, router=router, context=Context())
    skills_root = PROJECT_ROOT / "skills"
    skill_registry = SkillRegistry.from_directory(skills_root)
    orchestrator.skill_registry = skill_registry
    orchestrator.skill_loader = SkillLoader(skills_root)
    orchestrator.skill_router = SkillRouter(skill_registry, orchestrator.skill_loader)
    return orchestrator


def creer_tache(
    message: str,
    agent_override: str | None = None,
    known_agents=None,
) -> Task:
    """Accepte un préfixe correspondant à un agent découvert, ou --agent."""
    prefix, separator, description = message.partition(":")
    agent_type = prefix.strip().lower()
    accepted = set(known_agents or {"coder", "tester", "reviewer", "researcher"})
    if separator and agent_type in accepted:
        return Task(description=description.strip(), type=agent_type, explicit_agent=True)
    if agent_override:
        return Task(description=message.strip(), type=agent_override, explicit_agent=True)
    return Task(description=message.strip(), type="researcher")


def choisir_mode() -> str | None:
    """Demande le mode avant toute détection de provider ou création d'agent."""
    while True:
        print("=" * 40)
        print("        MY AI HARNESS")
        print("=" * 40)
        print("\nChoisis le mode :\n")
        print("[1] LOCAL")
        print("[2] API DISTANTE")
        try:
            choice = input("\nTon choix : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nArrêt du harness.")
            return None

        if choice == "1":
            return "local"
        if choice == "2":
            return "api"
        if choice in {"exit", "q"}:
            print("Arrêt du harness.")
            return None
        print("Choix invalide. Saisis 1, 2 ou exit.\n")


def choisir_llm_local(settings: dict, requested_model: str | None = None):
    """Détecte Ollama et le modèle local avant de le proposer au choix."""
    ollama_options = settings.get("providers", {}).get("ollama", {})
    model = ollama_options.get("model", OllamaProvider.DEFAULT_MODEL)
    print("\nMode sélectionné : LOCAL")
    print("\nLLM locaux disponibles :\n")
    if not ollama_options.get("enabled", True):
        print("Aucun LLM local disponible (Ollama est désactivé dans la configuration).")
        return None

    provider = OllamaProvider(model=model)
    try:
        provider.check_available()
    except OllamaProviderError as error:
        print(f"Ollama indisponible : {error}")
        print("Aucun LLM local disponible.")
        return None

    print("[OK] Ollama connecté")
    print(f"[OK] {model} installé")
    if requested_model:
        if requested_model.casefold() != model.casefold():
            print(f"Modèle local demandé indisponible : {requested_model}")
            return None
        return "ollama", provider
    print(f"\n[1] Ollama — {model}")
    while True:
        try:
            choice = input("\nChoisis ton LLM : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nArrêt du harness.")
            return None
        if choice == "1":
            return "ollama", provider
        if choice in {"exit", "q"}:
            print("Arrêt du harness.")
            return None
        print("Choix invalide. Saisis 1 ou exit.")


def _credential_exists(*names: str) -> bool:
    """Vérifie uniquement la présence d'une variable, sans révéler sa valeur."""
    return any(os.environ.get(name, "").strip() for name in names)


def choisir_llm_api(settings: dict, requested_model: str | None = None):
    """Liste les providers distants utilisables et les modèles Gemini accessibles."""
    provider_settings = settings.get("providers", {})
    openai_options = provider_settings.get("openai", {})
    model = openai_options.get("model")
    display_model = (
        model.replace("gpt-", "GPT-")
        if isinstance(model, str) and model.strip()
        else "modèle non configuré"
    )
    print("\nMode sélectionné : API DISTANTE")
    print("\nLLM disponibles :\n")

    # Chaque option garde le provider et le modèle choisi (s'il y en a un).
    available = []
    if not openai_options.get("enabled", False):
        print(f"OpenAI — {display_model} : désactivé dans config/config.yaml")
    elif not isinstance(model, str) or not model.strip():
        print("OpenAI : modèle absent de config/config.yaml")
    elif not _credential_exists("OPENAI_API_KEY"):
        print(f"OpenAI — {display_model} : clé API absente")
    elif importlib.util.find_spec("openai") is None:
        print(f"OpenAI — {display_model} : SDK OpenAI absent")
    else:
        available.append(("openai", OpenAIProvider(model=model), model))
        print("[OK] OpenAI configuré")
        print(f"[OK] Modèle : {display_model}")
        print(f"[{len(available)}] OpenAI — {display_model}")

    gemini_options = provider_settings.get("gemini", {})
    preferred_gemini_model = gemini_options.get("model")
    claude_configured = _credential_exists("ANTHROPIC_API_KEY")
    if not gemini_options.get("enabled", False):
        print("Gemini — désactivé dans config/config.yaml")
    elif not _credential_exists("GEMINI_API_KEY"):
        print("Gemini — clé API absente")
    elif importlib.util.find_spec("google.genai") is None:
        print("Gemini — SDK google-genai absent")
    else:
        gemini_provider = GeminiProvider(
            model=(
                preferred_gemini_model
                if isinstance(preferred_gemini_model, str)
                and preferred_gemini_model.strip()
                else None
            )
        )
        try:
            gemini_models = gemini_provider.list_available_models()
        except GeminiProviderError as error:
            if error.category == "configuration":
                print(error)
            elif error.category == "authentication":
                print("Gemini — clé API refusée")
            else:
                print(f"Gemini — indisponible : {error}")
        else:
            print("[OK] Gemini configuré")
            # Le modèle de config est une préférence de tri, pas une restriction.
            gemini_models.sort(
                key=lambda item: (
                    item["model"] != preferred_gemini_model,
                    item["display_name"].casefold(),
                    item["model"].casefold(),
                )
            )
            print("Modèles Gemini accessibles prenant en charge generateContent :")
            for model_info in gemini_models:
                model_id = model_info["model"]
                display_name = model_info["display_name"]
                preferred_label = (
                    " (préférence config)"
                    if model_id == preferred_gemini_model
                    else ""
                )
                available.append(("gemini", gemini_provider, model_id))
                print(
                    f"[{len(available)}] Gemini — {display_name} "
                    f"({model_id}){preferred_label}"
                )

    if claude_configured:
        print("Claude — credentials présents, provider API pas encore connecté")
    else:
        print("Claude — non configuré")

    if not available:
        print("\nAucun LLM distant disponible.")
        if not _credential_exists("OPENAI_API_KEY", "GEMINI_API_KEY"):
            print("Vérifiez OPENAI_API_KEY ou GEMINI_API_KEY.")
        return None

    if requested_model:
        match = next(
            (
                item for item in available
                if item[2] and item[2].casefold() == requested_model.casefold()
            ),
            None,
        )
        if match is None:
            print(f"Modèle demandé indisponible : {requested_model}")
            return None
        provider_key, provider, selected_model = match
        if provider_key == "gemini":
            provider.select_model(selected_model)
        return provider_key, provider

    while True:
        try:
            choice = input("\nChoisis ton LLM : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nArrêt du harness.")
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(available):
            provider_key, provider, selected_model = available[int(choice) - 1]
            if provider_key == "gemini":
                provider.select_model(selected_model)
            return provider_key, provider
        if choice in {"exit", "q"}:
            print("Arrêt du harness.")
            return None
        print("Choix invalide. Seuls les LLM listés comme disponibles sont sélectionnables.")


def afficher_harness_pret(mode: str, provider_key: str, provider, agents=None) -> None:
    """Affiche le mode actif, le modèle choisi et les commandes d'Agent."""
    family = {
        "ollama": "Ollama",
        "openai": "OpenAI",
        "gemini": "Gemini",
    }.get(provider_key, provider_key)
    print("\n" + "=" * 40)
    print("        MY AI HARNESS")
    print("=" * 40)
    print(f"Mode : {'LOCAL' if mode == 'local' else 'API DISTANTE'}")
    print(f"LLM : {family}")
    print(f"Modèle : {provider.get_model_name()}")
    print("\nAgents disponibles :")
    keys = sorted(agents or {"coder", "tester", "reviewer", "researcher"})
    for key in keys:
        print(f"- {key}:")
    print("\nTape exit pour arrêter.\n")


def _confirmation_outil(name: str, risk: RiskLevel) -> bool:
    try:
        answer = input(
            f"\nAutoriser l'outil {name} (risque {risk.name}) ? "
            "Tape oui pour continuer : "
        ).strip().casefold()
    except (EOFError, KeyboardInterrupt):
        print("\nConfirmation annulée.")
        return False
    return answer in {"oui", "o", "yes", "y"}


def _construire_boucle(args: argparse.Namespace) -> AgentLoop:
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else PROJECT_ROOT
    if args.workspace and (not workspace.exists() or not workspace.is_dir()):
        raise ValueError("Le workspace fourni doit déjà exister et être un dossier.")
    filesystem = WorkspaceFilesystem(workspace)
    permissions = PermissionPolicy(
        confirm=_confirmation_outil,
        dry_run=args.dry_run,
        autonomous=args.autonomous,
    )
    registry = ToolRegistry(filesystem, permissions)
    return AgentLoop(
        registry,
        max_iterations=args.max_iterations,
        max_retries=2,
    )


def _executer_harness(
    mode: str,
    provider_key: str,
    provider,
    settings: dict,
    args: argparse.Namespace,
) -> None:
    """Démarre le runtime agentique avec la sélection existante de provider."""
    orchestrator = construire_harness(
        provider, provider_key, settings, mode=mode
    )
    for registered_provider in orchestrator.router.providers.values():
        if hasattr(registered_provider, "max_output_tokens"):
            registered_provider.max_output_tokens = args.max_output_tokens
    loop = _construire_boucle(args)
    afficher_harness_pret(mode, provider_key, provider, orchestrator.agent_registry.agents)

    if args.dry_run:
        print("Mode dry-run : aucune modification, commande ou suite de tests ne sera exécutée.")
    elif args.autonomous:
        print("Mode autonome activé : les outils mutateurs ne demanderont pas de confirmation.")

    if args.task is not None:
        _executer_mission(orchestrator, loop, args.task, args)
        return

    while True:
        try:
            message = input("Que veux-tu faire ? ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nArrêt du harness.")
            return

        if message.lower() == "exit":
            print("Arrêt du harness.")
            return
        if not message:
            continue

        try:
            _executer_mission(orchestrator, loop, message, args)
        except (OpenAIProviderError, OllamaProviderError, GeminiProviderError) as error:
            print(f"Erreur du provider : {error}")
        except (KeyError, RuntimeError, ValueError) as error:
            print(f"Erreur du harness : {error}")


def _executer_mission(orchestrator, loop: AgentLoop, message: str, args) -> None:
    try:
        launch = orchestrator.skill_router.resolve(message)
    except SkillCommandError as error:
        print(f"[SKILL ERROR] {error}")
        return

    if launch is not None:
        skill = launch.skill
        agent = skill.agent
        skill_path = skill.path.relative_to(PROJECT_ROOT).as_posix()
        print(f"[SLASH] /{launch.command.name}")
        print(f"[SKILL] {skill.display_name}")
        print(f"[SKILL PATH] {skill_path}")
        print(f"[SKILL SOURCE] {skill_path}/skill.md")
        if agent is None:
            print(f"[SKILL ERROR] /{skill.name} ne définit pas d'agent compatible dans agent.py.")
            return
        print(f"[AGENT] {agent.name}")
        print(f"[MISSION] {launch.command.mission}")
        if not launch.command.mission:
            print(f"Décris la mission après /{skill.name}, par exemple : /{skill.name} <mission>")
            return
        task = Task(
            description=launch.command.mission,
            type=agent.routing_key,
            explicit_agent=True,
            skill=skill,
        )
    else:
        known_agents = orchestrator.agent_registry.agents
        agent_override = args.agent
        if agent_override:
            try:
                agent_override = orchestrator.agent_registry.resolve(agent_override)[0]
            except KeyError as error:
                print(f"Agent indisponible : {error}")
                return
        task = creer_tache(
            message,
            agent_override,
            set(known_agents) | set(orchestrator.agent_registry.aliases),
        )
    try:
        result = orchestrator.run_agentic(task, loop)
    except ClarificationRequired as error:
        print(f"Clarification nécessaire : {error}")
        return
    if args.verbose:
        print("\n[OBSERVATIONS STRUCTURÉES]")
        print(json.dumps(result.observations, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> None:
    """Demande le mode, puis le LLM, et ne lance un Agent qu'après ces choix."""
    if hasattr(sys.stdout, "reconfigure"):
        # Certains terminaux Windows ne peuvent pas encoder les emojis générés.
        sys.stdout.reconfigure(errors="replace")

    args = _arguments(argv)
    try:
        settings = charger_configuration()
    except (OSError, ValueError) as error:
        print(f"Erreur de configuration : {error}")
        return

    while True:
        mode = choisir_mode()
        if mode is None:
            return

        selection = (
            choisir_llm_local(settings, args.model)
            if mode == "local"
            else choisir_llm_api(settings, args.model)
        )
        if selection is None:
            # Si aucun provider n'est disponible, l'utilisateur peut choisir l'autre mode.
            continue

        provider_key, provider = selection
        if hasattr(provider, "max_output_tokens"):
            provider.max_output_tokens = args.max_output_tokens
        try:
            _executer_harness(mode, provider_key, provider, settings, args)
        except (OpenAIProviderError, OllamaProviderError, GeminiProviderError) as error:
            print(f"Erreur du provider : {error}")
        except (OSError, ValueError, RuntimeError) as error:
            print(f"Erreur du harness : {error}")
        return


if __name__ == "__main__":
    main()
