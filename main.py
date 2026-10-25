# RÔLE DE CE FICHIER :
# Point d'entrée interactif. Il demande le mode, détecte les providers réellement
# utilisables, laisse choisir le LLM puis le relie aux quatre Agents du harness.

import argparse
import importlib.util
import json
import os
import re
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
from core.events import EventTranslator
from core.memory import MemoryManager
from core.modes import HarnessMode, ModeManager
from providers.gemini import GeminiProvider, GeminiProviderError
from providers.mistral import MistralProvider, MistralProviderError
from providers.ollama import OllamaProvider, OllamaProviderError
from providers.openai import OpenAIProvider, OpenAIProviderError
from skills.loader import SkillLoader
from skills.registry import SkillRegistry
from skills.router import SkillCommandError, SkillRouter
from skills.runtime import SkillRuntime
from tools.filesystem import WorkspaceFilesystem
from tools.registry import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parent
SHIFT_TAB = "\x00SHIFT_TAB"


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Runtime agentique My AI Harness")
    parser.add_argument("task", nargs="?", help="Mission à lancer après le choix du mode et du LLM")
    parser.add_argument("--agent", help="Clé d'un agent découvert dans le paquet agents/")
    parser.add_argument("--model", help="ID exact d'un modèle proposé")
    parser.add_argument("--workspace", help="Racine de fichiers autorisée pour cette exécution")
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    parser.add_argument("--dry-run", action="store_true", help="Bloque écritures, déplacements, suppressions et tests")
    parser.add_argument("--autonomous", action="store_true", help="Démarre en AUTO et autorise explicitement les outils mutateurs sans confirmation")
    parser.add_argument("--verbose", action="store_true", help="Affiche le détail structuré de la mission")
    parser.add_argument("--ui", action="store_true", help="Démarre l'interface graphique web NeoHarness AI (Operating Environment)")
    parser.add_argument("--replay", help="Rejoue une mission enregistrée par son run_id")
    parser.add_argument("--port", type=int, default=8765, help="Port HTTP local pour l'interface --ui (défaut : 8765)")
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

        mistral_options = provider_options.get("mistral", {})
        if provider_key == "mistral" and isinstance(provider, MistralProvider):
            providers["mistral"] = provider
        elif (
            mistral_options.get("enabled", False)
            and _credential_exists("MISTRAL_API_KEY")
            and importlib.util.find_spec("mistralai") is not None
        ):
            candidate = MistralProvider(model=mistral_options.get("model"))
            try:
                models = candidate.list_available_models()
                model_ids = {item["model"] for item in models}
                preferred = mistral_options.get("model")
                selected = preferred if preferred in model_ids else None
                if selected is None:
                    selected = sorted(model_ids, key=str.casefold)[0]
                candidate.select_model(selected)
                providers["mistral"] = candidate
            except MistralProviderError as error:
                print(f"[ROUTER] Mistral non enregistré : {error}")

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
    """Liste les providers distants utilisables et leurs modèles accessibles."""
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

    mistral_options = provider_settings.get("mistral", {})
    preferred_mistral_model = mistral_options.get("model")
    if not mistral_options.get("enabled", False):
        print("Mistral — désactivé dans config/config.yaml")
    elif not _credential_exists("MISTRAL_API_KEY"):
        print("Mistral — clé API absente")
    elif importlib.util.find_spec("mistralai") is None:
        print("Mistral — SDK mistralai absent; lance python -m pip install -r requirements.txt")
    else:
        mistral_provider = MistralProvider(
            model=(
                preferred_mistral_model
                if isinstance(preferred_mistral_model, str)
                and preferred_mistral_model.strip()
                else None
            )
        )
        try:
            mistral_models = mistral_provider.list_available_models()
        except MistralProviderError as error:
            if error.category == "authentication":
                print("Mistral — clé API refusée")
            else:
                print(f"Mistral — indisponible : {error}")
        else:
            print("[OK] Mistral configuré")
            mistral_models.sort(
                key=lambda item: (
                    item["model"] != preferred_mistral_model,
                    item["model"].casefold(),
                )
            )
            print("Modèles Mistral accessibles prenant en charge le chat :")
            for model_info in mistral_models:
                model_id = model_info["model"]
                preferred_label = (
                    " (préférence config)"
                    if model_id == preferred_mistral_model
                    else ""
                )
                available.append(("mistral", mistral_provider, model_id))
                print(f"[{len(available)}] Mistral — {model_id}{preferred_label}")

    if not available:
        print("\nAucun LLM distant disponible.")
        if not _credential_exists(
            "OPENAI_API_KEY", "GEMINI_API_KEY", "MISTRAL_API_KEY"
        ):
            print("Vérifiez OPENAI_API_KEY, GEMINI_API_KEY ou MISTRAL_API_KEY.")
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
        if provider_key in {"gemini", "mistral"}:
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
            if provider_key in {"gemini", "mistral"}:
                provider.select_model(selected_model)
            return provider_key, provider
        if choice in {"exit", "q"}:
            print("Arrêt du harness.")
            return None
        print("Choix invalide. Seuls les LLM listés comme disponibles sont sélectionnables.")


