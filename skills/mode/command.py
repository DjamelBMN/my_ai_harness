# RÔLE DE CE FICHIER : interface slash vers le gestionnaire global de modes.

from core.modes import ModeManager


def handle(runtime, mission, skill):
    manager = runtime.mode_manager
    if manager is None:
        print("[MODE ERROR] Gestionnaire global indisponible.")
        return

    requested = mission.strip().casefold()
    if not requested:
        print(ModeManager.help_table())
        print(f"Mode actif : {manager.current.value}")
        print("Raccourci : Shift+Tab")
        return

    if requested in {"status", "show"}:
        print(f"Mode actif : {manager.current.value}")
        print(ModeManager.DESCRIPTIONS[manager.current])
        return

    try:
        previous, selected = manager.set_mode(requested)
    except ValueError as error:
        print(f"[MODE ERROR] {error}")
        print(ModeManager.help_table())
        return

    if previous is selected:
        print(f"[MODE] {selected.value} déjà actif.")
    else:
        print(f"[MODE] {previous.value} → {selected.value}")
    print("╭─────────────────────────────╮")
    print(f"│ MODE : {selected.value:<19}│")
    print(f"│ {ModeManager.SHORT_DESCRIPTIONS[selected]:<27}│")
    print("╰─────────────────────────────╯")
