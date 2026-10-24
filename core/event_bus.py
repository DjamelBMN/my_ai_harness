# RÔLE DE CE FICHIER :
# Adaptateur et bus d'événements normalisés pour l'interface agentique NeoHarness AI.
# Traduit les HarnessEvent existants en événements normalisés temps réel (SSE / Inspector /
# Developer Mode) sans altérer EventTranslator ni exposer de chaîne de pensée privée.

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import queue
import threading
from time import monotonic
from typing import Any, Callable
import uuid

from core.events import EventTranslator, HarnessEvent


NORMALIZED_EVENT_TYPES = (
    "TASK_STARTED",
    "PLANNER_STARTED",
    "PLAN_CREATED",
    "SKILL_DISCOVERY",
    "SKILL_SELECTED",
    "CONTEXT_LOADING",
    "MEMORY_RETRIEVAL",
    "RAG_SEARCH",
    "MODEL_SELECTED",
    "TOOL_CALL",
    "TOOL_RESULT",
    "AGENT_STEP",
    "REVIEW",
    "VERIFIER",
    "ERROR",
    "RETRY",
    "REPLAN",
    "APPROVAL_REQUIRED",
    "ARTIFACT_READY",
    "STREAM_DELTA",
    "TASK_COMPLETED",
    "MODE_CHANGED",
)


