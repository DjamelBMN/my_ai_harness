# RÔLE DE CE FICHIER :
# Définit l'agent BacBlanc attaché aux instructions et ressources chargées par le
# Skill. SkillLoader lui fournit les règles; le runtime lui attribue le provider.

from core.agent import Agent
from core.task import Task


class BacBlancAgent(Agent):
    description = "Conçoit des sujets de bac blanc, corrigés et barèmes."
    capabilities = (
        "exam_creation",
        "bac_blanc",
        "mathematics",
        "grading",
        "correction",
        "latex",
        "pdf",
        "document_generation",
    )
    supported_intents = ("exam_creation", "writing", "file_analysis")

    def __init__(self) -> None:
        super().__init__(
            name="BacBlancAgent",
            role="conception de sujets et corrigés d'examen",
            routing_key="bacblanc",
        )
        self.skill_instructions = ""
        self.skill_rules = ""
        self.skill_rag_resources = []
        self.skill_templates = []

    def build_prompt(self, task: Task) -> str:
        parts = [super().build_prompt(task)]
        if getattr(self, "skill_source_path", ""):
            parts.append(f"MANIFESTE DU SKILL CHARGÉ : {self.skill_source_path}")
        if self.skill_instructions:
            parts.append("INSTRUCTIONS DU SKILL:\n" + self.skill_instructions)
        if self.skill_rules:
            parts.append("RÈGLES DU SKILL:\n" + self.skill_rules)
        resource_names = [str(path) for path in self.skill_rag_resources]
        available_templates = [str(path) for path in self.skill_available_templates]
        parts.append(
            "RAG DU SKILL:\n"
            + ("Ressources disponibles: " + ", ".join(resource_names) if resource_names else "Aucune ressource RAG locale chargée.")
        )
        parts.append(
            "TEMPLATES DÉCLARÉS:\n"
            + (", ".join(self.skill_templates) if self.skill_templates else "Aucun template déclaré.")
            + "\nFICHIERS TEMPLATE RÉELLEMENT PRÉSENTS:\n"
            + (
                ", ".join(available_templates)
                if available_templates
                else "Aucun fichier template présent. Ne prétends pas en avoir utilisé un."
            )
        )
        parts.append(
            "Tu es l'agent de raisonnement du Skill BacBlanc. Applique les instructions "
            "chargées, utilise les outils autorisés et délègue les vérifications nécessaires "
            "aux agents génériques disponibles. Ne prétends pas avoir lu de ressource, utilisé "
            "un template ou vérifié un résultat sans preuve observable."
        )
        return "\n\n".join(parts)
