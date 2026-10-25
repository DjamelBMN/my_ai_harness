# RÔLE DE CE FICHIER :
# Traduit une demande utilisateur en décision de mission structurée : objectif,
# intention, capacités, workspace, outils, risques et critères de réussite.
# Planner l'utilise; la sélection finale d'agent appartient à AgentSelector.

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.agent_registry import AgentRegistry

def _contains_any_word(text: str, keywords: tuple[str, ...] | list[str]) -> bool:
    """Vérifie la présence d'au moins un mot ou locution avec frontière de mot."""
    for kw in keywords:
        pattern = r"(?:\b|_)" + re.escape(kw.strip()) + r"(?:\b|_)"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False



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

    @staticmethod
    def is_web_query(text: str) -> bool:
        normalized = " ".join(text.casefold().strip().split())
        return any(
            marker in normalized
            for marker in (
                "sur internet",
                "sur le web",
                "en ligne",
                "sources officielles",
                "source officielle",
                "recherche web",
                "recherche internet",
                "vérifie cette information",
                "verifie cette information",
                "dernières informations",
                "derniere information",
                "dernières nouvelles",
                "dernieres nouvelles",
                "programmes officiels",
                "actualité",
                "actualite",
                "actualités",
                "actualites",
                "aujourd'hui",
                "aujourd hui",
                "en 2025",
                "en 2026",
                "sources web",
                "liens web",
            )
        )

    def decide(self, request: str, task_context: Any | None = None) -> IntentDecision:
        text = " ".join(request.casefold().strip().split())
        if not text:
            raise ValueError("La demande est vide.")

        # Prise en compte du contexte persistant de la tâche active si fourni
        is_cont = bool(task_context is not None and hasattr(task_context, "is_continuity_request") and task_context.is_continuity_request(request))
        context_files = list(getattr(task_context, "files", [])) if is_cont else []
        last_intent = str(getattr(task_context, "last_intent", "")) if is_cont else ""

        # Détection des demandes directes de correction / déverminage dans la tâche active
        is_fix_demand = any(m in text for m in ("corrige", "répare", "repare", "fix", "résous", "resous", "débogue", "debogue", "bug", "erreur"))
        if is_cont and is_fix_demand:
            return self._decision(
                "coding",
                request,
                0.95,
                capabilities=["coding"],
                secondary=["testing"] if "testing" in last_intent or getattr(task_context, "tests_executed", None) else [],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document", "write_file", "patch_file", "run_python", "run_tests"],
                workspace=True,
                file_read=True,
                modification=True,
                tests=True,
                risk="MODERATE",
                confirmation=False,
                criteria=["erreur corrigée sur les fichiers de la tâche active", "vérification observable"],
                rationale=["continuité de la tâche active : correction demandée sur le travail en cours"],
                files_required=context_files,
            )

        # Détection des demandes d'enchaînement de tests dans la tâche active
        is_test_demand = any(m in text for m in ("test suivant", "tests suivants", "lance les tests", "relance les tests", "rejoue les tests", "teste-le", "teste ça"))
        if is_cont and is_test_demand:
            return self._decision(
                "testing",
                request,
                0.95,
                capabilities=["testing"],
                tools=["list_files", "find_file", "search_files", "read_file", "read_document", "run_tests", "run_python"],
                workspace=True,
                file_read=bool(context_files),
                tests=True,
                criteria=["suite de tests exécutée sur les fichiers de la tâche active"],
                rationale=["continuité de la tâche active : exécution des tests demandée"],
                files_required=context_files,
            )

        # Détection des demandes d'analyse ou de consultation dans la continuité
        is_analysis_continuity = is_cont and _contains_any_word(text, ("analyse-le", "analyse le", "analyse la", "analyse-la", "analyse ce", "analyse", "lis-le", "ouvre-le", "regarde-le", "examine-le", "lit", "lis"))
        if is_analysis_continuity and context_files:
            return self._decision(
                "file_analysis",
                request,
                0.95,
                capabilities=["file_analysis"],
                tools=["read_document", "read_file", "list_files", "find_file"],
                workspace=True,
                file_read=True,
                criteria=["document du workspace réellement lu et analysé", "synthèse fondée sur le contenu extrait"],
                rationale=["continuité de la tâche active : analyse du document récupéré"],
                files_required=context_files,
            )

        # Détection des demandes d'enchaînement générique (ensuite, continue, améliore-le, etc.)
        is_next_step_demand = any(m in text for m in ("ensuite", "continue", "poursuis", "avance", "fais la suite", "la suite", "améliore-le", "ameliore-le", "optimise", "peaufine", "ça marche", "ca marche", "c'est bon"))
        if is_cont and is_next_step_demand:
            target_intent = last_intent if last_intent in {"coding", "testing", "exam_creation", "file_analysis", "review"} else ("coding" if context_files else "general_question")
            if target_intent == "coding":
                return self._decision(
                    "coding",
                    request,
                    0.94,
                    capabilities=["coding"],
                    secondary=["testing"],
                    tools=["list_files", "find_file", "search_files", "read_file", "read_document", "write_file", "patch_file", "run_python", "run_tests"],
                    workspace=True,
                    file_read=True,
                    modification=True,
                    tests=True,
                    risk="MODERATE",
                    criteria=["étape suivante de la tâche active réalisée"],
                    rationale=["continuité de la tâche active : étape suivante de codage"],
                    files_required=context_files,
                )
            elif target_intent == "exam_creation":
                return self._decision(
                    "exam_creation",
                    request,
                    0.93,
                    capabilities=["exam_creation"],
                    workspace=True,
                    file_read=True,
                    criteria=["suite du sujet réalisée"],
                    rationale=["continuité de la tâche active : suite de création du sujet"],
                    files_required=context_files,
                )

        files = self._files(text)
        if is_cont and context_files:
            for cf in context_files:
                if cf not in files:
                    files.append(cf)

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
        asks_web = self.is_web_query(text) or asks_official

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
                    "html", "page web", "page html", "interface", "interface web", "site web", "css", "javascript",
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
        asks_download = any(
            marker in text
            for marker in (
                "télécharge", "telecharge", "télécharger", "telecharger",
                "télécharge-le", "télécharge le", "récupère", "recupere",
                "téléchargement", "télécharge ce", "download",
            )
        ) or (
            (asks_web or any(m in text for m in ("sur internet", "sur le web", "en ligne")))
            and any(m in text for m in ("trouve", "cherche", "obtient", "prends", "télécharge", "telecharge"))
            and any(m in text for m in ("pdf", "fichier", "document", "sujet", "annale"))
        )

        asks_file_analysis = has_file and not asks_download and not any(m in text for m in ("sur internet", "sur le web", "en ligne")) and _contains_any_word(text, ("analyse", "résume", "resume", "lis", "lit", "lire", "compare", "extrais", "extrait", "explique le contenu"))
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

        if asks_download or (asks_research and asks_download):
            return self._decision(
                "research", request, 0.95,
                capabilities=["research", "coding"],
                tools=["web_search", "read_document", "read_file", "write_file", "list_files"],
                web=True,
                workspace=True,
                file_read=True,
                modification=True,
                criteria=[
                    "document identifié sur des sources fiables",
                    "document réellement téléchargé dans le workspace",
                    "fichier vérifié physiquement (existence, taille non nulle, format valide)",
                ],
                rationale=["demande de recherche et téléchargement effectif d'un document distant dans le workspace"],
            )

        asks_word = any(kw in text for kw in ("word", "docx", ".docx", "document word", "fichier word", "pandoc"))
        if asks_word and (asks_creation or any(v in text for v in ("fais", "faire", "produis", "genere", "cree", "redige", "livre"))):
            return self._decision(
                "document_generation", request, 0.94,
                capabilities=["document_generation", "writing"],
                tools=["generate_docx", "read_file", "write_file", "list_files"],
                workspace=True,
                modification=True,
                criteria=["document Word (.docx) généré via Pandoc", "formules mathématiques converties en OMML", "fichier Word vérifié et intègre"],
                rationale=["demande de génération de document Word (DOCX) via Pandoc"],
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
        files_required: list[str] | None = None,
    ) -> IntentDecision:
        return IntentDecision(
            intent=intent,
            confidence=confidence,
            objective=request.strip(),
            required_capabilities=capabilities,
            secondary_capabilities=secondary or [],
            required_tools=tools or [],
            files_required=files_required if files_required is not None else cls._files(request),
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
