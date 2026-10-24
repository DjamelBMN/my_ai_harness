# RÔLE DE CE FICHIER : délègue la sélection et l'exécution au runtime existant.
def handle(runtime, mission, skill):
    return runtime.run_task(
        mission,
        instructions=skill.instructions,
        allowed_tools=skill.tools,
        automatic=True,
        skill=skill,
    )
