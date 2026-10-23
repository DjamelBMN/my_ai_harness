# RÔLE DE CE FICHIER :
# Exécute le cycle planifier/appeler le modèle/outils/observer/vérifier/corriger.
# Orchestrator le pilote; ToolRegistry applique les autorisations avant les actions.

from __future__ import annotations

import json
import time
from typing import Any, Callable

from core.planner import Planner
from core.task import Task
from core.task_state import AgentResult, PlanStep, TaskState, TaskStatus
from core.verifier import Verifier
from tools.registry import ToolCall, ToolExecution, ToolRegistry


class AgentLoop:
    def __init__(
        self,
        tools: ToolRegistry,
        planner: Planner | None = None,
        verifier: Verifier | None = None,
        *,
        max_iterations: int = 8,
        max_retries: int = 2,
        max_tool_calls: int = 20,
        emit: Callable[[str], None] | None = print,
    ) -> None:
        self.tools = tools
        self.planner = planner or Planner()
        self.verifier = verifier or Verifier()
        self.max_iterations = max(1, max_iterations)
        self.max_retries = max(0, max_retries)
        self.max_tool_calls = max(1, max_tool_calls)
        self.emit = emit
        self.delegation_engine = None

    def _emit(self, message: str) -> None:
        if self.emit is not None:
            self.emit(message)

    @staticmethod
    def _target_label(arguments: dict[str, Any]) -> str:
        targets = []
        for key in ("path", "script_path", "source", "destination"):
            value = arguments.get(key)
            if isinstance(value, str) and value:
                targets.append(f"{key}={value[:200]}")
        return " [" + ", ".join(targets) + "]" if targets else ""

    def _initial_prompt(
        self,
        agent,
        task: Task,
        state: TaskState,
        initial_results: list[ToolExecution],
    ) -> str:
        plan_lines = [f"{index + 1}. {step.description}" for index, step in enumerate(state.plan)]
        evidence = [
            {"tool": item.tool, "status": item.status, "output": item.output}
            for item in initial_results
        ]
        parts = [
                agent.build_prompt(task),
                "MISSION STATE (plan évolutif):\n" + "\n".join(plan_lines),
                "DÉCISION DE MISSION:\n" + json.dumps(state.intent_decision, ensure_ascii=False),
                (
                    "Agents secondaires prévus : "
                    + ", ".join(state.intent_decision.get("secondary_agents", []))
                    + ". Chaque agent secondaire listé est une étape requise : délègue-lui "
                    "une sous-mission précise avec delegate_to_agent, observe son résultat "
                    "et intègre-le avant ta réponse finale."
                    if state.intent_decision.get("secondary_agents")
                    else "Aucun agent secondaire n'est requis par la décision de mission."
                ),
                "ÉVIDENCE INITIALE ISSUE DES OUTILS:\n"
                + json.dumps(evidence, ensure_ascii=False),
                (
                    "Tu peux appeler les outils déclarés. L'appel d'un outil ne prouve "
                    "pas sa réussite : attends son résultat, observe-le, corrige si "
                    "nécessaire, puis donne une réponse finale. N'invente jamais un "
                    "chemin, une lecture, un test ou une source. Les chemins sont "
                    "relatifs à la racine du workspace. Ne révèle aucune pensée privée; "
                    "rapporte seulement les conclusions utiles et les preuves observées."
                ),
                (
                    "Si des sources Web sont demandées, distingue FACT, SOURCE, INFERENCE "
                    "et UNKNOWN. Cite uniquement les sources remontées par l'outil de recherche."
                    if state.requires_web_search
                    else "N'invente pas de sources Web ni de citations."
                ),
                (
                    "Pour corriger un bug : inspecte le code, lance d'abord une suite qui "
                    "reproduit l'échec, modifie ensuite, puis relance la suite. Si tu ne peux "
                    "pas reproduire le bug, explique cette limite et ne dis pas qu'il est corrigé."
                    if any(word in task.description.casefold() for word in ("bug", "corrige", "répare", "fix "))
                    else ""
                ),
        ]
        return "\n\n".join(part for part in parts if part)

    def _run_initial_observations(self, state: TaskState) -> list[ToolExecution]:
        executions = []
        for name, arguments in self.planner.initial_observation_tools(state):
            if name not in {tool.name for tool in self.tools.discover()}:
                continue
            self._emit(
                f"[TOOL] {name}{self._target_label(arguments)} (perception initiale)"
            )
            state.observations.append(
                {"kind": "tool_call", "tool": name, "target": self._target_label(arguments).strip()}
            )
            execution = self.tools.execute(ToolCall(name=name, arguments=arguments))
            self._record_execution(state, execution, call_id="planner")
            self._emit(f"[RESULT] {execution.status}: {execution.summary}")
            executions.append(execution)
        return executions

    @staticmethod
    def _record_execution(state: TaskState, execution: ToolExecution, call_id: str) -> dict[str, Any]:
        record = execution.to_dict()
        record["call_id"] = call_id
        record["name"] = execution.tool
        state.record_tool_result(record)
        return {
            "call_id": call_id,
            "name": execution.tool,
            "status": execution.status,
            "summary": execution.summary,
            "output": execution.output,
            "data": execution.data,
        }

    def run(
        self,
        agent,
        task: Task,
        state: TaskState | None = None,
        *,
        delegation_stack: tuple[tuple[str, str], ...] | None = None,
    ) -> AgentResult:
        if agent.provider is None:
            raise RuntimeError("L'agent doit recevoir son provider via ModelRouter avant AgentLoop.")
        state = state or self.planner.plan(task)
        state.status = TaskStatus.UNDERSTANDING
        provider = agent.provider
        if not state.agent_history:
            state.agent_history.append(agent.name)
        if delegation_stack is None:
            delegation_stack = (
                (agent.routing_key, " ".join(task.description.casefold().split())),
            )
        self._emit(f"[TASK] {state.task_id} | intent={state.intent} | agent={agent.name}")
        self._emit("[PLAN]")
        for index, step in enumerate(state.plan, start=1):
            self._emit(f"  {index}. {step.description}")
        self._emit(f"[MODEL] {provider.get_name()} / {provider.get_model_name()}")

        state.status = TaskStatus.PLANNING
        if state.plan:
            state.plan[0].status = "in_progress"
        initial_results = self._run_initial_observations(state)
        prompt: str | None = self._initial_prompt(agent, task, state, initial_results)
        continuation: Any = None
        pending_tool_results: list[dict[str, Any]] = []
        schemas = self.tools.schemas()
        mission_tools = set(state.intent_decision.get("required_tools", []))
        if mission_tools:
            schemas = [item for item in schemas if item.get("name") in mission_tools]
        allowed_tools = getattr(agent, "allowed_tools", None)
        if allowed_tools is not None:
            permitted = set(allowed_tools)
            schemas = [item for item in schemas if item.get("name") in permitted]
        if self.delegation_engine is not None:
            schemas.append(
                self.delegation_engine.schema(
                    state.intent_decision.get("allowed_secondary_agents")
                )
            )
        if state.requires_web_search:
            if provider.get_name() == "GeminiProvider":
                schemas.append(
                    {
                        "name": "google_search_grounding",
                        "description": "Recherche Web intégrée de Gemini pour trouver des sources récentes.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                        "builtin": "google_search",
                    }
                )
            else:
                state.observations.append(
                    {
                        "kind": "tool_unavailable",
                        "tool": "web_search",
                        "status": "unavailable",
                        "reason": "Aucun backend Web compatible avec ce provider n'est connecté.",
                    }
                )
        total_calls = 0
        correction_count = 0
        final_answer = ""
        verification: dict[str, Any] = {"status": "not_required", "checks": []}
        provider_error: str | None = None

        for iteration in range(1, self.max_iterations + 1):
            state.current_step = iteration
            state.status = TaskStatus.EXECUTING
            self._emit(f"[AGENT LOOP] iteration {iteration}/{self.max_iterations}")
            attempt = 0
            while True:
                try:
                    active_schemas = schemas
                    if state.sources:
                        active_schemas = [
                            item for item in schemas
                            if item.get("builtin") != "google_search"
                        ]
                    turn = provider.generate_agent_turn(
                        prompt,
                        active_schemas,
                        continuation=continuation,
                        tool_results=pending_tool_results,
                    )
                    provider_error = None
                    break
                except Exception as error:
                    attempt += 1
                    provider_error = f"{type(error).__name__}: {error}"
                    state.errors.append(
                        {"phase": "provider", "iteration": iteration, "message": provider_error}
                    )
                    self._emit(f"[ERROR] provider: {provider_error}")
                    if attempt > self.max_retries:
                        state.status = TaskStatus.FAILED
                        return self._failure_result(state, provider_error)
                    self._emit(f"[RETRY] provider attempt {attempt}/{self.max_retries}")
                    time.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))

            continuation = turn.continuation
            for source in turn.sources:
                if source not in state.sources:
                    state.sources.append(source)
                    state.observations.append(
                        {"kind": "source", "status": "verified", **source}
                    )
            prompt = None
            if turn.tool_calls:
                state.status = TaskStatus.OBSERVING
                remaining = self.max_tool_calls - total_calls
                selected_calls = turn.tool_calls[: max(0, remaining)]
                if not selected_calls:
                    state.status = TaskStatus.BLOCKED
                    return self._failure_result(
                        state, "La limite d'appels d'outils a été atteinte."
                    )
                calls = [
                    ToolCall(name=item.name, arguments=item.arguments, call_id=item.call_id)
                    for item in selected_calls
                ]
                for call in calls:
                    target = self._target_label(call.arguments)
                    self._emit(f"[TOOL] {call.name}{target}")
                    state.observations.append(
                        {
                            "kind": "tool_call",
                            "tool": call.name,
                            "target": target.strip(),
                        }
                    )
                if all(call.name != "delegate_to_agent" for call in calls):
                    executions = []
                    for call in calls:
                        if (
                            (allowed_tools is not None and call.name not in set(allowed_tools))
                            or (mission_tools and call.name not in mission_tools)
                        ):
                            executions.append(
                                ToolExecution(
                                    tool=call.name,
                                    status="error",
                                    summary=f"L'outil {call.name} n'est pas autorisé pour {agent.name}.",
                                    output="Appel d'outil refusé par les capacités de l'agent.",
                                    risk_level="READ_ONLY",
                                )
                            )
                        else:
                            executions.append(None)
                    if any(item is None for item in executions):
                        raw_calls = [
                            call for call, execution in zip(calls, executions)
                            if execution is None
                        ]
                        raw_results = iter(self.tools.execute_many(raw_calls))
                        executions = [
                            next(raw_results) if execution is None else execution
                            for execution in executions
                        ]
                else:
                    executions = []
                    for call in calls:
                        if call.name == "delegate_to_agent":
                            engine = self.delegation_engine
                            if engine is None:
                                execution = ToolExecution(
                                    tool=call.name,
                                    status="error",
                                    summary="La délégation n'est pas configurée pour cette boucle.",
                                    output="Aucun DelegationEngine n'est disponible.",
                                    risk_level="READ_ONLY",
                                )
                            else:
                                execution = engine.execute(
                                    agent,
                                    state,
                                    call.arguments,
                                    delegation_stack,
                                )
                        elif (
                            (allowed_tools is not None and call.name not in set(allowed_tools))
                            or (mission_tools and call.name not in mission_tools)
                        ):
                            execution = ToolExecution(
                                tool=call.name,
                                status="error",
                                summary=f"L'outil {call.name} n'est pas autorisé pour {agent.name}.",
                                output="Appel d'outil refusé par les capacités de l'agent.",
                                risk_level="READ_ONLY",
                            )
                        else:
                            execution = self.tools.execute(call)
                        executions.append(execution)
                pending_tool_results = []
                for call, execution in zip(calls, executions):
                    total_calls += 1
                    record = self._record_execution(state, execution, call.call_id)
                    pending_tool_results.append(record)
                    self._emit(f"[RESULT] {execution.status}: {execution.summary}")
                if any(item.status == "error" for item in executions):
                    state.status = TaskStatus.CORRECTING
                    state.plan.append(
                        PlanStep(
                            "Diagnostiquer l'échec d'outil puis choisir une action corrective sûre.",
                            "pending",
                            agent.name,
                        )
                    )
                    self._emit("[REPLAN] un outil a échoué; le modèle reçoit l'erreur observée.")
                continue

            if turn.partial:
                continuation = turn.continuation
                prompt = (
                    "La réponse précédente a atteint sa limite de sortie. Continue à partir "
                    "de l'historique conservé; termine la réponse ou demande un outil."
                )
                continue

            final_answer = turn.text.strip()
            if not final_answer:
                provider_error = "Le modèle n'a fourni ni réponse finale ni appel d'outil."
                state.errors.append({"phase": "model_turn", "message": provider_error})
                if iteration < self.max_iterations:
                    prompt = "Réponds maintenant par un outil valide ou une réponse finale vérifiable."
                    continue
                state.status = TaskStatus.FAILED
                return self._failure_result(state, provider_error)

            state.status = TaskStatus.VERIFYING
            verification = self.verifier.verify(state, self.tools.filesystem)
            self._emit(f"[VERIFICATION] {verification['status']}: {verification['summary']}")
            if verification["status"] == "failed":
                correction_count += 1
                if correction_count <= self.max_retries and iteration < self.max_iterations:
                    state.status = TaskStatus.CORRECTING
                    state.plan.append(
                        PlanStep(
                            "Compléter les critères de vérification manquants, puis vérifier à nouveau.",
                            "pending",
                            agent.name,
                        )
                    )
                    prompt = (
                        "La vérification déterministe n'est pas passée. Ne dis pas que la tâche "
                        "est terminée. Effectue les actions sûres manquantes, demande les "
                        "autorisations nécessaires, puis redonne une réponse finale. Résultats "
                        "de vérification : " + json.dumps(verification, ensure_ascii=False)
                    )
                    pending_tool_results = []
                    self._emit("[REPLAN] vérification incomplète; tentative de correction bornée.")
                    continue
                state.status = TaskStatus.BLOCKED
                final_answer = (
                    final_answer
                    + "\n\nVérification incomplète : "
                    + verification["summary"]
                    + " Aucune réussite non vérifiée n'est annoncée."
                )
                state.completed = False
                return self._success_shape(state, final_answer, verification, status="incomplete")

            if state.sources:
                citations = "\n\nSources effectivement consultées :\n" + "\n".join(
                    f"- [{source.get('title') or source.get('url')}]({source.get('url')})"
                    for source in state.sources
                    if source.get("url", "").startswith("https://")
                )
                if citations.strip() != "Sources effectivement consultées :":
                    final_answer += citations

            state.status = TaskStatus.COMPLETED
            state.completed = True
            for step in state.plan:
                if step.status in {"ready", "pending", "in_progress"}:
                    step.status = "completed"
            state.observations.append(
                {"kind": "delivery", "status": "delivered", "agent": agent.name}
            )
            self._emit("[DELIVER]")
            verified_test = any(
                check.get("check") == "tests_executed_and_passed"
                and check.get("status") == "passed"
                for check in verification.get("checks", [])
            )
            result_status = (
                "success" if verified_test
                else "verified" if verification.get("status") == "passed"
                else "answered"
            )
            return self._success_shape(
                state, final_answer, verification, status=result_status
            )

        state.status = TaskStatus.BLOCKED
        message = "La limite de tours agentiques a été atteinte avant une réponse vérifiée."
        if provider_error:
            message += " Dernière erreur : " + provider_error
        return self._failure_result(state, message)

    @staticmethod
    def _success_shape(
        state: TaskState,
        answer: str,
        verification: dict[str, Any],
        *,
        status: str,
    ) -> AgentResult:
        artifacts = []
        for item in state.tool_results:
            tool_name = item.get("tool")
            data = item.get("data", {})
            if tool_name in {"write_file", "patch_file"} and data.get("path"):
                artifacts.append(
                    {"path": data["path"], "sha256": data.get("sha256")}
                )
            elif tool_name == "move_file" and data.get("destination"):
                artifacts.append({"path": data["destination"]})
            elif tool_name == "delegate_to_agent":
                delegated = data.get("artifacts", [])
                if isinstance(delegated, list):
                    artifacts.extend(item for item in delegated if isinstance(item, dict))
        return AgentResult(
            status=status,
            summary=answer[:500],
            artifacts=artifacts,
            observations=state.observations,
            errors=state.errors,
            next_actions=[],
            verification=verification,
            answer=answer,
        )

    @classmethod
    def _failure_result(cls, state: TaskState, message: str) -> AgentResult:
        return cls._success_shape(
            state,
            "Mission non terminée : " + message,
            {"status": "failed", "checks": [], "summary": message},
            status="failed",
        )

