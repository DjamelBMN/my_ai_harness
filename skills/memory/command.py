# RÔLE DE CE FICHIER : gère la mémoire temporaire et les notes projet explicitement confirmées.
def handle(runtime,mission,skill):
    memory=runtime.memory
    if memory is None: print("[MEMORY] Gestionnaire indisponible."); return
    parts=mission.strip().split(maxsplit=2); command=parts[0].casefold() if parts else "status"
    if command in {"status","show"}:
        print(f"Mémoire de mission : {runtime.orchestrator.context.mission_memory or 'aucune'}")
        print(f"Notes de session : {memory.session}")
        print(f"Décisions : {memory.decisions}")
        print(f"Préférences : {memory.preferences}")
        print(f"Mémoire projet ({memory.PROJECT_PATH}) : {memory.project}")
        return
    if command=="clear" and len(parts)>1 and parts[1].casefold()=="session":
        memory.clear_session(); print("Mémoire session effacée; notes projet conservées."); return
    if command!="remember" or len(parts)<3:
        print("Utilisation : /memory status | remember session|project|decision <note> | remember preference clé=valeur | clear session"); return
    try: print(memory.remember(parts[1].casefold(),parts[2]))
    except (ValueError,PermissionError) as error: print(f"[MEMORY ERROR] {error}")
