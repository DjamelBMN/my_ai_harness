# RÔLE DE CE FICHIER : affiche puis exécute l'agent/provider choisis par le runtime.
def handle(runtime, mission, skill):
    return runtime.run_task(
        mission,
        instructions=skill.instructions,
        allowed_tools=skill.tools,
        automatic=True,
        skill=skill,
    )