def afficher_harness_pret(
    mode: str,
    provider_key: str,
    provider,
    agents=None,
    *,
    work_mode: str = "ACCEPT",
) -> None:
    """Affiche le mode actif, le modèle choisi et les commandes d'Agent."""
    family = {
        "ollama": "Ollama",
        "openai": "OpenAI",
        "gemini": "Gemini",
        "mistral": "Mistral",
    }.get(provider_key, provider_key)
    print("\n" + render_mode_panel(work_mode))
    print(f"Connexion LLM : {'LOCAL' if mode == 'local' else 'API DISTANTE'}")
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


def _preview_edit(name: str, arguments: dict) -> None:
    """Présente la cible et la nature de l'écriture avant l'outil EDIT."""
    path = str(arguments.get("path", "chemin non fourni"))
    print("\n[EDIT MODE]")
    print("Modification prévue :")
    print(f"`{path}`")
    if name == "write_file":
        exists = bool(arguments.get("overwrite"))
        action = "Remplacer le contenu existant" if exists else "Créer le fichier"
        content = arguments.get("content", "")
        print(f"Action : {action} ({len(content)} caractères).")
    else:
        old_text = str(arguments.get("old_text", ""))
        new_text = str(arguments.get("new_text", ""))
        print("Action : remplacer le texte ciblé dans ce fichier.")
        print(f"Cible : {old_text[:120]!r}")
        print(f"Nouveau texte : {new_text[:120]!r}")


def _is_shift_tab_input(value: str) -> bool:
    return value in {"\x1b[Z", "\x00\x0f", "\xe0\x0f", SHIFT_TAB}


def _terminal_supports_unicode() -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "┌─│●".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _terminal_supports_ansi() -> bool:
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return False
    if os.environ.get("NO_COLOR") is not None or os.environ.get("TERM", "").casefold() == "dumb":
        return False
    if os.name == "nt":
        return bool(
            os.environ.get("WT_SESSION")
            or os.environ.get("ANSICON")
            or os.environ.get("ConEmuANSI", "").casefold() == "on"
            or os.environ.get("TERM")
        )
    return True


