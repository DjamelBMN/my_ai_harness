# RÔLE DE CE FICHIER :
# Définit ResearchAgent, notre agent spécialisé en recherche et analyse. Il prépare
# son prompt puis utilise le provider LLM attribué par l'Orchestrator via le Router.

from core.agent import Agent
from core.task import Task


class ResearchAgent(Agent):
    description = "Analyse des sujets, fichiers et sources accessibles au runtime."
    capabilities = ("research", "source_analysis", "file_analysis", "synthesis")
    supported_intents = ("research", "file_analysis", "general_question")

    def __init__(self) -> None:
        super().__init__(
            name="ResearchAgent",
            role="recherche et analyse",
            routing_key="researcher",
        )

    def build_prompt(self, task: Task) -> str:
        base_prompt = super().build_prompt(task)
        return (
            f"{base_prompt}\n"
            "Consigne : explique le sujet clairement et structure les idées."
        )
