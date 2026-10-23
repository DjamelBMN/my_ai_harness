# RÔLE DE CE FICHIER :
# Sélectionne l'agent le plus adapté à une mission à partir de l'override, de
# l'intention, des capacités et des besoins. Orchestrator l'utilise avant l'exécution.

from __future__ import annotations

from dataclasses import dataclass

from core.agent_registry import AgentRegistry
from core.task import Task
from core.task_state import TaskState


class AgentSelectionError(ValueError):
    """La mission demande un agent qui n'est pas disponible."""


@dataclass(frozen=True)
class AgentSelection:
    key: str
    agent: object
    score: int
    reasons: tuple[str, ...]


class AgentSelector:
    def __init__(self, registry: AgentRegistry, default_agent: str = "researcher") -> None:
        self.registry = registry
        self.default_agent = default_agent

    def select(self, task: Task, state: TaskState) -> AgentSelection:
        requested_key = task.type.strip() if task.type else ""
        is_explicit = task.explicit_agent or (
            requested_key and requested_key.casefold() != self.default_agent.casefold()
        )
        if is_explicit:
            try:
                key, agent = self.registry.resolve(requested_key)
            except KeyError as error:
                raise AgentSelectionError(str(error)) from None
            return AgentSelection(key, agent, 100, ("agent explicitement demandé",))

        decision = state.intent_decision or {}
        required = set(decision.get("required_capabilities", ()))
        if not required:
            # Compatibilité avec les TaskState construits par un appelant ancien.
            required = {
                "coding": {"coding"},
                "testing": {"testing"},
                "review": {"review"},
                "research": {"research"},
                "file_analysis": {"file_analysis"},
                "exam_creation": {"exam_creation"},
            }.get(state.intent, set())

        scored: list[tuple[int, str, object, list[str]]] = []
        for key, agent in self.registry.agents.items():
            score = 0
            reasons: list[str] = []
            if state.intent in agent.supported_intents:
                score += 12
                reasons.append(f"intention prise en charge : {state.intent}")
            matched = required.intersection(agent.capabilities)
            if matched:
                score += 5 * len(matched)
                reasons.append("capacités : " + ", ".join(sorted(matched)))
            if key == state.assigned_agent:
                score += 1
                reasons.append("suggestion initiale du planner")
            if score:
                scored.append((score, key, agent, reasons))

        if scored:
            score, key, agent, reasons = sorted(
                scored, key=lambda item: (-item[0], item[1])
            )[0]
            return AgentSelection(key, agent, score, tuple(reasons))

        try:
            key, agent = self.registry.resolve(self.default_agent)
        except KeyError:
            available = sorted(self.registry.agents)
            if not available:
                raise AgentSelectionError("Aucun agent n'est disponible.") from None
            key, agent = self.registry.resolve(available[0])
        return AgentSelection(key, agent, 0, ("fallback configuré",))

    def select_for_capability(
        self,
        capability: str,
        *,
        exclude: set[str] | None = None,
    ) -> AgentSelection | None:
        excluded = {self.registry.normalize(item) for item in (exclude or set())}
        normalized_capability = self.registry.normalize(capability)
        candidates = []
        for key, agent in self.registry.agents.items():
            known_capabilities = {self.registry.normalize(item) for item in agent.capabilities}
            if key in excluded or normalized_capability not in known_capabilities:
                continue
            candidates.append((key, agent))
        if not candidates:
            return None
        key, agent = sorted(candidates, key=lambda item: item[0])[0]
        return AgentSelection(
            key,
            agent,
            10,
            (f"capacité requise : {capability}",),
        )
