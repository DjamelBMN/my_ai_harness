# RÔLE DE CE FICHIER :
# Définit TestAgent, notre agent spécialisé dans les tests. Il prépare une consigne
# de vérification et reçoit un provider LLM attribué par l'Orchestrator et le Router.

from core.agent import Agent
from core.task import Task


class TestAgent(Agent):
    description = "Exécute et analyse les tests réellement présents dans le workspace."
    capabilities = ("testing", "unit_test", "integration_test", "regression", "verification")
    supported_intents = ("testing", "verification")

    def __init__(self) -> None:
        super().__init__(
            name="TestAgent",
            role="tests et vérification",
            routing_key="tester",
        )

    def build_prompt(self, task: Task) -> str:
        base_prompt = super().build_prompt(task)
        return (
            f"{base_prompt}\n"
            "Consigne : propose des cas de test et indique le résultat attendu."
        )
