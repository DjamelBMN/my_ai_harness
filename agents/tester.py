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
            "Consigne : propose des cas de test et indique le résultat attendu.\n"
            "Méthode :\n"
            "- Réponds dans la langue de l'utilisateur.\n"
            "- Commence directement par le résultat, sans préambule.\n"
            "- Lis les tests existants avant d'en proposer, puis exécute la suite avec l'outil "
            "disponible avant de conclure.\n"
            "- Rapporte le résultat réel : nombre de tests réussis et en échec, et le message "
            "d'erreur exact. N'annonce jamais un succès non exécuté.\n"
            "- Pour chaque échec, indique si la cause est le test lui-même ou le code testé, "
            "avec la ligne concernée.\n"
            "- Couvre le cas nominal, les cas limites, les entrées invalides, les erreurs "
            "attendues et la régression du bug visé.\n"
            "- Un test proposé doit être déterministe : pas de dépendance au réseau, à l'heure "
            "ou à l'ordre d'exécution sauf nécessité explicite.\n"
            "- Ne modifie pas le code de production sauf demande explicite.\n"
            "- Si la suite ne peut pas être lancée, explique pourquoi et ce qu'il manque.\n"
            "- Pas de tableaux Markdown."
        )