# RÔLE DE CE FICHIER :
# Couche centrale (Tool Gateway) contrôlant l'accès de l'agent à toutes ses
# capacités (filesystem, terminal, computer_use, windows, process, clipboard,
# browser, git, documents, mcp).
# Assure le passage obligatoire par le PolicyEngine, le HITL et la journalisation
# d'observabilité horodatée (.harness/operator_audit.jsonl).

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from core.policy_engine import PolicyEngine, PolicyEvaluation

if TYPE_CHECKING:
    from tools.registry import Tool, ToolCall, ToolExecution, ToolRegistry


@dataclass
class GatewayTraceEntry:
    """Entrée d'observabilité structurée pour chaque action passant par le Tool Gateway."""

    timestamp: str
    time_short: str
    step_type: str  # "AGENT_CALL" | "POLICY" | "HITL" | "EXECUTION" | "VERIFICATION"
    tool: str
    category: str
    message: str
    risk_label: str = ""
    status: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def format_line(self) -> str:
        return f"{self.time_short}\n{self.message}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolGateway:
    """Point d'entrée unique et contrôlé entre l'Agent et les capacités système Windows."""

    NAMESPACES: tuple[str, ...] = (
        "filesystem",
        "terminal",
        "computer_use",
        "windows",
        "process",
        "clipboard",
        "browser",
        "git",
        "search",
        "documents",
        "mcp",
    )

    def __init__(
        self,
        registry: "ToolRegistry",
        policy_engine: PolicyEngine | None = None,
        *,
        audit_log_path: Path | None = None,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.registry = registry
        self.policy_engine = policy_engine or self.registry.permissions._get_policy_engine()
        self.registry.permissions.policy_engine = self.policy_engine
        self.event_callback = event_callback
        self._lock = threading.Lock()
        self._traces: list[GatewayTraceEntry] = []
        if audit_log_path is not None:
            self.audit_log_path = audit_log_path
        else:
            root = getattr(getattr(registry, "filesystem", None), "root", Path("workspace"))
            self.audit_log_path = Path(root) / ".harness" / "operator_audit.jsonl"

    @staticmethod
    def _now() -> tuple[str, str]:
        now = datetime.now(timezone.utc).astimezone()
        return now.isoformat(), now.strftime("%H:%M:%S")

    def _record_trace(
        self,
        step_type: str,
        tool: str,
        category: str,
        message: str,
        *,
        risk_label: str = "",
        status: str = "",
        details: dict[str, Any] | None = None,
    ) -> GatewayTraceEntry:
        iso_ts, short_ts = self._now()
        entry = GatewayTraceEntry(
            timestamp=iso_ts,
            time_short=short_ts,
            step_type=step_type,
            tool=tool,
            category=category,
            message=message,
            risk_label=risk_label,
            status=status,
            details=details or {},
        )
        with self._lock:
            self._traces.append(entry)
            self._traces[:] = self._traces[-1000:]
            try:
                self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.audit_log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry.to_dict(), ensure_ascii=False, default=str) + "\n")
            except Exception:
                pass
        if self.event_callback is not None:
            try:
                self.event_callback(f"gateway.{step_type.lower()}", entry.to_dict())
            except Exception:
                pass
        return entry

    def evaluate_call(self, call: "ToolCall") -> PolicyEvaluation:
        """Évalue un appel d'outil via le PolicyEngine avant son exécution."""
        try:
            tool = self.registry.get(call.name)
            default_risk = tool.risk_level
            mutates = tool.mutates
        except ValueError:
            from core.permissions import RiskLevel

            default_risk = RiskLevel.MODERATE
            mutates = True
        return self.policy_engine.evaluate(
            call.name,
            call.arguments if isinstance(call.arguments, dict) else {},
            default_risk=default_risk,
            mutates=mutates,
        )

    def record_pre_execution(self, call: "ToolCall", evaluation: PolicyEvaluation) -> None:
        args_repr = ", ".join(
            f"{k}={v!r}" for k, v in list((call.arguments or {}).items())[:4]
        )
        self._record_trace(
            "AGENT_CALL",
            call.name,
            evaluation.category,
            f"Agent → {evaluation.canonical_action}({args_repr})",
            risk_label=evaluation.risk_label,
            status="requested",
            details={"arguments": call.arguments, "description": evaluation.human_description},
        )
        self._record_trace(
            "POLICY",
            call.name,
            evaluation.category,
            f"Policy → {evaluation.risk_label} RISK ({evaluation.human_description})",
            risk_label=evaluation.risk_label,
            status="blocked" if evaluation.blocked else "evaluated",
            details=evaluation.to_dict(),
        )

    def record_hitl_decision(
        self,
        call: "ToolCall",
        evaluation: PolicyEvaluation,
        allowed: bool,
        reason: str,
    ) -> None:
        label = "AUTORISÉ" if allowed else "REFUSÉ"
        self._record_trace(
            "HITL",
            call.name,
            evaluation.category,
            f"HITL → {label} ({reason})",
            risk_label=evaluation.risk_label,
            status="approved" if allowed else "denied",
            details={"allowed": allowed, "reason": reason},
        )

    def record_post_execution(
        self,
        call: "ToolCall",
        evaluation: PolicyEvaluation,
        execution: "ToolExecution",
    ) -> None:
        verif_passed = execution.status == "success"
        if isinstance(execution.data, dict) and "verified" in execution.data:
            verif_passed = bool(execution.data.get("verified"))
        verif_label = "SUCCESS" if verif_passed else execution.status.upper()
        self._record_trace(
            "VERIFICATION",
            call.name,
            evaluation.category,
            f"Verification → {verif_label} ({execution.summary})",
            risk_label=evaluation.risk_label,
            status=execution.status,
            details={
                "elapsed_seconds": execution.elapsed_seconds,
                "status": execution.status,
                "verified": verif_passed,
            },
        )

    def execute(self, call: "ToolCall") -> "ToolExecution":
        """Exécute un ToolCall en passant par la chaîne complète du ToolGateway."""
        return self.registry.execute(call)

    def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [entry.to_dict() for entry in self._traces[-limit:]]

    def format_timeline(self, limit: int = 50) -> str:
        with self._lock:
            selected = list(self._traces[-limit:])
        return "\n\n".join(entry.format_line() for entry in selected)

    def list_tools_by_namespace(self) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {ns: [] for ns in self.NAMESPACES}
        for tool in self.registry.discover():
            ev = self.policy_engine.evaluate(
                tool.name,
                {},
                default_risk=tool.risk_level,
                mutates=tool.mutates,
            )
            prefix = ev.canonical_action.split(".")[0]
            target_ns = prefix if prefix in grouped else "filesystem"
            grouped[target_ns].append(tool.name)
        return grouped