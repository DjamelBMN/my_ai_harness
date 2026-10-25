# RÔLE DE CE FICHIER :
# Moteur d'orchestration asynchrone en graphe (DAG) multi-agents.
# Permet l'exécution hautement concurrente des sous-tâches indépendantes,
# l'isolation stricte des contextes, la résolution topologique des dépendances,
# la détection de cycles et l'arbitrage avec remédiation ciblée par le Critic.

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from enum import Enum
import time
from typing import Any, Callable

from core.multi_agent_coordinator import CritiqueRequest, CritiqueVerdict


class NodeStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class DAGError(RuntimeError):
    """Erreur générique du graphe de tâches."""


class InvalidDAGError(DAGError):
    """Structure du DAG invalide (dépendance inexistante, configuration incorrecte)."""


class CyclicDAGError(DAGError):
    """Cycle ou interblocage détecté dans le graphe orienté."""


@dataclass
class DAGNode:
    """Nœud unitaire d'un graphe de tâches multi-agents."""

    id: str
    agent: str
    title: str = ""
    prompt: str = ""
    dependencies: list[str] = field(default_factory=list)
    input_artifacts: list[dict[str, Any]] = field(default_factory=list)
    timeout_seconds: float = 60.0
    status: NodeStatus = NodeStatus.PENDING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TaskDAG:
    """Graphe orienté acyclique représentant une mission multi-agents décomposée."""

    mission_id: str
    requirements: list[str] = field(default_factory=list)
    nodes: dict[str, DAGNode] = field(default_factory=dict)

    def add_node(self, node: DAGNode) -> None:
        if node.id in self.nodes:
            raise InvalidDAGError(f"Le nœud '{node.id}' existe déjà dans le graphe.")
        self.nodes[node.id] = node

    def topological_sort(self) -> list[str]:
        """Calcule l'ordonnancement topologique (Algorithme de Kahn) et détecte les cycles."""
        # 1. Vérification de l'existence de toutes les dépendances
        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise InvalidDAGError(
                        f"Le nœud '{nid}' dépend du nœud inconnu '{dep}'."
                    )

        # 2. Calcul des degrés entrants
        in_degree: dict[str, int] = {nid: len(node.dependencies) for nid, node in self.nodes.items()}
        # Adjacence : qui dépend de ce nœud
        dependents: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for nid, node in self.nodes.items():
            for dep in node.dependencies:
                dependents[dep].append(nid)

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        sorted_nodes: list[str] = []

        while queue:
            curr = queue.pop(0)
            sorted_nodes.append(curr)
            for nxt in dependents[curr]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(sorted_nodes) != len(self.nodes):
            unresolved = [nid for nid, deg in in_degree.items() if deg > 0]
            raise CyclicDAGError(
                f"Cycle ou dépendance circulaire détecté impliquant les nœuds : {unresolved}"
            )

        return sorted_nodes

    def get_ready_nodes(self) -> list[DAGNode]:
        """Retourne tous les nœuds dont toutes les dépendances sont au statut COMPLETED."""
        ready: list[DAGNode] = []
        for node in self.nodes.values():
            if node.status == NodeStatus.PENDING:
                all_deps_completed = all(
                    self.nodes[dep].status == NodeStatus.COMPLETED
                    for dep in node.dependencies
                )
                if all_deps_completed:
                    ready.append(node)
        return ready

    def propagate_blocking(self) -> None:
        """Marque en BLOCKED tout nœud dont au moins un parent a échoué ou est bloqué."""
        changed = True
        while changed:
            changed = False
            for node in self.nodes.values():
                if node.status == NodeStatus.PENDING:
                    has_failed_dep = any(
                        self.nodes[dep].status in (NodeStatus.FAILED, NodeStatus.BLOCKED, NodeStatus.SKIPPED)
                        for dep in node.dependencies
                    )
                    if has_failed_dep:
                        node.status = NodeStatus.BLOCKED
                        node.error = "Dépendance amont défaillante ou bloquée."
                        changed = True

    def is_finished(self) -> bool:
        """Vérifie si tous les nœuds ont atteint un état terminal."""
        terminal_states = {
            NodeStatus.COMPLETED,
            NodeStatus.FAILED,
            NodeStatus.BLOCKED,
            NodeStatus.SKIPPED,
        }
        return all(node.status in terminal_states for node in self.nodes.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "requirements": list(self.requirements),
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
        }


