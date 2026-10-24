# RÔLE DE CE FICHIER : affiche le plan heuristique sans LLM, tool ou modification.
from core.task import Task
def handle(runtime,mission,skill):
    if not mission.strip(): print("Utilisation : /plan <mission>"); return
    planner=runtime.agent_loop.planner
    planner.set_agent_registry(runtime.orchestrator.agent_registry)
    task=Task(mission.strip()); state=planner.plan(task)
    selection=runtime.orchestrator.agent_selector.select(task,state); decision=state.intent_decision
    print("[PLAN — PRÉVISUALISATION, AUCUNE ACTION EXÉCUTÉE]")
    print(f"Objectif : {state.objective}")
    print(f"Intention : {state.intent}")
    print(f"Agent disponible : {selection.agent.name} (score {selection.score})")
    files=decision.get("files_required",[])
    print("Fichiers : "+(", ".join(files) if files else "à identifier ou non précisés"))
    print("Agents secondaires : "+(", ".join(decision.get("secondary_capabilities",[])) or "aucun détecté"))
    print("Skills : "+("/bacblanc disponible" if state.intent=="exam_creation" else "aucun Skill spécialisé détecté"))
    print("Outils : "+(", ".join(decision.get("required_tools",[])) or "aucun tool initialement requis"))
    print("Étapes :")
    for i,step in enumerate(state.plan,1): print(f"  {i}. {step.description}")
    print("Vérifications : "+("; ".join(decision.get("success_criteria",[])) or "vérifier les résultats observables"))
