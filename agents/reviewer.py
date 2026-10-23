# RÔLE DE CE FICHIER :
# Définit ReviewAgent, notre agent spécialisé dans la revue de code et de réponses.
# Il reçoit le provider LLM choisi pour lui par l'Orchestrator via le Router.

from core.agent import Agent
from core.task import Task


class ReviewAgent(Agent):
    description = "Évalue de façon critique le code, les documents et les réponses."
    capabilities = ("review", "quality_check", "risk_analysis", "verification")
    supported_intents = ("review", "verification")

    def __init__(self) -> None:
        super().__init__(
            name="ReviewAgent",
            role="revue de code et vérification critique",
            routing_key="reviewer",
        )

    def build_prompt(self, task: Task) -> str:
        base_prompt = super().build_prompt(task)
        return (
            f"{base_prompt}\n"
            "Consigne : vérifie la justesse, la clarté et les éventuels problèmes."
        )
