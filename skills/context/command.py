# RÔLE DE CE FICHIER : compte les données de contexte sans en révéler le contenu.
def handle(runtime,mission,skill):
    context=runtime.orchestrator.context; manager=runtime.orchestrator.context_manager
    print("CONTEXTE DE SESSION")
    print(f"Historique : {len(context.history)} entrée(s), {sum(len(x) for x in context.history)} caractères")
    print(f"Fichiers suivis : {len(context.files)}")
    print(f"Dernier résultat : {len(context.last_result)} caractères")
    print(f"Limite compaction : {manager.max_items} éléments / {manager.max_characters} caractères")
    print(f"Dernier Skill chargé : {context.last_skill or 'aucun'}")
    print(f"Ressources RAG chargées : {context.skill_rag_resources or 'aucune'}")
    print(f"Templates chargés : {context.skill_templates or 'aucun'}")
    if context.mission_memory:
        data=context.mission_memory
        print(f"Dernière mission : {data.get('intent')} / {data.get('status')}; {len(data.get('agents',[]))} agent(s), {len(data.get('files',[]))} fichier(s), {len(data.get('errors',[]))} erreur(s)")
    else: print("Aucune mémoire de mission disponible.")
    memory=runtime.memory
    if memory: print(f"Mémoire session : {len(memory.session)} note(s), {len(memory.decisions)} décision(s), {len(memory.preferences)} préférence(s), {len(memory.project)} note(s) projet.")
