# RÔLE DE CE FICHIER :
# Définit CodeAgent, notre agent spécialisé en programmation. Il construit une
# consigne pour son LLM ; l'Orchestrator lui attribue le provider choisi par le Router.

from core.agent import Agent
from core.task import Task


class CodeAgent(Agent):
    description = "Inspecte, explique, modifie et débogue du code dans le workspace."
    capabilities = ("coding", "debugging", "file_edit", "python", "testing_handoff")
    supported_intents = ("coding", "debugging", "file_analysis")

    def __init__(self) -> None:
        super().__init__(
            name="CodeAgent",
            role="programmation",
            routing_key="coder",
        )

    def build_prompt(self, task: Task) -> str:
        base_prompt = super().build_prompt(task)
        return (
            f"{base_prompt}\n"
            "Consigne : propose une solution de programmation claire et explique "
            "les choix importants."
        )
