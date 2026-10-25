from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.events import HarnessEvent


@dataclass
class MissionMetricsRecord:
    task_id: str
    objective: str
    status: str
    start_time: float
    end_time: float = 0.0
    duration_seconds: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    delegation_depth: int = 0
    verification_passed: bool = False
    user_cost_approx_usd: float = 0.0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_jsonl(self) -> str:
        data = asdict(self)
        return json.dumps(data, ensure_ascii=False)


class JSONLMissionMetricsSink:
    """Collecteur d'observabilité agentique branché sur HarnessEvent.
    
    Enregistre les métriques déterministes de chaque mission dans un fichier JSONL.
    """

    def __init__(self, log_path: str | Path = "workspace/.harness/metrics.jsonl", chained_sink: Callable[[HarnessEvent], None] | None = None) -> None:
        self.log_path = Path(log_path)
        self.chained_sink = chained_sink
        self.active_missions: dict[str, MissionMetricsRecord] = {}

    def handle_event(self, event: HarnessEvent) -> None:
        """Traite les événements émis par l'AgentLoop."""
        name = event.name
        data = event.data or {}

        # 1. Début de tâche
        if name in {"agent.started", "task.started"}:
            task_id = str(data.get("task_id") or f"task-{int(time.time()*1000)}")
            if task_id not in self.active_missions:
                self.active_missions[task_id] = MissionMetricsRecord(
                    task_id=task_id,
                    objective=str(data.get("objective") or data.get("skill") or ""),
                    status="running",
                    start_time=time.monotonic(),
                    metadata={"agent": data.get("agent"), "mode": data.get("mode")},
                )

        # 2. Appels d'outils
        elif name == "tool.completed":
            task_id = self._get_or_last_task(data)
            if task_id and task_id in self.active_missions:
                self.active_missions[task_id].tool_calls_count += 1

        # 3. Délégation multi-agents
        elif name == "delegation.completed":
            task_id = self._get_or_last_task(data)
            if task_id and task_id in self.active_missions:
                self.active_missions[task_id].delegation_depth += 1

        # 4. Vérification
        elif name == "verification.completed":
            task_id = self._get_or_last_task(data)
            if task_id and task_id in self.active_missions:
                status = str(data.get("status", "")).casefold()
                self.active_missions[task_id].verification_passed = (status == "passed")

        # 5. Fin de livraison ou échec
        elif name in {"delivery.completed", "delivery.failed"}:
            task_id = self._get_or_last_task(data)
            if task_id and task_id in self.active_missions:
                rec = self.active_missions[task_id]
                rec.end_time = time.monotonic()
                rec.duration_seconds = round(rec.end_time - rec.start_time, 3)
                rec.status = "success" if name == "delivery.completed" else "failed"
                # Approximation du coût (ex. standard 1$/MTok)
                rec.total_tokens = rec.tokens_in + rec.tokens_out
                rec.user_cost_approx_usd = round((rec.total_tokens / 1_000_000) * 1.5, 6)
                self._persist(rec)
                self.active_missions.pop(task_id, None)

        # Chaine vers le sink parent si configuré
        if self.chained_sink is not None:
            try:
                self.chained_sink(event)
            except Exception:
                pass

    def _get_or_last_task(self, data: dict[str, Any]) -> str | None:
        if data.get("task_id"):
            return str(data["task_id"])
        if self.active_missions:
            return next(reversed(self.active_missions.keys()))
        return None

    def _persist(self, record: MissionMetricsRecord) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(record.to_jsonl() + "\n")
        except Exception:
            pass
