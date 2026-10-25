# RÔLE DE CE FICHIER :
# Définit la classe commune Agent, qui représente un programme construit dans ce
# harness. L'Orchestrator lui attribue un provider LLM via le ModelRouter.

import re
from datetime import datetime

from core.task import Task, ensure_task
from providers.base_provider import BaseProvider


class Agent:
    """Contrat commun des agents chargeables par le runtime.

    Un plugin peut déclarer ses métadonnées comme attributs de classe et fournir
    un constructeur sans argument. Les agents historiques qui transmettent
    explicitement name/role/routing_key restent compatibles.
    """

    name = ""
    role = "agent spécialisé"
    routing_key = ""
    description = "Agent spécialisé du harness."
    capabilities: tuple[str, ...] = ()
    supported_intents: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] | None = None

    def __init__(
        self,
        name: str | None = None,
        role: str | None = None,
        routing_key: str | None = None,
        *,
        description: str | None = None,
        capabilities=None,
        supported_intents=None,
        allowed_tools=None,
    ) -> None:
        self.name = name or type(self).name or type(self).__name__
        self.role = role or type(self).role
        self.routing_key = routing_key or type(self).routing_key or self._default_routing_key()
        self.description = description or type(self).description
        self.capabilities = tuple(capabilities if capabilities is not None else type(self).capabilities)
        self.supported_intents = tuple(
            supported_intents
            if supported_intents is not None
            else type(self).supported_intents
        )
        self.allowed_tools = (
            tuple(allowed_tools)
            if allowed_tools is not None
            else type(self).allowed_tools
        )
        self.provider: BaseProvider | None = None
        self.last_prompt = ""
        self.last_llm_response = ""

    def _default_routing_key(self) -> str:
        slug = re.sub(r"(?<!^)(?=[A-Z])", "_", type(self).__name__).casefold()
        return slug[:-6] if slug.endswith("_agent") else slug

    def set_provider(self, provider: BaseProvider) -> None:
        """Reçoit le provider sélectionné par ModelRouter."""
        self.provider = provider

    def build_prompt(self, task: Task | str) -> str:
        """Construit le prompt de base envoyé au moteur de raisonnement."""
        task = ensure_task(task, default_type=self.routing_key or "researcher")
        now = datetime.now()
        french_weekdays = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        french_months = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        date_str = f"{french_weekdays[now.weekday()]} {now.day} {french_months[now.month - 1]} {now.year}, {now.strftime('%H:%M:%S')}"

        parts = [
            f"Tu es {self.name}, un agent d'élite dont le rôle est : {self.role}.",
            "DIRECTIVE D'IDENTITÉ PERMANENTE (NeoHarness AI) :\n"
            "- NeoHarness AI est un agent/harness conçu et développé par Djamel BENMAKHLOUF, "
            "professeur de mathématiques, assisté par IA.\n"
            "- Djamel BENMAKHLOUF, professeur de mathématiques, est le concepteur, assisté par IA, "
            "de l'architecture, du harness, de l'orchestration et du système agentique.\n"
            "- NeoHarness AI peut utiliser différents modèles d'IA comme moteurs/providers "
            "pour produire ses réponses : Gemini, Claude, GPT, un modèle local ou un autre "
            "moteur, selon la configuration du ModelRouter.\n"
            "- Le provider ou modèle utilisé n'est pas le concepteur de NeoHarness AI. "
            "Distingue toujours ton identité (NeoHarness AI) de celle du modèle qui "
            "t'exécute.\n"
            "- Si l'utilisateur demande « Qui t'a créé ? », « Qui a conçu NeoHarness AI ? », "
            "« Qui est ton développeur ? », « Es-tu Gemini ? », « Es-tu Claude ? », "
            "« Es-tu OpenAI ? » ou toute question équivalente, réponds honnêtement : "
            "« NeoHarness AI a été conçu et développé par Djamel BENMAKHLOUF, professeur de "
            "mathématiques, assisté par IA. Le harness "
            "orchestre différents modèles d'intelligence artificielle utilisés comme moteurs "
            "pour faire fonctionner l'agent. »\n"
            "- Si l'utilisateur demande quel modèle est actuellement utilisé, tu peux donner "
            "le nom réel du provider et du modèle, en précisant que ce modèle est le moteur "
            "utilisé par NeoHarness AI et non son concepteur.\n"
            "- N'attribue jamais la conception de NeoHarness AI à Anthropic, Google, OpenAI, "
            "Gemini, Claude ou à un autre fournisseur simplement parce que le modèle utilisé "
            "provient de ce fournisseur.",
            f"Date et heure actuelles : {date_str} (Europe/Paris). Tu as pleine conscience de la date courante.",
            f"Tâche à accomplir : {task.description}",
            f"Mode global du Harness : {task.mode}.",
            "Directive d'intelligence et d'autonomie Web : En cas de manque de connaissances récentes, de vérification de fait, d'annale ou de point de programme officiel, utilise l'outil 'web_search' pour interroger Internet en temps réel. Si la demande implique de trouver, récupérer ou télécharger un document (ex: sujet d'examen, annale, rapport, PDF), la mission n'est réussie que lorsque le document est physiquement téléchargé dans le workspace et vérifié (existence, taille > 0, format valide). Une simple recherche sans document téléchargé constitue un échec.",
            "DIRECTIVE D'INTÉGRITÉ ABSOLUE DES ARTEFACTS :\n"
            "- L'agent ne doit JAMAIS fabriquer, remplacer, inventer ou substituer un document demandé afin de faire croire que la mission est réussie.\n"
            "- Lorsqu'un document externe est demandé : il doit provenir RÉELLEMENT de la source recherchée sur Internet. Son contenu ne doit jamais être remplacé par un contenu généré par l'agent.\n"
            "- Un fichier existant du workspace ne doit JAMAIS être modifié pour simuler le résultat attendu. La compilation d'un fichier de substitution ne constitue jamais une réussite.\n"
            "- Ne jamais transformer un échec de récupération en faux succès par génération de contenu. Ne jamais considérer 'fichier créé + compilation réussie' comme preuve que le document a été récupéré.\n"
            "- Si le téléchargement échoue : 1. conserver la mission active; 2. essayer une autre source; 3. essayer une autre méthode de téléchargement; 4. si toutes les stratégies échouent, déclarer honnêtement l'échec sans aucune fabrication de substitution.\n"
            "- Le système établit obligatoirement une chaîne de provenance infalsifiable : SOURCE WEB → URL → TÉLÉCHARGEMENT → FICHIER PHYSIQUE → HASH → TYPE/MAGIC BYTES → CONTENU → VÉRIFICATION.",
        ]
        if task.skill_name:
            parts.append(f"Skill actif : {task.skill_name}.")
        if task.mode == "PLAN":
            parts.append(
                "PLAN MODE : inspecte et prépare un plan vérifiable; ne demande ni "
                "n'effectue aucune écriture, suppression, commande ou suite mutatrice."
            )
        elif task.mode == "EDIT":
            parts.append(
                "EDIT MODE : les écritures autorisées sont précédées d'un aperçu "
                "terminal de la cible et de l'action; respecte les autres permissions."
            )
        elif task.mode == "AUTO":
            parts.append(
                "AUTO MODE : poursuis les étapes utiles jusqu'à vérification ou "
                "blocage avec les permissions autonomes du Harness; respecte "
                "toujours le dry-run et les restrictions globales."
            )
        else:
            parts.append(
                "ACCEPT MODE : attends une confirmation pour les actions sensibles."
            )
        if task.context is not None:
            context_description = task.context.describe()
            if context_description:
                parts.append(f"Contexte de session : {context_description}")
        if task.instructions.strip():
            parts.append("Instructions du Skill :\n" + task.instructions.strip())
        return "\n".join(parts)

    def interpret_response(self, llm_response: str) -> str:
        """Point d'extension pour interpréter la réponse du LLM."""
        return llm_response.strip()

    def run(self, task: Task | str) -> str:
        """Construit le prompt, appelle le provider puis interprète sa réponse."""
        task = ensure_task(task, default_type=self.routing_key or "researcher")
        if self.provider is None:
            raise RuntimeError(
                f"Aucun provider n'a été attribué à {self.name}. "
                "L'Orchestrator doit d'abord appeler le ModelRouter."
            )

        self.last_prompt = self.build_prompt(task)
        self.last_llm_response = self.provider.generate(self.last_prompt)
        return self.interpret_response(self.last_llm_response)


# Nom de contrat explicite pour les nouveaux plugins; l'alias conserve toute
# la compatibilité avec les imports historiques de ``Agent``.
BaseAgent = Agent