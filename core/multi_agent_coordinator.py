# RÔLE DE CE FICHIER :
# Gère la coordination hiérarchique multi-agents industrielle (Manager -> Workers -> Critic).
# Garantit le protocole de communication typé, l'isolation stricte des contextes,
# la prévention des cycles et la profondeur maximale de délégation.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Callable
from uuid import uuid4

from core.task_state import TaskState


class DelegationError(RuntimeError):
    """Erreur générique du protocole de délégation multi-agents."""


class CyclicDelegationError(DelegationError):
    """Cycle de délégation détecté dans l'arbre d'exécution."""


class MaxDepthExceededError(DelegationError):
    """Profondeur maximale de délégation dépassée."""


@dataclass
class SubtaskRecord:
    task_id: str
    parent_task_id: str
    agent: str
    description: str
    status: str = "running"
    dependencies: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocole de communication structuré et typé
# ---------------------------------------------------------------------------

@dataclass
class TaskAssignment:
    """Affectation typée d'une sous-tâche émise par le Manager vers un Worker."""

    task_id: str
    parent_task_id: str
    assigned_to: str
    instructions: str
    input_artifacts: list[dict[str, str]] = field(default_factory=list)
    timeout_seconds: float = 60.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskProgress:
    """Notification typée d'avancement d'un Worker."""

    task_id: str
    step_index: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskCompletion:
    """Résultat typé et vérifiable produit par un Worker."""

    task_id: str
    status: str  # "success" | "failed"
    output_artifacts: list[dict[str, str]] = field(default_factory=list)
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CritiqueRequest:
    """Demande d'évaluation indépendante émise vers le Critic."""

    mission_id: str
    deliverable_summary: str
    artifacts: list[dict[str, str]] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CritiqueVerdict:
    """Verdict structuré du Critic avec droit de veto motivé."""

    decision: str  # "APPROVE" | "REJECT"
    defects: list[str] = field(default_factory=list)
    confidence: float = 1.0
    remediation_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Coordinateur multi-agents
# ---------------------------------------------------------------------------

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
            raise MaxDepthExceededError(
                f"La profondeur maximale de délégation ({self.max_depth}) est atteinte."
            )

        # Détection de cycle direct et indirect dans la chaîne d'appel
        active_agents = [caller_agent for caller_agent, _ in stack]
        if agent in active_agents:
            raise CyclicDelegationError(
                f"Cycle de délégation détecté : l'agent '{agent}' est déjà actif dans la chaîne d'appel {active_agents}."
            )

        signature = (agent, " ".join(description.casefold().split()))
        if signature in stack:
            raise CyclicDelegationError("Cycle de délégation détecté pour cette même sous-mission.")

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


# ---------------------------------------------------------------------------
# Moteur hiérarchique Manager -> Workers -> Critic
# ---------------------------------------------------------------------------

class HierarchicalCoordinator:
    """Orchestre la hiérarchie stricte Manager / Workers / Critic avec isolation et boucles de remédiation."""

    def __init__(self, *, max_depth: int = 3, global_timeout: float = 300.0) -> None:
        self.max_depth = max_depth
        self.global_timeout = global_timeout
        self.coordinator = MultiAgentCoordinator(max_depth=max_depth)

    @staticmethod
    def create_isolated_worker_context(
        assignment: TaskAssignment,
    ) -> dict[str, Any]:
        """Crée un contexte isolé au principe du moindre privilège pour un worker.

        Le worker ne reçoit QUE ses instructions et les artefacts explicitement transmis.
        Aucune donnée privée ni historique interne d'autres workers n'est divulgué.
        """
        return {
            "task_id": assignment.task_id,
            "instructions": assignment.instructions,
            "input_artifacts": [dict(a) for a in assignment.input_artifacts],
            "allowed_timeout": assignment.timeout_seconds,
        }

    def execute_hierarchy(
        self,
        manager_id: str,
        assignments: list[TaskAssignment],
        worker_executors: dict[str, Callable[[dict[str, Any]], TaskCompletion]],
        critic_evaluator: Callable[[CritiqueRequest], CritiqueVerdict],
        requirements: list[str],
        max_remediation_rounds: int = 2,
    ) -> dict[str, Any]:
        """Exécute la chaîne hiérarchique complète avec droit de veto du Critic."""
        start_time = time.monotonic()
        all_completions: list[TaskCompletion] = []
        artifacts_pool: list[dict[str, str]] = []

        # 1. Exécution des Workers isolés
        for assignment in assignments:
            if time.monotonic() - start_time > self.global_timeout:
                raise TimeoutError("Timeout global de la mission multi-agents dépassé.")

            executor = worker_executors.get(assignment.assigned_to)
            if executor is None:
                raise ValueError(f"Aucun exécuteur trouvé pour le worker : {assignment.assigned_to}")

            # Contexte strictement isolé
            worker_ctx = self.create_isolated_worker_context(assignment)
            completion = executor(worker_ctx)
            all_completions.append(completion)

            if completion.status == "success":
                artifacts_pool.extend(completion.output_artifacts)
            else:
                return {
                    "status": "failed",
                    "stage": "worker_execution",
                    "failed_worker": assignment.assigned_to,
                    "summary": f"Échec du worker {assignment.assigned_to}: {completion.summary}",
                    "completions": [c.to_dict() for c in all_completions],
                }

        # 2. Phase de Critique avec boucles de remédiation
        current_summary = "\n".join(c.summary for c in all_completions)
        remediation_round = 0
        final_verdict = None

        while remediation_round <= max_remediation_rounds:
            critique_req = CritiqueRequest(
                mission_id=manager_id,
                deliverable_summary=current_summary,
                artifacts=artifacts_pool,
                requirements=requirements,
            )
            verdict = critic_evaluator(critique_req)
            final_verdict = verdict

            if verdict.decision == "APPROVE":
                return {
                    "status": "success",
                    "verdict": verdict.to_dict(),
                    "artifacts": artifacts_pool,
                    "summary": current_summary,
                    "remediation_rounds": remediation_round,
                }

            # En cas de REJECT par le Critic : tentative de remédiation
            remediation_round += 1
            if remediation_round > max_remediation_rounds:
                break

            # Réassignation au dernier worker avec le feedback structuré du Critic
            last_assignment = assignments[-1]
            remediation_instructions = (
                f"{last_assignment.instructions}\n"
                f"CORRECTIONS EXIGÉES PAR LE CRITIC :\n"
                + "\n".join(f"- {d}" for d in verdict.defects)
            )
            remediation_assignment = TaskAssignment(
                task_id=f"{last_assignment.task_id}_rem_{remediation_round}",
                parent_task_id=manager_id,
                assigned_to=last_assignment.assigned_to,
                instructions=remediation_instructions,
                input_artifacts=artifacts_pool,
            )
            executor = worker_executors[last_assignment.assigned_to]
            new_completion = executor(self.create_isolated_worker_context(remediation_assignment))
            all_completions.append(new_completion)
            if new_completion.status == "success":
                artifacts_pool.extend(new_completion.output_artifacts)
                current_summary = f"{current_summary}\n[Remédiation] {new_completion.summary}"

        return {
            "status": "rejected",
            "verdict": final_verdict.to_dict() if final_verdict else {},
            "artifacts": artifacts_pool,
            "summary": current_summary,
            "remediation_rounds": remediation_round,
        }
