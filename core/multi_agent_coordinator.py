# RÔLE DE CE FICHIER :
# Suit les sous-missions d'une mission mère, leurs dépendances et leur statut.
# DelegationEngine l'utilise pour borner les appels et prévenir les cycles.

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from core.task_state import TaskState


@dataclass
class SubtaskRecord:
    task_id: str
    parent_task_id: str
    agent: str
    description: str
    status: str = "running"
    dependencies: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)


class MultiAgentCoordinator:
    """État de coordination isolé à une seule mission utilisateur."""

    def __init__(self, *, max_delegations: int = 8, max_depth: int = 3) -> None:
        self.max_delegations = max(1, max_delegations)
        self.max_depth = max(1, max_depth)
        self.records: dict[str, SubtaskRecord] = {}

    def begin(
        self,
        parent: TaskState,
        agent: str,
        description: str,
        stack: tuple[tuple[str, str], ...],
    ) -> SubtaskRecord:
        if len(self.records) >= self.max_delegations:
            raise RuntimeError("La limite de délégations de cette mission est atteinte.")
        if parent.delegation_depth >= self.max_depth:
            raise RuntimeError("La profondeur maximale de délégation est atteinte.")
        signature = (agent, " ".join(description.casefold().split()))
        if signature in stack:
            raise RuntimeError("Cycle de délégation détecté pour cette même sous-mission.")
        record = SubtaskRecord(
            task_id=uuid4().hex,
            parent_task_id=parent.task_id,
            agent=agent,
            description=description,
            dependencies=list(parent.child_task_ids[-1:]),
        )
        self.records[record.task_id] = record
        parent.child_task_ids.append(record.task_id)
        parent.agent_history.append(agent)
        return record

    def complete(self, task_id: str, result: dict) -> None:
        record = self.records[task_id]
        record.status = str(result.get("status", "completed"))
        record.result = result

    def fail(self, task_id: str, message: str) -> None:
        record = self.records[task_id]
        record.status = "failed"
        record.result = {"status": "failed", "errors": [message]}

    def snapshot(self) -> list[dict]:
        return [
            {
                "task_id": item.task_id,
                "parent_task_id": item.parent_task_id,
                "agent": item.agent,
                "description": item.description,
                "status": item.status,
                "dependencies": list(item.dependencies),
                "result": item.result,
            }
            for item in self.records.values()
        ]
