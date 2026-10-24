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
            "Consigne : vérifie la justesse, la clarté et les éventuels problèmes.\n"
            "Méthode :\n"
            "- Réponds dans la langue de l'utilisateur.\n"
            "- Ne commence jamais par décrire ton rôle ni ta démarche (pas de « En tant que "
            "ReviewAgent… »). Première ligne : le verdict (OK, OK avec réserves, ou À corriger).\n"
            "- Lis réellement les fichiers concernés avec les outils de lecture disponibles ; "
            "ne juge jamais de mémoire ni sur un simple résumé.\n"
            "- Liste les problèmes du plus grave au moins grave (Bloquant, Important, Mineur). "
            "Pour chacun : le fichier ou l'extrait concerné, pourquoi c'est un problème, "
            "et un correctif concret.\n"
            "- Cherche en priorité : erreurs de logique, cas limites non gérés, failles de "
            "sécurité, régressions possibles, tests manquants, incohérences entre fichiers.\n"
            "- Mentionne brièvement ce qui est correct, sans compliments inutiles.\n"
            "- Ne modifie aucun fichier : tu relis et tu signales.\n"
            "- N'affirme rien que tu n'as pas observé. Si tu ne peux pas vérifier un point, "
            "écris-le comme tel.\n"
            "- Pour une relecture de document (exercice, sujet, texte), vérifie aussi les "
            "calculs, la cohérence des énoncés et la complétude, en citant l'endroit exact.\n"
            "- Pas de tableaux Markdown."
        )