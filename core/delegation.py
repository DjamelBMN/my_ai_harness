# RÔLE DE CE FICHIER :
# Exécute les demandes delegate_to_agent au travers du registre, du sélecteur,
# du ModelRouter et de la même AgentLoop. Les agents ne s'importent pas entre eux.

from __future__ import annotations

import json
from typing import Any

from core.agent_registry import AgentRegistry
from core.agent_selector import AgentSelector
from core.context import Context
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.task import Task
from core.task_state import TaskState
from tools.registry import ToolExecution


class DelegationEngine:
    TOOL_NAME = "delegate_to_agent"

    def __init__(
        self,
        registry: AgentRegistry,
        selector: AgentSelector,
        router,
        agent_loop,
        coordinator: MultiAgentCoordinator,
        *,
        emit=None,
    ) -> None:
        self.registry = registry
        self.selector = selector
        self.router = router
        self.agent_loop = agent_loop
        self.coordinator = coordinator
        self.emit = emit

    @classmethod
    def schema(cls, allowed_agents: list[str] | None = None) -> dict[str, Any]:
        agent_schema: dict[str, Any] = {
            "type": "string",
            "description": "Clé ou nom d'un agent déclaré dans le registre.",
        }
        if allowed_agents:
            agent_schema["enum"] = list(allowed_agents)
        return {
            "name": cls.TOOL_NAME,
            "description": (
                "Délègue une sous-mission à un autre agent disponible. "
                "Le résultat réel lui sera retourné avant de continuer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": agent_schema,
                    "task": {
                        "type": "string",
                        "description": "Sous-mission autonome, précise et vérifiable.",
                    },
                },
                "required": ["agent", "task"],
                "additionalProperties": False,
            },
        }

    def execute(
        self,
        parent_agent,
        parent_state: TaskState,
        arguments: dict[str, Any],
        stack: tuple[tuple[str, str], ...],
    ) -> ToolExecution:
        target = arguments.get("agent")
        description = arguments.get("task")
        if not isinstance(target, str) or not isinstance(description, str):
            return self._error("Les champs 'agent' et 'task' doivent être des chaînes.")
        description = description.strip()
        if not description:
            return self._error("La sous-mission ne peut pas être vide.")
        try:
            key, agent = self.registry.resolve(target)
        except KeyError as error:
            return self._error(str(error))
        allowed_agents = parent_state.intent_decision.get("allowed_secondary_agents", [])
        if allowed_agents:
            allowed = {self.registry.normalize(item) for item in allowed_agents}
            if (
                self.registry.normalize(target) not in allowed
                and key not in allowed
                and self.registry.normalize(agent.name) not in allowed
            ):
                return self._error(
                    f"L'agent {agent.name} n'est pas autorisé par ce Skill pour une délégation."
                )

        try:
            record = self.coordinator.begin(parent_state, key, description, stack)
        except RuntimeError as error:
            return self._error(str(error))

        self._emit(f"[DELEGATION] {parent_agent.name} -> {agent.name} | {description[:180]}")
        parent_state.observations.append(
            {
                "kind": "delegation",
                "status": "started",
                "parent_agent": parent_agent.name,
                "agent": agent.name,
                "task_id": record.task_id,
                "description": description,
            }
        )

        # Le contexte enfant ne partage pas l'historique de session complet.
        # Il reçoit seulement des éléments pertinents de la mission mère.
        handoff = {
            "mission": parent_state.user_request[:1500],
            "objective": parent_state.objective[:1000],
            "observations": parent_state.observations[-8:],
            "tool_results": [
                {
                    "tool": item.get("tool"),
                    "status": item.get("status"),
                    "summary": item.get("summary", "")[:500],
                    "output": item.get("output", "")[:3500],
                    "data": item.get("data", {}),
                }
                for item in parent_state.tool_results[-8:]
            ],
            "files": list(parent_state.files[-20:]),
            "errors": parent_state.errors[-5:],
            "previous_agent_results": parent_state.delegation_results[-5:],
        }
        child_context = Context(
            history=["Contexte de délégation : " + json.dumps(handoff, ensure_ascii=False)[:7000]],
            files=list(parent_state.files[-20:]),
        )
        child_task = Task(description=description, type=key, context=child_context, explicit_agent=True)
        try:
            child_state = self.agent_loop.planner.plan(child_task)
            child_state.task_id = record.task_id
            child_state.parent_task_id = parent_state.task_id
            child_state.delegation_depth = parent_state.delegation_depth + 1
            child_state.agent_history = [*parent_state.agent_history, agent.name]
            selection = self.selector.select(child_task, child_state)
            child_state.assigned_agent = selection.key
            child_state.decisions.append(
                {"kind": "agent_selection", "agent": selection.key, "reasons": list(selection.reasons)}
            )
            provider = self.router.get_provider(
                agent.routing_key,
                intent=child_state.intent,
                complexity=child_state.complexity,
            )
            agent.set_provider(provider)
            child_result = self.agent_loop.run(
                agent,
                child_task,
                state=child_state,
                delegation_stack=stack + ((key, " ".join(description.casefold().split())),),
            )
            result_data = {
                "status": child_result.status,
                "summary": child_result.summary,
                "answer": child_result.answer,
                "artifacts": child_result.artifacts,
                "observations": child_result.observations[-20:],
                "tool_results": child_state.tool_results[-20:],
                "files": child_state.files[-20:],
                "errors": child_result.errors,
                "verification": child_result.verification,
                "sources": child_state.sources[-20:],
                "task_id": record.task_id,
                "agent": agent.name,
            }
            self.coordinator.complete(record.task_id, result_data)
            parent_state.delegation_results.append(result_data)
            for path in child_state.files:
                if path not in parent_state.files:
                    parent_state.files.append(path)
            for source in child_state.sources:
                if source not in parent_state.sources:
                    parent_state.sources.append(source)
            parent_state.observations.append(
                {
                    "kind": "delegation",
                    "status": child_result.status,
                    "agent": agent.name,
                    "task_id": record.task_id,
                    "summary": child_result.summary[:600],
                }
            )
            failed = child_result.status in {"failed", "incomplete", "blocked"}
            status = "error" if failed else "success"
            summary = f"{agent.name} a terminé avec le statut {child_result.status}."
            return ToolExecution(
                tool=self.TOOL_NAME,
                status=status,
                summary=summary,
                output=json.dumps(result_data, ensure_ascii=False),
                data=result_data,
                elapsed_seconds=0.0,
                risk_level="READ_ONLY",
            )
        except Exception as error:
            message = f"{type(error).__name__}: {str(error).replace(chr(10), ' ')[:800]}"
            self.coordinator.fail(record.task_id, message)
            parent_state.errors.append(
                {"phase": "delegation", "agent": key, "message": message}
            )
            parent_state.delegation_results.append(
                {"status": "failed", "agent": agent.name, "task_id": record.task_id, "errors": [message]}
            )
            parent_state.observations.append(
                {"kind": "delegation", "status": "failed", "agent": agent.name, "task_id": record.task_id, "error": message}
            )
            self._emit(f"[DELEGATION ERROR] {message}")
            return ToolExecution(
                tool=self.TOOL_NAME,
                status="error",
                summary=message,
                output=message,
                data={"status": "failed", "agent": agent.name, "task_id": record.task_id},
                risk_level="READ_ONLY",
            )

    @staticmethod
    def _error(message: str) -> ToolExecution:
        return ToolExecution(
            tool=DelegationEngine.TOOL_NAME,
            status="error",
            summary=message,
            output=message,
            data={"status": "failed", "error": message},
            risk_level="READ_ONLY",
        )

    def _emit(self, message: str) -> None:
        if self.emit is not None:
            self.emit(message)
