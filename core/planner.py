# RÔLE DE CE FICHIER :
# Déduit l'intention, choisit l'agent et crée un plan de départ modifiable par
# l'AgentLoop. Les routages explicitement demandés par l'utilisateur sont prioritaires.

from __future__ import annotations

import re
from typing import Any

from core.task import Task, ensure_task
from core.task_state import PlanStep, TaskState
from core.intent_engine import IntentDecision, IntentEngine


class ClarificationRequired(ValueError):
    """La requête est trop ambiguë pour démarrer une action sûre."""


class Planner:
    AGENTS = {"coder", "tester", "reviewer", "researcher"}
    FILE_EXTENSIONS = {
        ".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".pdf", ".docx",
        ".xlsx", ".pptx", ".html", ".css", ".js", ".ts", ".py",
    }

    def __init__(self, reflective_memory: Any | None = None) -> None:
        self.intent_engine = IntentEngine()
        self.reflective_memory = reflective_memory

    def set_agent_registry(self, registry) -> None:
        """Active la reconnaissance des capacités ajoutées par les plugins."""
        self.intent_engine.agent_registry = registry

    def plan(self, task: Task | str) -> TaskState:
        task = ensure_task(task)
        if task.skill is None and task.type.strip().lower() in {"bacblancagent", "bacblanc", "exerciceagent", "dmagent"}:
            task.type = "researcher"
            task.explicit_agent = False
        request = task.description.strip()
        if not request:
            raise ClarificationRequired("Décris la mission que tu veux confier au harness.")

        task_context = getattr(task, "task_context", None)
        if task_context is None and task.context is not None:
            task_context = getattr(task.context, "task_context", None)

        skill = task.skill
        if skill is not None and not bool(skill.config.get("auto_route")):
            config = skill.config
            intent = str(config.get("intent") or "specialized")
            agent = skill.agent.routing_key if skill.agent is not None else task.type
            normalized_request = request.casefold()
            web_triggers = [str(item).casefold() for item in config.get("requires_web_when", [])]
            test_triggers = [str(item).casefold() for item in config.get("requires_tests_when", [])]
            web_required = (
                bool(config.get("requires_web", False))
                or any(trigger in normalized_request for trigger in web_triggers)
                or (
                    "web_search" in skill.tools
                    and self.intent_engine.is_web_query(normalized_request)
                )
            )
            tests_required = bool(config.get("requires_tests", False)) or any(
                trigger in normalized_request for trigger in test_triggers
            )
            secondary_capabilities = list(config.get("secondary_capabilities", []))
            for capability, triggers in config.get("conditional_secondary_capabilities", {}).items():
                if any(str(trigger).casefold() in normalized_request for trigger in triggers):
                    if capability not in secondary_capabilities:
                        secondary_capabilities.append(capability)
            required_tools = list(skill.tools)
            if web_required and "web_search" not in required_tools:
                required_tools.append("web_search")
            decision = IntentDecision(
                intent=intent,
                confidence=1.0,
                objective=request,
                primary_agent=skill.agent.name if skill.agent is not None else None,
                required_capabilities=list(config.get("capabilities", [])),
                secondary_capabilities=secondary_capabilities,
                allowed_secondary_agents=list(config.get("allowed_secondary_agents", [])),
                required_tools=required_tools,
                requires_workspace=bool(config.get("requires_workspace", False)),
                requires_file_read=bool(config.get("requires_file_read", False)),
                requires_modification=bool(config.get("requires_modification", False)),
                requires_tests=tests_required,
                requires_web=web_required,
                requires_verification=bool(config.get("requires_verification", True)),
                risk_level=str(config.get("risk_level", "READ_ONLY")),
                requires_user_confirmation=bool(config.get("requires_user_confirmation", False)),
                success_criteria=list(config.get("success_criteria", [])),
                rationale=[f"slash command explicite /{skill.name}"],
            )
        else:
            try:
                decision = self.intent_engine.decide(request, task_context=task_context)
            except ValueError as error:
                raise ClarificationRequired(str(error)) from None

        if skill is not None and not bool(skill.config.get("auto_route")):
            intent = decision.intent
        elif task.explicit_agent or task.type != "researcher":
            agent = task.type.strip().lower()
            builtin_intents = {
                "coder": "coding",
                "tester": "testing",
                "reviewer": "review",
                "researcher": "research",
            }
            if decision.intent == "computer_use" and agent == "coder":
                intent = "computer_use"
            elif agent in builtin_intents:
                intent = builtin_intents[agent]
            else:
                intent = decision.intent
            if agent == "researcher":
                if decision.intent == "research":
                    intent = "research"
                elif self._mentions_local_files(request):
                    intent = "file_analysis"
        else:
            intent = decision.intent
            agent = self._suggested_agent(intent)

        decision.intent = intent
        if skill is not None and skill.agent is not None:
            decision.primary_agent = skill.agent.name
        elif task.explicit_agent or task.type != "researcher":
            decision.primary_agent = task.type.strip()
        else:
            decision.primary_agent = agent

        relevant_lessons = []
        if self.reflective_memory is not None:
            try:
                relevant_lessons = self.reflective_memory.retrieve_relevant_lessons(request, limit=3)
            except Exception:
                relevant_lessons = []

        state = TaskState(
            user_request=request,
            mode=task.mode,
            skill_name=(task.skill_name or (skill.name if skill is not None else None)),
            intent=intent,
            intent_decision=decision.to_dict(),
            complexity=self._complexity(intent, request),
            objective=request,
            requires_web_search=decision.requires_web,
            constraints=[
                "N'utiliser que les outils enregistrés et les chemins dans le workspace.",
                "Ne jamais annoncer une vérification qu'un outil n'a pas exécutée.",
                "Ne jamais prétendre avoir lu un fichier si l'extraction a échoué.",
            ],
        )
        state.relevant_lessons = relevant_lessons
        if task_context is not None:
            is_pivot = bool(
                hasattr(task_context, "is_pivot_request")
                and task_context.is_pivot_request(request)
            )
            if not is_pivot:
                for f in getattr(task_context, "files", []):
                    if f not in state.files:
                        state.files.append(f)
            get_unresolved = getattr(task_context, "get_unresolved_errors", None)
            if callable(get_unresolved):
                for err in get_unresolved():
                    state.errors.append({"message": err.get("message"), "compiler": err.get("compiler")})
        if skill is not None:
            for relative_path, content in skill.template_contents.items():
                state.observations.append(
                    {
                        "kind": "skill_template_read",
                        "path": relative_path,
                        "status": "success",
                        "characters": len(content),
                    }
                )
            for relative_path, content in skill.rag_contents.items():
                state.observations.append(
                    {
                        "kind": "skill_rag_read",
                        "path": relative_path,
                        "status": "success",
                        "characters": len(content),
                    }
                )
            for relative_path, error in skill.resource_errors.items():
                state.observations.append(
                    {
                        "kind": "skill_resource_read",
                        "path": relative_path,
                        "status": "error",
                        "error": error,
                    }
                )
        state.plan = self._steps(intent, request, agent)
        state.observations.append(
            {"kind": "intent", "value": intent, "agent": agent, "status": "inferred"}
        )
        state.assigned_agent = agent
        return state

    @classmethod
    def _mentions_local_files(cls, request: str) -> bool:
        normalized = request.casefold()
        if any(w in normalized for w in ("sur internet", "sur le web", "télécharge", "telecharge", "download")):
            return False
        return any(ext in normalized for ext in cls.FILE_EXTENSIONS) or any(
            phrase in normalized
            for phrase in (" fichier", " document", " projet", " dossier", "workspace")
        )

    @classmethod
    def _requires_workspace(cls, intent: str, request: str) -> bool:
        if intent in {"file_analysis", "testing"}:
            return True
        if intent == "coding":
            return True
        if cls._mentions_local_files(request):
            return True
        return intent == "coding" and any(
            marker in request.casefold()
            for marker in (
                "corrige", "modifie", "implémente", "implement", "fix ",
                "refactor", "répare", "edit ", "ajoute", "crée un fichier", "écris dans",
                "supprime", "déplace", "delete ", "move ",
            )
        )

    @staticmethod
    def _complexity(intent: str, request: str) -> str:
        """Estimation grossière destinée au routage, pas une mesure de confiance."""
        text = request.casefold()
        complex_markers = (
            "compare", "plusieurs", "sources", "corrige", "modifie", "implémente",
            "tests", "régression", "analyse", "diagnostique", "planifie", "puis",
        )
        if intent in {"coding", "testing", "review", "file_analysis", "computer_use"}:
            return "complex"
        if len(request) > 300 or sum(marker in text for marker in complex_markers) >= 2:
            return "complex"
        return "simple"

    def classify(self, request: str) -> tuple[str, str]:
        try:
            intent = self.intent_engine.decide(request).intent
        except ValueError as error:
            raise ClarificationRequired(str(error)) from None
        return intent, self._suggested_agent(intent)

    @staticmethod
    def _suggested_agent(intent: str) -> str:
        """Suggestion historique; AgentSelector choisit réellement via le registre."""
        return {
            "coding": "coder",
            "debugging": "coder",
            "computer_use": "coder",
            "testing": "tester",
            "review": "reviewer",
            "file_analysis": "researcher",
            "research": "researcher",
            "exam_creation": "researcher",
            "general_question": "researcher",
        }.get(intent, "researcher")

    @staticmethod
    def _steps(intent: str, request: str, agent: str) -> list[PlanStep]:
        steps = [
            PlanStep(f"Comprendre l'objectif et les contraintes ({intent}).", "ready", agent),
        ]
        if Planner._requires_workspace(intent, request):
            steps.append(PlanStep("Inspecter les fichiers nécessaires avec les outils du workspace."))
        if intent == "coding":
            steps.extend(
                [
                    PlanStep("Inspecter l'architecture du workspace et repérer les fichiers pertinents."),
                    PlanStep("Formuler une modification justifiée par les fichiers lus."),
                    PlanStep("Demander l'autorisation avant toute écriture."),
                    PlanStep("Implémenter puis relire les fichiers modifiés."),
                    PlanStep("Lancer les tests pertinents et corriger les échecs dans une boucle bornée."),
                    PlanStep("Vérifier les critères de réussite et les régressions observables."),
                ]
            )
        elif intent == "computer_use":
            req_low = request.replace("’", "'").casefold()
            if any(k in req_low for k in ("capture", "screenshot")) and any(k in req_low for k in ("bureau", "desktop")):
                return [
                    PlanStep("Capturer l'écran actif.", "ready", agent),
                    PlanStep("Enregistrer la capture sur le Bureau Windows.", "pending", agent),
                    PlanStep("Vérifier le fichier créé et confirmer.", "pending", agent),
                ]
            return [
                PlanStep("Observer la cible Windows.", "ready", agent),
                PlanStep("Exécuter l'action avec l'outil natif direct.", "pending", agent),
                PlanStep("Vérifier le résultat observable.", "pending", agent),
            ]
        elif intent == "testing":
            steps.append(PlanStep("Exécuter la suite du workspace et conserver son code retour."))
        elif intent in {"research", "file_analysis"}:
            steps.append(PlanStep("Séparer les faits extraits, les inférences et les inconnues."))
        elif intent == "exam_creation":
            steps.extend(
                [
                    PlanStep("Définir le niveau, la durée, le périmètre et les livrables attendus."),
                    PlanStep("Construire le sujet, le corrigé et le barème selon les contraintes."),
                    PlanStep("Faire contrôler les exigences et les calculs par des agents spécialisés si utile."),
                ]
            )
        steps.append(PlanStep("Présenter le résultat et les limites de vérification."))
        return steps

    def initial_observation_tools(self, state: TaskState) -> list[tuple[str, dict]]:
        """Planifie une vraie lecture ou action d'observation Windows directe sans doublon."""
        if state.intent == "computer_use":
            req_low = state.user_request.replace("’", "'").casefold()
            wants_shot = any(k in req_low for k in ("capture", "screenshot"))
            wants_desktop = any(k in req_low for k in ("bureau", "desktop"))
            if wants_shot:
                return [
                    (
                        "computer_screenshot",
                        {
                            "label": "capture_ecran",
                            "save_to_desktop": wants_desktop,
                        },
                    )
                ]
            if any(k in req_low for k in ("processus", "tasklist", "pid")):
                return [("process_list", {"limit": 30})]
            if any(k in req_low for k in ("fenêtre", "fenetre", "fenêtres", "fenetres")):
                return [("window_list", {"visible_only": True})]
            return []

        if not self._requires_workspace(state.intent, state.user_request):
            return []
        paths = []
        for match in re.finditer(r"[^\s\"']+\.(?:txt|md|json|ya?ml|csv|pdf|docx|xlsx|pptx|html|css|js|ts|py)", state.user_request, re.I):
            candidate = match.group(0).rstrip(").,;:")
            if candidate not in paths:
                paths.append(candidate)
        if paths:
            name = "read_document"
            return [(name, {"path": path}) for path in paths[:3]]
        return [("list_files", {"path": ".", "recursive": True})]