@dataclass
class NormalizedEvent:
    id: str
    task_id: str
    event: str
    raw_event: str
    timestamp: str
    summary: str
    agent: str = ""
    skill: str = ""
    tool: str = ""
    provider: str = ""
    model: str = ""
    status: str = "info"
    duration_ms: int = 0
    retry: int = 0
    error: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NormalizedEventBus:
    """Collecte, normalise et diffuse en temps réel les événements réels du Harness."""

    def __init__(
        self,
        *,
        max_history: int = 500,
        forward_sink: Callable[[HarnessEvent], None] | None = None,
    ) -> None:
        self.max_history = max_history
        self.forward_sink = forward_sink
        self.translator = EventTranslator()
        self._lock = threading.Lock()
        self._history: list[NormalizedEvent] = []
        self._subscribers: list[queue.Queue[dict[str, Any]]] = []
        self._active_task_id: str = ""
        self._active_agent: str = ""
        self._active_skill: str = ""
        self._active_provider: str = ""
        self._active_model: str = ""
        self._step_started_at: float = monotonic()
        self._tool_started_at: dict[str, float] = {}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _sanitize_details(data: dict[str, Any]) -> dict[str, Any]:
        """Supprime tout champ susceptible de contenir une continuation ou pensée interne."""
        forbidden = {"continuation", "thought", "thought_signature", "api_key", "secret"}
        cleaned: dict[str, Any] = {}
        for key, value in data.items():
            if key.casefold() in forbidden:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                cleaned[key] = value
            elif isinstance(value, (list, tuple)):
                cleaned[key] = [str(item)[:300] for item in value[:20]]
            elif isinstance(value, dict):
                cleaned[key] = {
                    str(k): str(v)[:300]
                    for k, v in value.items()
                    if str(k).casefold() not in forbidden
                }
            else:
                cleaned[key] = str(value)[:300]
        return cleaned

    def start_task(
        self,
        *,
        task_id: str | None = None,
        objective: str = "",
        skill: str = "",
        mode: str = "",
    ) -> str:
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._active_task_id = tid
            self._active_skill = skill
            self._step_started_at = monotonic()
        self.emit_normalized(
            event="TASK_STARTED",
            raw_event="task.started",
            summary=f"Tâche démarrée : {objective[:120]}",
            skill=skill,
            status="running",
            details={"objective": objective[:500], "mode": mode},
        )
        return tid

    def complete_task(
        self,
        *,
        status: str = "completed",
        duration_ms: int = 0,
        summary: str = "Tâche terminée.",
        error: str = "",
        details: dict[str, Any] | None = None,
    ) -> NormalizedEvent:
        return self.emit_normalized(
            event="TASK_COMPLETED" if status != "error" else "ERROR",
            raw_event="task.completed",
            summary=summary,
            status=status,
            duration_ms=duration_ms,
            error=error,
            details=details or {},
        )

    def handle_harness_event(self, event: HarnessEvent) -> NormalizedEvent:
        """Convertit un HarnessEvent natif en NormalizedEvent sans perte d'information."""
        if self.forward_sink is not None:
            try:
                self.forward_sink(event)
            except Exception:
                pass

        name = event.name
        data = dict(event.data or {})
        now_mono = monotonic()

        norm_type = "AGENT_STEP"
        status = "running"
        tool_name = str(data.get("tool", ""))
        error_text = ""
        retry_count = int(data.get("retry", 0) or 0)
        duration_ms = int(data.get("duration_ms", 0) or 0)

        with self._lock:
            if data.get("agent"):
                self._active_agent = str(data["agent"])
            if data.get("skill"):
                self._active_skill = str(data["skill"])
            if data.get("provider"):
                self._active_provider = str(data["provider"])
            if data.get("model"):
                self._active_model = str(data["model"])

            agent = str(data.get("agent") or self._active_agent)
            skill = str(data.get("skill") or self._active_skill)
            provider = str(data.get("provider") or self._active_provider)
            model = str(data.get("model") or self._active_model)

        if name == "mode.changed":
            norm_type = "MODE_CHANGED"
            status = "completed"
        elif name == "skill.loaded":
            norm_type = "SKILL_SELECTED"
            status = "completed"
        elif name == "agent.started":
            norm_type = "AGENT_STEP"
            status = "running"
            self._step_started_at = now_mono
        elif name == "agent.thinking":
            norm_type = "AGENT_STEP"
            status = "running"
        elif name == "provider.started":
            norm_type = "MODEL_SELECTED"
            status = "running"
            self._step_started_at = now_mono
        elif name == "provider.error":
            norm_type = "ERROR"
            status = "error"
            error_text = str(data.get("category") or data.get("reason") or "provider_error")
            duration_ms = int((now_mono - self._step_started_at) * 1000)
        elif name == "tool.started":
            norm_type = "TOOL_CALL"
            status = "running"
            if tool_name:
                self._tool_started_at[tool_name] = now_mono
        elif name == "tool.completed":
            norm_type = "TOOL_RESULT"
            raw_status = str(data.get("status", "success"))
            status = "completed" if raw_status in {"success", "ok"} else raw_status
            if raw_status in {"error", "denied"}:
                error_text = raw_status
            started = self._tool_started_at.pop(tool_name, self._step_started_at)
            duration_ms = int((now_mono - started) * 1000)
        elif name == "delegation.started":
            target = str(data.get("agent", ""))
            norm_type = "REVIEW" if "review" in target.casefold() else "AGENT_STEP"
            status = "running"
            self._step_started_at = now_mono
        elif name == "delegation.completed":
            target = str(data.get("agent", ""))
            norm_type = "REVIEW" if "review" in target.casefold() else "AGENT_STEP"
            status = str(data.get("status", "completed"))
            duration_ms = int((now_mono - self._step_started_at) * 1000)
        elif name in {"verification.started", "verification.completed"}:
            norm_type = "VERIFIER"
            status = "running" if name.endswith(".started") else str(data.get("status", "completed"))
            if name.endswith(".completed"):
                duration_ms = int((now_mono - self._step_started_at) * 1000)
            else:
                self._step_started_at = now_mono
        elif name == "delivery.started":
            norm_type = "AGENT_STEP"
            status = "running"
        elif name == "delivery.completed":
            norm_type = "TASK_COMPLETED"
            status = "partial" if data.get("partial") else "completed"
        elif name == "delivery.failed":
            norm_type = "ERROR"
            status = "error"
            error_text = str(data.get("reason") or "delivery_failed")
        elif name == "provider.stream_delta":
            delta = str(data.get("delta") or "")
            accumulated = str(data.get("accumulated") or "")
            return self.emit_stream_delta(
                delta=delta,
                accumulated=accumulated,
                provider=provider,
                model=model,
            )

        translated = self.translator.translate(event) or name
        summary = " | ".join(line.strip() for line in translated.splitlines() if line.strip())

        return self.emit_normalized(
            event=norm_type,
            raw_event=name,
            summary=summary,
            agent=agent,
            skill=skill,
            tool=tool_name,
            provider=provider,
            model=model,
            status=status,
            duration_ms=duration_ms,
            retry=retry_count,
            error=error_text,
            details=data,
        )

    def emit_normalized(
        self,
        *,
        event: str,
        raw_event: str = "",
        summary: str = "",
        agent: str = "",
        skill: str = "",
        tool: str = "",
        provider: str = "",
        model: str = "",
        status: str = "info",
        duration_ms: int = 0,
        retry: int = 0,
        error: str = "",
        details: dict[str, Any] | None = None,
    ) -> NormalizedEvent:
        with self._lock:
            task_id = self._active_task_id or "session"
            item = NormalizedEvent(
                id=f"evt-{uuid.uuid4().hex[:10]}",
                task_id=task_id,
                event=event if event in NORMALIZED_EVENT_TYPES else "AGENT_STEP",
                raw_event=raw_event or event.lower(),
                timestamp=self._now_iso(),
                summary=summary or event,
                agent=agent or self._active_agent,
                skill=skill or self._active_skill,
                tool=tool,
                provider=provider or self._active_provider,
                model=model or self._active_model,
                status=status,
                duration_ms=max(0, int(duration_ms)),
                retry=max(0, int(retry)),
                error=error,
                details=self._sanitize_details(details or {}),
            )
            self._history.append(item)
            if len(self._history) > self.max_history:
                self._history = self._history[-self.max_history :]
            subscribers = list(self._subscribers)

        payload = item.to_dict()
        for sub in subscribers:
            try:
                sub.put_nowait(payload)
            except queue.Full:
                pass
        return item

    def emit_stream_delta(
        self,
        *,
        delta: str,
        accumulated: str = "",
        provider: str = "",
        model: str = "",
    ) -> NormalizedEvent:
        """Diffuse un fragment de texte réel en temps réel aux abonnés SSE sans saturer l'historique."""
        with self._lock:
            task_id = self._active_task_id or "session"
            item = NormalizedEvent(
                id=f"evt-{uuid.uuid4().hex[:10]}",
                task_id=task_id,
                event="STREAM_DELTA",
                raw_event="provider.stream_delta",
                timestamp=self._now_iso(),
                summary=delta[:120],
                agent=self._active_agent,
                skill=self._active_skill,
                provider=provider or self._active_provider,
                model=model or self._active_model,
                status="streaming",
                details={"delta": delta, "accumulated": accumulated[:16000]},
            )
            subscribers = list(self._subscribers)
        payload = item.to_dict()
        for sub in subscribers:
            try:
                sub.put_nowait(payload)
            except queue.Full:
                pass
        return item

    def list_events(self, *, task_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._history)
        if task_id:
            items = [item for item in items if item.task_id == task_id]
        return [item.to_dict() for item in items[-limit:]]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def subscribe(self) -> queue.Queue[dict[str, Any]]:
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=250)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict[str, Any]]) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
