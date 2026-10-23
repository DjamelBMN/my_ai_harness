# RÔLE DE CE FICHIER :
# Prépare l'interface d'un futur modèle exécuté localement. Il n'installe aucun
# modèle et ne fait aucun appel réseau ; il pourra être sélectionné par le Router.

from providers.base_provider import BaseProvider


class LocalProvider(BaseProvider):
    """Squelette commun pour un futur LLM local, encore non configuré."""

    def generate(self, prompt: str = "") -> str:
        raise RuntimeError(
            "LocalProvider n'est pas connecté à un LLM local. "
            "Aucune génération n'a été effectuée."
        )

    def execute(self, instruction: str = "") -> str:
        return "LocalProvider ne peut pas exécuter d'instructions dans ce prototype."

    def get_name(self) -> str:
        return "LocalProvider"

    def get_model_name(self) -> str:
        return "LLM local (non configuré)"
