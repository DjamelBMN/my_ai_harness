# RÔLE DE CE FICHIER :
# Coordonne toute tâche : choisit l'agent, demande un provider au ModelRouter,
# attribue le provider à l'agent, récupère sa réponse et la présente à l'utilisateur.

from core.agent import Agent
from core.agent_registry import AgentRegistry
from core.agent_selector import AgentSelector
from core.context import Context
from core.context_manager import ContextManager
from core.delegation import DelegationEngine
from core.multi_agent_coordinator import MultiAgentCoordinator
from core.router import ModelRouter
from core.task import Task, ensure_task
from core.task_state import AgentResult


class Orchestrator:
    """Chef d'orchestre du harness et point de passage des tâches utilisateur."""

    def __init__(
        self,
        agents: dict[str, Agent] | AgentRegistry,
        router: ModelRouter,
        context: Context | None = None,
        default_agent: str = "researcher",
    ) -> None:
        if isinstance(agents, AgentRegistry):
            self.agent_registry = agents
        else:
            # Les anciens appels avec un dictionnaire restent pris en charge.
            self.agent_registry = AgentRegistry(agents, discover=False)
        self.agents = self.agent_registry.agents
        self.router = router
        self.context = context or Context()
        self.context_manager = ContextManager()
        self.default_agent = default_agent.lower()
        self.agent_selector = AgentSelector(self.agent_registry, self.default_agent)

    def run(self, task: Task | str) -> str:
        """Envoie la tâche à l'agent, puis affiche le résultat final."""
        task = ensure_task(task, default_type=self.default_agent)
        agent_key = task.type.strip().lower() or self.default_agent
        try:
            _, agent = self.agent_registry.resolve(agent_key)
        except KeyError as error:
            raise ValueError(str(error)) from None

        self.context.current_task = task
        if task.context is None:
            task.context = self.context

        provider = self.router.get_provider(agent.routing_key)
        agent.set_provider(provider)

        print()
        print(f"Utilisateur : {task.type}: {task.description}")
        print("|")
        print("Orchestrator")
        print("|")
        print(agent.name)
        print("|")
        print("ModelRouter")
        print("|")
        print(provider.get_name())

        result = agent.run(task)

        model_name = provider.get_model_name()
        if provider.get_name() == "OllamaProvider":
            model_name = f"Qwen / {model_name}"
        elif provider.get_name() == "GeminiProvider":
            model_name = f"Gemini / {model_name}"
        print("|")
        print(model_name)
        print("|")
        print(provider.get_status_label())
        print("|")
        print(agent.name)
        print("|")
        print("Réponse")

        self.context.agent_results[agent.name] = result
        self.context.history.append(
            f"{agent.name} | Tâche : {task.description} | Réponse : {result}"
        )
        print(result)
        return result

    def run_agentic(self, task: Task | str, agent_loop, state=None) -> AgentResult:
        """Nouveau runtime agentique sans modifier le contrat historique run()."""
        task = ensure_task(task, default_type=self.default_agent)
        if getattr(task, "task_context", None) is not None:
            self.context.sync_task_context(task.task_context)
        if hasattr(agent_loop.planner, "set_agent_registry"):
            agent_loop.planner.set_agent_registry(self.agent_registry)
        state = state or agent_loop.planner.plan(task)
        if task.skill is not None and task.skill.agent is not None:
            agent = task.skill.agent
            agent_key = agent.routing_key
            score = 100
            selection_reasons = (f"Skill explicite /{task.skill.name}",)
        else:
            selection = self.agent_selector.select(task, state)
            agent_key = selection.key
            agent = selection.agent
            score = selection.score
            selection_reasons = selection.reasons
        state.assigned_agent = agent_key
        state.agent_history.append(agent.name)
        state.decisions.append(
            {
                "kind": "agent_selection",
                "agent": agent_key,
                "score": score,
                "reasons": list(selection_reasons),
            }
        )
        decision_data = state.intent_decision
        decision_data["primary_agent"] = agent.name
        secondary_selections = []
        for capability in decision_data.get("secondary_capabilities", []):
            excluded = {agent_key, *(item["key"] for item in secondary_selections)}
            secondary = self.agent_selector.select_for_capability(capability, exclude=excluded)
            if secondary is not None:
                secondary_selections.append(
                    {"key": secondary.key, "name": secondary.agent.name, "capability": capability}
                )
        decision_data["secondary_agents"] = [item["key"] for item in secondary_selections]
        decision_data["secondary_agent_details"] = secondary_selections
        if state.plan:
            state.plan[0].agent = agent.name
        print(f"[INTENT] {state.intent}")
        print(f"[CONFIDENCE] {decision_data.get('confidence', 0):.2f} (estimation heuristique)")
        print(f"[AGENT] {agent.name}")
        if secondary_selections:
            print("[DELEGATION] agents suggérés : " + ", ".join(item["name"] for item in secondary_selections))
        if decision_data.get("required_tools"):
            print("[TOOLS] " + ", ".join(decision_data["required_tools"]))
        print("[PLAN]")
        for index, step in enumerate(state.plan, start=1):
            print(f"  {index}. {step.description}")
        print(
            f"[AGENT SELECTOR] {agent.name} | score={score} | "
            + "; ".join(selection_reasons)
        )
        self.context.current_task = task
        if task.context is None:
            task.context = self.context
        self.context_manager.compact(self.context)
        provider = self.router.get_provider(
            agent.routing_key,
            intent=state.intent,
            complexity=state.complexity,
        )
        agent.set_provider(provider)
        coordinator = MultiAgentCoordinator()
        delegation_engine = DelegationEngine(
            self.agent_registry,
            self.agent_selector,
            self.router,
            agent_loop,
            coordinator,
            emit=agent_loop.emit,
        )
        previous_engine = agent_loop.delegation_engine
        agent_loop.delegation_engine = delegation_engine
        agent_loop.router = self.router
        try:
            result = agent_loop.run(agent, task, state=state)
        finally:
            agent_loop.delegation_engine = previous_engine
        if coordinator.records:
            state.observations.append(
                {"kind": "multi_agent_coordinator", "status": "finished", "subtasks": coordinator.snapshot()}
            )
        result.observations = state.observations
        result.errors = state.errors
        self.context.agent_results[agent.name] = result.answer
        self.context.last_result = result.answer
        self.context.mission_memory = {
            "task_id": state.task_id,
            "objective": state.objective,
            "intent": state.intent,
            "status": result.status,
            "agents": list(state.agent_history),
            "files": list(state.files),
            "errors": list(state.errors),
            "verification": list(state.verification_results),
        }
        for path in state.files:
            if path not in self.context.files:
                self.context.files.append(path)
        self.context.files[:] = self.context.files[-20:]
        self.context.history.append(
            f"{agent.name} | tâche={task.description} | statut={result.status} | "
            f"résultat={result.answer[:1800]}"
        )
        self.context.history[:] = self.context.history[-5:]
        if getattr(task, "task_context", None) is not None:
            for path in state.files:
                task.task_context.record_file(path)
            for err in state.errors:
                task.task_context.record_error(str(err.get("message") if isinstance(err, dict) else err))
        print("\n[RESULT]")
        print(result.answer)
        print(f"\n[STATUS] {result.status}")
        return result
