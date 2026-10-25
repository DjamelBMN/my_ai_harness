# RÔLE DE CE FICHIER :
# Fournit aux gestionnaires de Skills les services existants du Harness. Il ne
# remplace ni Orchestrator ni AgentLoop et partage le contexte de la session.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.task import Task


@dataclass
class SkillRuntime:
    orchestrator: Any
    agent_loop: Any
    settings: dict
    mode: str
    args: Any = None
    memory: Any = None
    mode_manager: Any = None

    @property
    def workspace(self) -> Path:
        return self.agent_loop.tools.filesystem.root

    def run_task(
        self,
        mission: str,
        *,
        agent_key: str | None = None,
        instructions: str = "",
        allowed_tools: list[str] | tuple[str, ...] | None = None,
        automatic: bool = False,
        skill: Any = None,
    ):
        text = mission.strip()
        if not text:
            raise ValueError("Ajoute une mission après la commande Skill.")
        if automatic:
            self.orchestrator.router.enable_automatic_routing()
            task = Task(description=text, type=self.orchestrator.default_agent)
        else:
            key = (agent_key or self.orchestrator.default_agent).strip().casefold()
            task = Task(description=text, type=key, explicit_agent=True)
        task.task_context = getattr(self.orchestrator.context, "task_context", None)
        task.context = self.orchestrator.context
        task.mode = (
            self.mode_manager.current.value
            if self.mode_manager is not None
            else self.agent_loop.tools.permissions.mode
        )
        if skill is not None:
            task.skill_name = skill.name
            task.skill = skill
            skill_text = "\n\n".join(
                part for part in (skill.instructions, skill.rules) if part
            )
            if skill.template_contents:
                template_sections = []
                for tmpl_name, tmpl_code in skill.template_contents.items():
                    template_sections.append(
                        f"=== GABARIT LATEX OBLIGATOIRE ({tmpl_name}) ===\n"
                        f"Tu DOIS utiliser strictement les commandes et la structure de ce gabarit officiel :\n"
                        f"```latex\n{tmpl_code}\n```"
                    )
                skill_text += "\n\n" + "\n\n".join(template_sections)
            instructions = "\n\n".join(
                part for part in (skill_text, instructions) if part
            )
            if allowed_tools is None:
                allowed_tools = skill.tools
        task.instructions = instructions.strip()
        task.allowed_tools = tuple(allowed_tools) if allowed_tools is not None else None
        state = self.agent_loop.planner.plan(task)
        if automatic:
            # Une Skill de routage peut déclarer un catalogue large. Ne montrer
            # au modèle que les tools correspondant à la mission classée.
            if task.allowed_tools is not None:
                required = set(state.intent_decision.get("required_tools", []))
                task.allowed_tools = tuple(
                    tool for tool in task.allowed_tools if tool in required
                )
            selection = self.orchestrator.agent_selector.select(task, state)
            provider = self.orchestrator.router.get_provider(
                selection.agent.routing_key,
                intent=state.intent,
                complexity=state.complexity,
            )
            print("[ROUTING]")
            print(f"Tâche : {state.intent}")
            print(f"Agent sélectionné : {selection.agent.name}")
            print(
                f"Modèle sélectionné : {provider.get_name()} / "
                f"{provider.get_model_name()}"
            )
            reasons = list(selection.reasons)
            route_label = self.orchestrator.router.last_provider_key
            if self.orchestrator.router.automatic_routing:
                reasons.append(f"route configurée ou provider de session ({route_label})")
            print("Raison : " + "; ".join(reasons))
        return self.orchestrator.run_agentic(task, self.agent_loop, state=state)