def render_mode_panel(
    mode: str | HarnessMode,
    *,
    unicode: bool | None = None,
    color: bool | None = None,
) -> str:
    """Construit le panneau de modes avec fallback ASCII et sans couleur."""
    selected = ModeManager.normalize(mode)
    use_unicode = _terminal_supports_unicode() if unicode is None else unicode
    use_color = _terminal_supports_ansi() if color is None else color
    width = 53
    if use_unicode:
        top, top_right, side, bottom, bottom_right, horizontal = (
            "┌", "┐", "│", "└", "┘", "─"
        )
        marker = "●"
    else:
        top, top_right, side, bottom, bottom_right, horizontal = (
            "+", "+", "|", "+", "+", "-"
        )
        marker = "*"

    reset = "\x1b[0m"
    accent = "\x1b[1;36m"
    badge = f"{marker} {selected.value}"
    if use_color:
        badge = f"{accent}{badge}{reset}"
    tabs = []
    for item in ModeManager.CYCLE:
        label = f"{marker} {item.value}" if item is selected else item.value
        tab = f"[{label}]"
        tabs.append(f"{accent}{tab}{reset}" if use_color and item is selected else tab)
    content_lines = [
        "MY AI HARNESS",
        "",
        f"Mode : {badge}",
        "",
        "   ".join(tabs),
        "",
        "Shift+Tab : changer de mode",
        "/mode <nom> : sélectionner directement",
    ]
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    lines = [top + horizontal * width + top_right]
    for content in content_lines:
        visible_width = len(ansi.sub("", content))
        lines.append(f"{side} {content}{' ' * max(0, width - visible_width - 1)}{side}")
    lines.append(bottom + horizontal * width + bottom_right)
    return "\n".join(lines)


def _read_windows_console_line(prompt: str) -> str:
    """Lit une ligne Windows en interceptant Shift+Tab sans changer de Skill."""
    import msvcrt

    sys.stdout.write(prompt)
    sys.stdout.flush()
    characters: list[str] = []
    while True:
        character = msvcrt.getwch()
        if character == "\r":
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(characters)
        if character == "\x03":
            raise KeyboardInterrupt
        if character == "\x08":
            if characters:
                characters.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if character == "\x0f":
            sys.stdout.write("\n")
            sys.stdout.flush()
            return SHIFT_TAB
        if character in {"\x00", "\xe0"}:
            scan_code = msvcrt.getwch()
            if scan_code == "\x0f":
                sys.stdout.write("\n")
                sys.stdout.flush()
                return SHIFT_TAB
            continue
        if character == "\x1b":
            # Windows Terminal peut transmettre la séquence ANSI Shift+Tab.
            following = msvcrt.getwch()
            if following == "[" and msvcrt.getwch() == "Z":
                sys.stdout.write("\n")
                sys.stdout.flush()
                return SHIFT_TAB
            continue
        characters.append(character)
        sys.stdout.write(character)
        sys.stdout.flush()


def _read_prompt_toolkit_line(prompt: str, *, input=None, output=None) -> str:
    """Use terminal key events so BackTab is not reduced to a submitted string."""
    from prompt_toolkit import PromptSession
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys

    bindings = KeyBindings()

    @bindings.add(Keys.BackTab)
    def _change_mode(event) -> None:
        event.app.exit(result=SHIFT_TAB)

    options = {
        "key_bindings": bindings,
        "complete_while_typing": False,
        "enable_history_search": False,
    }
    if input is not None:
        options["input"] = input
    if output is not None:
        options["output"] = output
    return PromptSession(**options).prompt(prompt)


