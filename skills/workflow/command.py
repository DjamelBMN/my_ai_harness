# RÔLE DE CE FICHIER : réutilise Planner, AgentLoop, tools et délégation déjà actifs.
def handle(runtime, mission, skill):
    instructions = "\n\n".join(
        part for part in (skill.instructions, skill.config.get("task_instructions", "")) if part
    )
    return runtime.run_task(
        mission,
        instructions=instructions,
        allowed_tools=skill.tools,
        automatic=True,
        skill=skill,
    )
