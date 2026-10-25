# RÔLE DE CE FICHIER :
# Définit ReviewAgent et IndependentCritic, spécialisés dans la revue critique indépendante.
# Le Critic opère sur un CONTEXTE VIERGE : aucun biais ni historique de conversation.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.agent import Agent
from core.task import Task


@dataclass
class CriticVerdict:
    decision: str  # "APPROVE" ou "REJECT"
    defects: list[str] = field(default_factory=list)
    feedback: str = ""
    roundtrip_count: int = 1
    max_roundtrips: int = 2

    @property
    def is_approved(self) -> bool:
        return self.decision.upper() == "APPROVE"


class IndependentCritic:
    """Critic indépendant opérant sur un CONTEXTE TOTALEMENT VIERGE.

    Zéro historique de conversation, zéro rationalisation du Coder.
    Seules les données physiques réelles (tâche, diff, sorties de tests) sont transmises.
    """

    def __init__(self, provider: Any = None) -> None:
        self.provider = provider

    def evaluate(
        self,
        task_description: str,
        code_diff: str,
        test_output: str,
        roundtrip: int = 1,
    ) -> CriticVerdict:
        prompt = (
            "Tu es un Critic indépendant et impartial. Tu évalues ce code avec un regard neuf.\n"
            "Voici les SEULES informations objectives dont tu disposes :\n\n"
            f"<tache>\n{task_description}\n</tache>\n\n"
            f"<code_diff>\n{code_diff}\n</code_diff>\n\n"
            f"<test_output>\n{test_output}\n</test_output>\n\n"
            "Consigne stricte :\n"
            "- Si le code remplit l'objectif sans régression, sans faille et avec tests valides, réponds en première ligne : VERDICT: APPROVE.\n"
            "- Si un bug, un cas limite non géré, une incohérence ou un manque de tests subsiste, réponds en première ligne : VERDICT: REJECT.\n"
            "- Liste ensuite les défauts sous forme de tirets : - [Défaut] explication et correctif."
        )

        raw = ""
        if self.provider is not None:
            try:
                raw = self.provider.generate(prompt)
            except Exception as e:
                raw = f"VERDICT: REJECT\n- Erreur d'évaluation du Critic : {e}"
        else:
            # Oracle déterministe hors provider
            if "FAIL" in test_output or "Error" in test_output:
                raw = "VERDICT: REJECT\n- [Test en échec] Des tests sont signalés en échec dans la sortie."
            elif not code_diff.strip():
                raw = "VERDICT: REJECT\n- [Diff vide] Aucun code n'a été produit ou modifié."
            else:
                raw = "VERDICT: APPROVE\n- Code conforme, propre et tests passants."

        lines = raw.strip().splitlines()
        first_line = lines[0].upper() if lines else ""
        is_approve = "APPROVE" in first_line

        defects = [] if is_approve else [
            line.strip().lstrip("-").strip()
            for line in lines[1:]
            if line.strip().startswith("-")
        ]

        return CriticVerdict(
            decision="APPROVE" if is_approve else "REJECT",
            defects=defects,
            feedback=raw,
            roundtrip_count=roundtrip,
        )


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
        self.critic = IndependentCritic()

    def set_provider(self, provider: Any) -> None:
        super().set_provider(provider)
        self.critic.provider = provider

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
