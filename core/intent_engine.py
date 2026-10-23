# RÔLE DE CE FICHIER :
# Traduit une demande utilisateur en décision de mission structurée : objectif,
# intention, capacités, workspace, outils, risques et critères de réussite.
# Planner l'utilise; la sélection finale d'agent appartient à AgentSelector.

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent_registry import AgentRegistry


@dataclass
class IntentDecision:
    intent: str
    confidence: float
    objective: str
    primary_agent: str | None = None
    secondary_agents: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    secondary_capabilities: list[str] = field(default_factory=list)
    allowed_secondary_agents: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    files_required: list[str] = field(default_factory=list)
    requires_workspace: bool = False
    requires_file_read: bool = False
    requires_modification: bool = False
    requires_tests: bool = False
    requires_web: bool = False
    requires_verification: bool = True
    risk_level: str = "READ_ONLY"
    requires_user_confirmation: bool = False
    success_criteria: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class IntentEngine:
    """Classification linguistique par objectifs et verbes d'action.

    Les règles sont des profils composables plutôt qu'un routage vers des noms
    d'agents. Les capacités des agents restent déclarées dans leur plugin.
    """

    FILE_SUFFIX = r"(?:pdf|docx|xlsx|pptx|txt|md|json|ya?ml|csv|html|css|js|ts|py)"
    CHANGE_VERBS = re.compile(
        r"\b(écris|ecris|crée|cree|create|développe|developpe|implémente|implement|"
        r"modifie|corrige|refactorise|refactorise|ajoute|supprime|répare|repare|"
        r"construis|build|write|implement|fix|refactor)\b",
        re.I,
    )
    TEST_ACTION = re.compile(
        r"\b(lance|exécute|execute|écris|ecris|crée|cree|run|write|ajoute|add)\b.{0,35}\btests?\b|"
        r"\btests?\b.{0,40}\b(unitaires?|de régression|de regression|cette fonctionnalité|cette modification)\b",
        re.I,
    )

    def __init__(self, agent_registry: "AgentRegistry | None" = None) -> None:
        self.agent_registry = agent_registry

    def decide(self, request: str) -> IntentDecision:
        text = " ".join(request.casefold().strip().split())
        if not text:
            raise ValueError("La demande est vide.")

        files = self._files(text)
        has_file = bool(files) or any(
            phrase in text
            for phrase in ("fichier", "document", "pdf", "mon projet", "codebase")
        )
        asks_creation = bool(
            re.search(r"\b(crée|cree|prépare|prepare|génère|genere|conçois|concois)\b", text)
        )
        asks_exam = any(
            marker in text
            for marker in (
                "bac blanc", "brevet blanc", "examen blanc", "sujet d'examen",
                "sujet de bac", "sujet de brevet", "devoir surveillé", "devoir surveille",
            )
        ) or (
            asks_creation
            and any(word in text for word in ("barème", "bareme", "corrigé", "corrige", "sujet"))
            and any(word in text for word in ("terminale", "première", "premiere", "math", "examen"))
        )
        asks_official = any(
            marker in text
            for marker in ("officiel", "programme", "source fiable", "sources", "sur internet", "sur le web")
        ) and any(marker in text for marker in ("cherche", "recherche", "vérifie", "verifie", "respecte", "conforme"))
        asks_web = any(
            marker in text
            for marker in (
                "sur internet", "sur le web", "en ligne", "sources officielles", "source officielle",
                "recherche web", "vérifie cette information", "verifie cette information",
                "dernières informations", "derniere information", "programmes officiels",
            )
        ) or asks_official

        asks_debug_and_fix = any(
            marker in text for marker in ("corrige", "répare", "repare", "fix", "résous", "resous")
        ) and any(marker in text for marker in ("bug", "plante", "erreur", "crash", "ne fonctionne"))
        code_action = bool(re.search(
            r"\bcode(?:z)?\s+(?:(?:un|une|le|la|des)\s+)?(?:programme|program|application|app|script|fonction|module|outil|agent)",
            text,
        ))
        asks_code_modification = (bool(self.CHANGE_VERBS.search(text)) or code_action) and (
            has_file
            or asks_debug_and_fix
            or any(
                marker in text
                for marker in (
                    "programme", "application", "app", "script", "fonction", "module", "code",
                    "program", "projet", "application python", "agent", "fonctionnalité", "fonctionnalite",
                )
            )
        )
        asks_test = bool(self.TEST_ACTION.search(text)) or any(
            marker in text
            for marker in ("lance les tests", "exécute les tests", "execute les tests", "run tests")
        )
        asks_regression_check = any(
            marker in text for marker in ("ne casse rien", "pas de régression", "pas de regression", "régressions", "regressions")
        )
        asks_review = any(
            marker in text
            for marker in (
                "revue complète", "revue complete", "revue de code", "vérifie mon code",
                "verifie mon code", "revue de cette architecture", "recherche les bugs",
                "cherche les bugs", "audit mon code", "audit de code",
            )
        )
        asks_file_analysis = has_file and any(
            marker in text
            for marker in (
                "analyse", "résume", "resume", "lis ", "lire ", "compare", "extrais", "extrait", "explique le contenu",
            )
        )
        asks_research = asks_web or any(
            marker in text
            for marker in ("cherche", "recherche", "trouve les sources", "trouve les informations", "vérifie cette information", "verifie cette information")
        )

        # Les demandes métier et les objectifs de modification priment sur les
        # mots secondaires. Une création de sujet n'est pas une recherche seule.
        if asks_exam:
            decision = self._decision(
                "exam_creation", request, 0.93,
                capabilities=["exam_creation"],
                workspace=has_file,
                file_read=has_file,
                web=asks_official or asks_web,
                secondary=( ["research", "review"] if asks_official else [] ),
                tools=(["web_search"] if asks_official else []),
                criteria=["sujet conforme aux contraintes", "corrigé et barème cohérents"],
                rationale=["objectif de création d'un sujet d'examen détecté"],
            )
            if asks_official:
                decision.rationale.append("vérification d'une exigence officielle demandée")
            return decision

        if asks_code_modification:
            secondaries = []
            if asks_research and asks_debug_and_fix:
                secondaries.append("research")
            if asks_test or asks_regression_check or asks_debug_and_fix:
                secondaries.append("testing")
            if "testing" not in secondaries:
                secondaries.append("testing")
            return self._decision(
                "coding", request, 0.94,
                capabilities=["coding"],
                secondary=secondaries,
                tools=["list_files", "find_file", "search_files", "read_file", "read_document", "write_file", "patch_file", "run_python", "run_tests"],
                workspace=True,
                file_read=True,
                modification=True,
                tests=True,
                risk="MODERATE",
                confirmation=True,
                criteria=["modification effectuée dans le workspace", "tests pertinents exécutés", "résultat vérifié"],
                rationale=["verbe d'implémentation ou de modification appliqué au code/projet"],
            )

        if asks_review and not asks_test:
            return self._decision(
                "review", request, 0.89,
                capabilities=["review"],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document", "run_tests"] if has_file else [],
                workspace=has_file,
                file_read=has_file,
                criteria=["observations justifiées par des éléments examinés", "problèmes et limites signalés"],
                rationale=["demande d'audit ou de revue critique détectée"],
            )

        if asks_test or asks_regression_check:
            return self._decision(
                "testing", request, 0.91,
                capabilities=["testing"],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document", "run_tests", "run_python"],
                workspace=True,
                file_read=has_file,
                tests=True,
                criteria=["suite de tests réellement exécutée", "résultats observés"],
                rationale=["demande d'exécution ou de validation de tests détectée"],
            )

        if asks_file_analysis:
            return self._decision(
                "file_analysis", request, 0.92,
                capabilities=["file_analysis"],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document"],
                workspace=True,
                file_read=True,
                criteria=["fichier réellement lu", "synthèse fondée sur le contenu extrait"],
                rationale=["action d'analyse appliquée à un fichier/document identifié"],
            )

        if asks_research:
            return self._decision(
                "research", request, 0.90,
                capabilities=["research"],
                tools=["web_search"] if asks_web else [],
                web=asks_web,
                criteria=["faits séparés des inférences", "sources citées uniquement si consultées"],
                rationale=["demande de recherche, de vérification ou de sources détectée"],
            )

        if files:
            return self._decision(
                "file_analysis", request, 0.72,
                capabilities=["file_analysis"],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document"],
                workspace=True,
                file_read=True,
                criteria=["contenu consulté avant toute conclusion"],
                rationale=["référence à un document local détectée"],
            )

        if text in {"python", "code", "coding", "programme", "programming"}:
            raise ValueError("Demande ambiguë : précise ce que tu veux faire avec ce sujet.")

        plugin_action = bool(self.CHANGE_VERBS.search(text)) or bool(
            re.search(r"\b(use|perform|execute|run|create|apply|employ)\b", text)
        )
        if self.agent_registry is not None and plugin_action:
            normalized = re.sub(r"[^a-z0-9 ]+", " ", text)
            normalized = " ".join(normalized.split())
            for key, agent in self.agent_registry.agents.items():
                declared = [
                    ("capability", item) for item in agent.capabilities
                ] + [("intent", item) for item in agent.supported_intents]
                for kind, declaration in declared:
                    phrase = re.sub(r"[_-]+", " ", declaration.casefold())
                    phrase = " ".join(phrase.split())
                    if len(phrase) > 2 and phrase in normalized:
                        intent = (
                            declaration
                            if kind == "intent"
                            else next(iter(agent.supported_intents), declaration)
                        )
                        capability = declaration if kind == "capability" else next(iter(agent.capabilities), declaration)
                        return self._decision(
                            intent,
                            request,
                            0.82,
                            capabilities=[capability],
                            workspace=has_file,
                            file_read=has_file,
                            criteria=["mission spécialisée accomplie selon la capacité déclarée"],
                            rationale=[f"capacité déclarée détectée chez {agent.name}: {capability}"],
                        )

        return self._decision(
            "general_question", request, 0.75,
            capabilities=["research"],
            verification=False,
            criteria=["réponse directe", "incertitudes explicites si nécessaire"],
            rationale=["aucune action locale ou recherche explicite n'est requise"],
        )

    @classmethod
    def _decision(
        cls,
        intent: str,
        request: str,
        confidence: float,
        *,
        capabilities: list[str],
        secondary: list[str] | None = None,
        tools: list[str] | None = None,
        workspace: bool = False,
        file_read: bool = False,
        modification: bool = False,
        tests: bool = False,
        web: bool = False,
        verification: bool = True,
        risk: str = "READ_ONLY",
        confirmation: bool = False,
        criteria: list[str] | None = None,
        rationale: list[str] | None = None,
    ) -> IntentDecision:
        return IntentDecision(
            intent=intent,
            confidence=confidence,
            objective=request.strip(),
            required_capabilities=capabilities,
            secondary_capabilities=secondary or [],
            required_tools=tools or [],
            files_required=cls._files(request),
            requires_workspace=workspace,
            requires_file_read=file_read,
            requires_modification=modification,
            requires_tests=tests,
            requires_web=web,
            requires_verification=verification,
            risk_level=risk,
            requires_user_confirmation=confirmation,
            success_criteria=criteria or [],
            rationale=rationale or [],
        )

    @classmethod
    def _files(cls, request: str) -> list[str]:
        pattern = rf"(?<![\w])[^\s\"']+\.{cls.FILE_SUFFIX}(?![\w])"
        return list(dict.fromkeys(match.rstrip(".,;:)") for match in re.findall(pattern, request, re.I)))