class AsyncDAGEngine:
    """Moteur d'exécution asynchrone hautement concurrent pour graphes multi-agents."""

    def __init__(
        self,
        *,
        max_workers: int = 4,
        global_timeout: float = 300.0,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.max_workers = max(1, max_workers)
        self.global_timeout = global_timeout
        self.event_sink = event_sink

    def _emit(self, event_name: str, payload: dict[str, Any]) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink(event_name, payload)
            except Exception:
                pass

    def execute_dag(
        self,
        dag: TaskDAG,
        worker_executors: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        critic_evaluator: Callable[[CritiqueRequest], CritiqueVerdict] | None = None,
        max_remediation_rounds: int = 2,
    ) -> dict[str, Any]:
        """Exécute l'intégralité du DAG en vagues asynchrones parallèles."""
        # 1. Validation de la cohérence et détection précoce de cycles
        dag.topological_sort()

        start_time = time.monotonic()
        self._emit(
            "dag.started",
            {
                "mission_id": dag.mission_id,
                "total_nodes": len(dag.nodes),
                "requirements": dag.requirements,
            },
        )

        running_futures: dict[Future, str] = {}
        all_artifacts: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not dag.is_finished() or running_futures:
                # Vérification du timeout global
                if time.monotonic() - start_time > self.global_timeout:
                    # Annuler les tâches en cours
                    for f in running_futures:
                        f.cancel()
                    raise TimeoutError(f"Timeout global ({self.global_timeout}s) dépassé pour le DAG.")

                # Propagation des blocages
                dag.propagate_blocking()

                # Soumission des nouveaux nœuds prêts
                ready_nodes = dag.get_ready_nodes()
                for node in ready_nodes:
                    node.status = NodeStatus.RUNNING
                    node.started_at = time.monotonic()

                    # Agrégation des artefacts issus des parents directs
                    collected_artifacts: list[dict[str, Any]] = list(node.input_artifacts)
                    for dep_id in node.dependencies:
                        parent_res = dag.nodes[dep_id].result
                        if isinstance(parent_res, dict) and "artifacts" in parent_res:
                            collected_artifacts.extend(parent_res["artifacts"])

                    # Contexte strictement isolé selon le principe du moindre privilège
                    worker_context = {
                        "id": node.id,
                        "agent": node.agent,
                        "title": node.title,
                        "prompt": node.prompt,
                        "input_artifacts": collected_artifacts,
                        "timeout_seconds": node.timeout_seconds,
                    }

                    worker_fn = worker_executors.get(node.agent)
                    if worker_fn is None:
                        node.status = NodeStatus.FAILED
                        node.error = f"Aucun exécuteur trouvé pour l'agent : {node.agent}"
                        dag.propagate_blocking()
                        continue

                    self._emit(
                        "dag.node_started",
                        {
                            "mission_id": dag.mission_id,
                            "node_id": node.id,
                            "agent": node.agent,
                            "title": node.title,
                        },
                    )

                    future = executor.submit(worker_fn, worker_context)
                    running_futures[future] = node.id

                if not running_futures:
                    # Si aucune tâche ne tourne et que le DAG n'est pas fini, il y a blocage
                    if not dag.is_finished():
                        dag.propagate_blocking()
                    break

                # Attendre qu'au moins une tâche termine
                done, _ = wait(running_futures.keys(), timeout=0.1, return_when=FIRST_COMPLETED)

                for fut in done:
                    node_id = running_futures.pop(fut)
                    node = dag.nodes[node_id]
                    node.completed_at = time.monotonic()
                    duration = round(node.completed_at - node.started_at, 3)

                    try:
                        res = fut.result()
                        if not isinstance(res, dict):
                            res = {"status": "success", "summary": str(res)}
                        node.result = res
                        if res.get("status") in ("failed", "error"):
                            node.status = NodeStatus.FAILED
                            node.error = str(res.get("error") or res.get("summary") or "Échec de l'agent")
                        else:
                            node.status = NodeStatus.COMPLETED
                            if "artifacts" in res and isinstance(res["artifacts"], list):
                                all_artifacts.extend(res["artifacts"])
                    except Exception as exc:
                        node.status = NodeStatus.FAILED
                        node.error = str(exc)
                        node.result = {"status": "failed", "error": str(exc)}

                    self._emit(
                        "dag.node_completed",
                        {
                            "mission_id": dag.mission_id,
                            "node_id": node.id,
                            "agent": node.agent,
                            "status": node.status.value,
                            "duration": duration,
                            "summary": node.result.get("summary", ""),
                        },
                    )

                    # Dès qu'un nœud termine ou échoue, réévaluer les dépendants
                    dag.propagate_blocking()

        # Synthèse de statut global
        has_failed = any(n.status == NodeStatus.FAILED for n in dag.nodes.values())
        has_blocked = any(n.status == NodeStatus.BLOCKED for n in dag.nodes.values())
        all_completed = all(n.status == NodeStatus.COMPLETED for n in dag.nodes.values())

        overall_status = "success" if all_completed else ("partial_failure" if has_failed or has_blocked else "completed")

        # 2. Phase de Critique et Boucle de Remédiation Ciblée (si exigé)
        remediation_round = 0
        final_verdict = None

        if all_completed and critic_evaluator is not None:
            current_summary = "\n".join(
                f"[{n.agent}] {n.result.get('summary', '')}" for n in dag.nodes.values()
            )

            while remediation_round <= max_remediation_rounds:
                critique_req = CritiqueRequest(
                    mission_id=dag.mission_id,
                    deliverable_summary=current_summary,
                    artifacts=all_artifacts,
                    requirements=dag.requirements,
                )
                verdict = critic_evaluator(critique_req)
                final_verdict = verdict

                if verdict.decision == "APPROVE":
                    overall_status = "success"
                    break

                # En cas de rejet : tentative de remédiation ciblée
                remediation_round += 1
                if remediation_round > max_remediation_rounds:
                    overall_status = "rejected"
                    break

                # Trouver le dernier nœud de production (ex: coder) pour remédiation
                last_node = list(dag.nodes.values())[-1]
                rem_node_id = f"{last_node.id}_rem_{remediation_round}"
                rem_instructions = (
                    f"RÉVISION EXIGÉE PAR LE CRITIC :\n"
                    + "\n".join(f"- {d}" for d in verdict.defects)
                    + (f"\nSuggestions : {', '.join(verdict.remediation_suggestions)}" if verdict.remediation_suggestions else "")
                )
                rem_context = {
                    "id": rem_node_id,
                    "agent": last_node.agent,
                    "title": f"Remédiation {last_node.agent}",
                    "prompt": rem_instructions,
                    "input_artifacts": all_artifacts,
                    "timeout_seconds": last_node.timeout_seconds,
                }

                worker_fn = worker_executors.get(last_node.agent)
                if worker_fn is not None:
                    rem_res = worker_fn(rem_context)
                    if isinstance(rem_res, dict) and "artifacts" in rem_res:
                        all_artifacts = [
                            a for a in all_artifacts
                            if not any(na.get("uri") == a.get("uri") for na in rem_res["artifacts"])
                        ]
                        all_artifacts.extend(rem_res["artifacts"])
                    current_summary = f"{current_summary}\n[Remédiation {remediation_round}] {rem_res.get('summary', '')}"

        self._emit(
            "dag.completed",
            {
                "mission_id": dag.mission_id,
                "status": overall_status,
                "duration": round(time.monotonic() - start_time, 3),
                "artifacts_count": len(all_artifacts),
            },
        )

        return {
            "status": overall_status,
            "mission_id": dag.mission_id,
            "dag": dag.to_dict(),
            "artifacts": all_artifacts,
            "verdict": final_verdict.to_dict() if final_verdict else {},
            "remediation_rounds": remediation_round,
        }

