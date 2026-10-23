# RÔLE DE CE FICHIER :
# Prépare le contrat Claude sans générer de réponse simulée ni appeler une API.

from providers.base_provider import BaseProvider


class ClaudeProvider(BaseProvider):
    def generate(self, prompt: str = "") -> str:
        raise RuntimeError(
            "ClaudeProvider n'est pas encore connecté à l'API Claude."
        )

    def execute(self, instruction: str = "") -> str:
        return "ClaudeProvider ne peut pas exécuter de commandes."

    def get_name(self) -> str:
        return "ClaudeProvider"

    def get_model_name(self) -> str:
        return "Claude"
