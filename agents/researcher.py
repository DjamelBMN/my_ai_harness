# RÔLE DE CE FICHIER :
# Définit ResearchAgent, notre agent spécialisé en recherche et analyse. Il prépare
# son prompt puis utilise le provider LLM attribué par l'Orchestrator via le Router.

from datetime import date

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
            "Consigne : explique le sujet clairement et structure les idées.\n"
            f"Date du jour : {date.today().isoformat()}.\n"
            "Méthode :\n"
            "- Réponds dans la langue de l'utilisateur.\n"
            "- Commence directement par la réponse ou la synthèse (2 à 3 phrases), puis détaille. "
            "Pas de préambule, ne te présente pas, ne décris pas tes outils ni ta démarche.\n"
            "- Pour toute information récente ou changeante (actualité, prix, versions, "
            "personnes en poste, lois), utilise web_search avant de répondre.\n"
            "- Pour un fichier ou un document du workspace, lis-le réellement "
            "(read_file ou read_document) avant d'en parler.\n"
            "- Distingue ce qu'une source établit, ce que tu en déduis, et ce qui reste inconnu.\n"
            "- Cite uniquement les sources réellement remontées par les outils. "
            "N'invente jamais une URL, une date, un chiffre ou une citation.\n"
            "- Si les sources divergent ou sont insuffisantes, dis-le franchement "
            "au lieu de combler les trous.\n"
            "- Si la question est ambiguë et que deux lectures mènent à des réponses "
            "très différentes, choisis la plus probable, indique ton hypothèse en une phrase, "
            "puis réponds.\n"
            "- Format : paragraphes courts, titres ## seulement si la réponse est longue, "
            "listes pour les énumérations. Pas de tableaux Markdown, pas de HTML."
        )