def lire_commande_harness(prompt: str) -> str:
    """Capture BackTab au niveau du CLI; garde un fallback sans dépendance."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            return _read_prompt_toolkit_line(prompt)
        except ImportError:
            if os.name == "nt":
                return _read_windows_console_line(prompt)
    answer = input(prompt)
    return SHIFT_TAB if _is_shift_tab_input(answer) else answer


def _afficher_etat_session(runtime: SkillRuntime) -> None:
    """Affiche le mode et le LLM actifs sans révéler de credential."""
    manager = runtime.mode_manager
    if manager is not None:
        print(f"[MODE] {manager.current.value}")
    router = runtime.orchestrator.router
    provider_key = (
        router.session_provider_key
        if not router.automatic_routing
        else router.last_provider_key
    )
    provider = router.providers.get(provider_key)
    if provider is not None:
        print(f"[PROVIDER] {provider.get_name()}")
        print(f"[MODEL] {provider.get_model_name()}")


def _traiter_raccourci_mode(runtime: SkillRuntime, message: str) -> bool:
    """Applique le changement global immédiatement après la touche BackTab."""
    if message != SHIFT_TAB or runtime.mode_manager is None:
        return False
    previous, current = runtime.mode_manager.advance()
    print(f"[MODE] {previous.value} → {current.value}")
    print(render_mode_panel(current))
    return True


def _construire_boucle(args: argparse.Namespace) -> AgentLoop:
    workspace = Path(args.workspace).expanduser().resolve() if args.workspace else PROJECT_ROOT
    if args.workspace and (not workspace.exists() or not workspace.is_dir()):
        raise ValueError("Le workspace fourni doit déjà exister et être un dossier.")
    filesystem = WorkspaceFilesystem(workspace)
    permissions = PermissionPolicy(
        confirm=_confirmation_outil,
        dry_run=args.dry_run,
        autonomous=args.autonomous,
        edit_preview=_preview_edit,
    )
    registry = ToolRegistry(filesystem, permissions)
    translator = EventTranslator()

    def afficher_evenement(event) -> None:
        print(f"[SUPERVISION] {translator.translate(event)}")

    return AgentLoop(
        registry,
        max_iterations=args.max_iterations,
        max_retries=2,
        event_sink=afficher_evenement,
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
    runtime = SkillRuntime(
        orchestrator=orchestrator,
        agent_loop=loop,
        settings=settings,
        mode=mode,
        args=args,
        memory=MemoryManager(loop.tools),
    )
    initial_work_mode = (
        HarnessMode.PLAN
        if args.dry_run
        else HarnessMode.AUTO
        if args.autonomous
        else HarnessMode.ACCEPT
    )
    runtime.mode_manager = ModeManager(
        loop.tools.permissions,
        initial_work_mode,
        hard_dry_run=args.dry_run,
        on_change=lambda previous, current: loop._event(
            "mode.changed",
            previous=previous.value,
            current=current.value,
        ),
    )
    afficher_harness_pret(
        mode,
        provider_key,
        provider,
        orchestrator.agent_registry.agents,
        work_mode=runtime.mode_manager.current.value,
    )

    if args.dry_run:
        print("Mode dry-run : aucune modification, commande ou suite de tests ne sera exécutée.")
    elif args.autonomous:
        print(
            "Option --autonomous explicite : elle contourne les confirmations; "
            "le mode AUTO seul ne change pas les permissions."
        )

    if args.task is not None:
        _executer_mission(orchestrator, loop, args.task, args, runtime=runtime)
        return

    while True:
        try:
            prompt = f"[{runtime.mode_manager.current.value}] Que veux-tu faire ? "
            message = lire_commande_harness(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nArrêt du harness.")
            return

        if _traiter_raccourci_mode(runtime, message):
            continue
        if message.lower().startswith("replay "):
            run_id = message.split(maxsplit=1)[1].strip()
            from core.replay import replay_mission
            replay_mission(run_id, log_dir=loop.tools.filesystem.root / ".harness")
            continue
        if message.lower() == "exit":
            print("Arrêt du harness.")
            return
        if not message:
            continue

        try:
            _executer_mission(orchestrator, loop, message, args, runtime=runtime)
        except (OpenAIProviderError, OllamaProviderError, GeminiProviderError) as error:
            print(f"Erreur du provider : {error}")
        except (KeyError, RuntimeError, ValueError) as error:
            print(f"Erreur du harness : {error}")


def _executer_mission(
    orchestrator,
    loop: AgentLoop,
    message: str,
    args,
    *,
    runtime: SkillRuntime | None = None,
) -> None:
    direct_agent_task: Task | None = None
    try:
        launch = orchestrator.skill_router.resolve(message)
    except SkillCommandError as error:
        try:
            command = orchestrator.skill_router.parse(message)
        except SkillCommandError:
            command = None
        if command is None:
            print(f"[SKILL ERROR] {error}")
            return
        try:
            _agent_key, direct_agent = orchestrator.agent_registry.resolve(command.name)
        except KeyError:
            print(f"[SKILL ERROR] {error}")
            return
        if not command.mission:
            print(f"Décris la mission après /{command.name}.")
            return
        print(f"[SLASH] /{command.name}")
        print(f"[AGENT] {direct_agent.name}")
        print(f"[MISSION] {command.mission}")
        direct_agent_task = Task(
            description=command.mission,
            type=direct_agent.routing_key,
            explicit_agent=True,
        )
        launch = None

    if launch is not None:
        skill = launch.skill
        agent = skill.agent
        loop._event("skill.loaded", skill=skill.display_name)
        skill_path = skill.path.relative_to(PROJECT_ROOT).as_posix()
        print(f"[SLASH] /{launch.command.name}")
        print(f"[SKILL] {skill.display_name}")
        print(f"[SKILL PATH] {skill_path}")
        print(f"[SKILL SOURCE] {skill_path}/skill.md")
        print(f"[MISSION] {launch.command.mission}")
        runtime = runtime or SkillRuntime(
            orchestrator=orchestrator,
            agent_loop=loop,
            settings={},
            mode="api",
            args=args,
            memory=MemoryManager(loop.tools),
        )
        if runtime.mode_manager is None:
            runtime.mode_manager = ModeManager(
                loop.tools.permissions,
                loop.tools.permissions.mode,
                hard_dry_run=loop.tools.permissions.dry_run,
                on_change=lambda previous, current: loop._event(
                    "mode.changed",
                    previous=previous.value,
                    current=current.value,
                ),
            )
        _afficher_etat_session(runtime)
        if skill.command_handler is not None:
            try:
                skill.command_handler(runtime, launch.command.mission, skill)
            except Exception as error:
                print(f"[SKILL ERROR] /{skill.name} : {type(error).__name__}: {error}")
            finally:
                orchestrator.context.last_skill = skill.name
                orchestrator.context.skill_rag_resources = sorted(skill.rag_contents)
                orchestrator.context.skill_templates = sorted(skill.template_contents)
            return
        orchestrator.context.last_skill = skill.name
        orchestrator.context.skill_rag_resources = sorted(skill.rag_contents)
        orchestrator.context.skill_templates = sorted(skill.template_contents)
        if not launch.command.mission:
            if skill.dispatch_agent or skill.config.get("auto_route"):
                print(f"Décris la mission après /{skill.name}.")
            else:
                print(f"[SKILL ERROR] /{skill.name} ne définit ni agent ni gestionnaire.")
            return
        if agent is not None:
            print(f"[AGENT] {agent.name}")
            task = Task(
                description=launch.command.mission,
                type=agent.routing_key,
                explicit_agent=True,
                skill=skill,
                skill_name=skill.name,
            )
        elif skill.dispatch_agent or skill.config.get("auto_route"):
            runtime.run_task(
                launch.command.mission,
                agent_key=skill.dispatch_agent,
                instructions=str(skill.config.get("task_instructions", "")),
                allowed_tools=skill.tools,
                automatic=bool(skill.config.get("auto_route")),
                skill=skill,
            )
            return
        else:
            print(f"[SKILL ERROR] /{skill.name} ne définit ni agent ni gestionnaire.")
            return
    else:
        if direct_agent_task is not None:
            task = direct_agent_task
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
    if runtime is not None and runtime.mode_manager is not None:
        task.mode = runtime.mode_manager.current.value
        if launch is None:
            _afficher_etat_session(runtime)
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
    if getattr(args, "replay", None):
        from core.replay import replay_mission
        workspace = Path(args.workspace) if args.workspace else PROJECT_ROOT / "workspace"
        replay_mission(args.replay, log_dir=workspace / ".harness")
        return
    if getattr(args, "ui", False):
        from ui.server import run_ui_server

        run_ui_server(port=getattr(args, "port", 8765))
        return
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
