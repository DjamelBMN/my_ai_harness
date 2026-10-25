# RÔLE DE CE FICHIER :
# Définit l'état structuré et les résultats d'une mission pendant son exécution.
# AgentLoop, Planner, Verifier et ToolRegistry ajoutent ici leurs observations.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class TaskStatus(StrEnum):
    IDLE = "idle"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    VERIFYING = "verifying"
    CORRECTING = "correcting"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class PlanStep:
    description: str
    status: str = "pending"
    agent: str | None = None


@dataclass
class TaskState:
    """Mémoire de tâche volatile, conservée tant que la mission s'exécute."""

    user_request: str
    task_id: str = field(default_factory=lambda: uuid4().hex)
    intent: str = "general_question"
    intent_decision: dict = field(default_factory=dict)
    complexity: str = "simple"
    assigned_agent: str = "researcher"
    requires_web_search: bool = False
    objective: str = ""
    constraints: list[str] = field(default_factory=list)
    plan: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    observations: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    verification_results: list[dict] = field(default_factory=list)
    parent_task_id: str | None = None
    delegation_depth: int = 0
    agent_history: list[str] = field(default_factory=list)
    child_task_ids: list[str] = field(default_factory=list)
    delegation_results: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    completed: bool = False
    confidence: float | None = None
    status: TaskStatus = TaskStatus.IDLE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    mode: str = "ACCEPT"
    skill_name: str | None = None
    relevant_lessons: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        normalized_plan: list[PlanStep] = []
        for item in self.plan:
            if isinstance(item, PlanStep):
                normalized_plan.append(item)
            elif isinstance(item, str):
                normalized_plan.append(PlanStep(description=item))
            elif isinstance(item, dict):
                normalized_plan.append(
                    PlanStep(
                        description=str(item.get("description", "")),
                        status=str(item.get("status", "pending")),
                        agent=item.get("agent"),
                    )
                )
        self.plan = normalized_plan

    def record_tool_result(self, result: dict) -> None:
        self.tool_results.append(result)
        self.observations.append(
            {
                "kind": "tool_result",
                "tool": result.get("tool"),
                "status": result.get("status"),
                "summary": result.get("summary", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        tool_name = result.get("tool")
        if tool_name in {"read_file", "read_document", "write_file", "patch_file", "delete_file"}:
            paths = result.get("files", [])
        elif tool_name == "move_file":
            paths = [result.get("data", {}).get("source"), result.get("data", {}).get("destination")]
        else:
            # Lister/rechercher ne signifie pas que chaque résultat est un fichier
            # effectivement consulté ou touché par la mission.
            paths = []
        for path in paths:
            if not isinstance(path, str):
                continue
            if path not in self.files:
                self.files.append(path)
        if result.get("status") == "error":
            self.errors.append(
                {"tool": result.get("tool"), "message": result.get("summary", "")}
            )

    def to_dict(self) -> dict:
        """Retourne un JSON-serializable snapshot sans outil/provider objects."""
        snapshot = asdict(self)
        snapshot["status"] = self.status.value
        return snapshot


@dataclass
class AgentResult:
    status: str
    summary: str
    artifacts: list[dict] = field(default_factory=list)
    observations: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    answer: str = ""

