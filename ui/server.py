# RÔLE DE CE FICHIER :
# Pont runtime non destructif et serveur HTTP/SSE de l'interface NeoHarness AI.
# Relie l'interface web aux composants réels (Orchestrator, AgentLoop, ModelRouter,
# SkillRegistry, SkillLoader, ToolRegistry, MemoryManager, ModeManager, WorkspaceFilesystem)
# sans modifier aucun contrat existant.

from __future__ import annotations

import base64
import contextlib
import difflib
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import mimetypes
import os
from pathlib import Path
import queue
import re
import threading
from time import monotonic
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse
import uuid

from agents.coder import CodeAgent
from agents.researcher import ResearchAgent
from agents.reviewer import ReviewAgent
from agents.tester import TestAgent
from core.agent_loop import AgentLoop, AgentResult
from core.agent_registry import AgentRegistry
from core.event_bus import NormalizedEventBus
from core.events import HarnessEvent
from core.memory import MemoryManager
from core.model_registry import ModelCapabilityRegistry
from core.modes import HarnessMode, ModeManager
from core.orchestrator import Orchestrator
from core.permissions import PermissionPolicy, RiskLevel
from core.planner import ClarificationRequired, Planner
from core.router import ModelRouter, load_config
from core.skill_compatibility import SkillCompatibilityEngine
from core.task import Task
from core.task_state import PlanStep, TaskState
from core.verifier import Verifier
from providers.claude import ClaudeProvider
from providers.gemini import GeminiProvider
from providers.mistral import MistralProvider
from providers.ollama import OllamaProvider
from providers.openai import OpenAIProvider
from skills.loader import SkillLoadError, SkillLoader
from skills.registry import SkillRegistry
from skills.router import SkillCommandError, SkillRouter
from skills.runtime import SkillRuntime
from tools.documents import _verify_compiled_pdf_bytes, compile_html, compile_latex, read_document
from tools.filesystem import WORKSPACE_ROOT, WorkspaceFilesystem
from tools.registry import ToolCall, ToolRegistry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"


class NeoHarnessRuntimeBridge:
    """Pont complet et non-destructif entre le moteur NeoHarness AI et l'interface."""

    def __init__(
        self,
        *,
        workspace: str | Path = WORKSPACE_ROOT,
        config_path: str | Path = PROJECT_ROOT / "config" / "config.yaml",
        orchestrator: Orchestrator | None = None,
        agent_loop: AgentLoop | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = PROJECT_ROOT
        self.workspace_path = Path(workspace).expanduser().resolve()
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.config_path = Path(config_path).expanduser().resolve()
        self.settings = settings if settings is not None else self._safe_load_config()

        self.event_bus = NormalizedEventBus()
        self._lock = threading.RLock()

        # Gestion des approbations humaines (Human-in-the-Loop)
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._approval_events: dict[str, threading.Event] = {}
        self._task_approved_tools: set[str] = set()
        self._always_approved_tools: set[str] = set()
        self.approval_timeout_seconds: float = 120.0
        self.auto_approve_in_headless: bool = False

        # Paramètres de génération UI (appliqués uniquement si le modèle les supporte)
        self.generation_preferences: dict[str, Any] = {
            "style": "equilibre",  # precis | equilibre | creatif | avance
            "temperature": 0.4,
            "max_output_tokens": None,
            "active_skills": [],  # vide = mode [Auto]
            "skill_mode": "auto",  # auto | manual
            "developer_mode": False,
        }

        # État de la tâche courante
        self.current_task_status: str = "En attente"
        self.current_task_id: str | None = None
        self._stop_requested: bool = False

        # Diffs et modifications de fichiers suivis dans la session
        self.file_changes: list[dict[str, Any]] = []

        # Chargement automatique d'un éventuel fichier .env local
        self._load_dotenv()

        if orchestrator is not None and agent_loop is not None:
            self.orchestrator = orchestrator
            self.agent_loop = agent_loop
            self.filesystem = self.agent_loop.tools.filesystem
            self.permissions = self.agent_loop.tools.permissions
            self.tools = self.agent_loop.tools
            self.agent_loop.event_sink = self.event_bus.handle_harness_event
            self.agent_loop.stream_callback = lambda delta, acc: self.event_bus.emit_stream_delta(
                delta=delta, accumulated=acc
            )
        else:
            self._build_runtime_components()

        self.mode_manager = ModeManager(
            self.permissions,
            initial_mode=self.permissions.mode,
            on_change=lambda previous, current: self.event_bus.handle_harness_event(
                HarnessEvent(
                    "mode.changed",
                    {"previous": previous.value, "current": current.value},
                )
            ),
        )
        self.memory = MemoryManager(self.tools)
        self.model_registry = ModelCapabilityRegistry(
            router=self.orchestrator.router,
            settings=self.settings,
            config_path=self.config_path,
        )
        self.skill_compatibility = SkillCompatibilityEngine(
            skill_registry=self.orchestrator.skill_registry,
            skill_loader=self.orchestrator.skill_loader,
            model_registry=self.model_registry,
            tool_registry=self.tools,
        )

        # Persistance des conversations dans workspace/.harness/conversations.json
        self._conversations_path = self.workspace_path / ".harness" / "conversations.json"
        self.conversations: list[dict[str, Any]] = self._load_conversations()
        self.active_conversation_id: str = (
            self.conversations[0]["id"] if self.conversations else self._create_default_conversation()["id"]
        )

    def _load_dotenv(self) -> None:
        """Charge les clés API depuis .env (racine du projet) si présent."""
        dotenv_path = self.project_root / ".env"
        if not dotenv_path.is_file():
            return
        try:
            for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                key = k.strip()
                val = v.strip().strip("\"'")
                if key in {"GEMINI_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY", "ANTHROPIC_API_KEY"} and val:
                    if not os.environ.get(key, "").strip():
                        os.environ[key] = val
        except Exception:
            pass

    def get_credentials_status(self) -> dict[str, bool]:
        """Retourne uniquement la présence (booléen) des clés API sans jamais exposer de secret."""
        return {
            "GEMINI_API_KEY": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
            "OPENAI_API_KEY": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            "MISTRAL_API_KEY": bool(os.environ.get("MISTRAL_API_KEY", "").strip()),
            "ANTHROPIC_API_KEY": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        }

    def update_credentials(self, updates: dict[str, Any], *, persist_dotenv: bool = True) -> dict[str, Any]:
        """Met à jour les clés API en mémoire (et dans .env) sans jamais renvoyer les clés en clair."""
        allowed_keys = ("GEMINI_API_KEY", "OPENAI_API_KEY", "MISTRAL_API_KEY", "ANTHROPIC_API_KEY")
        changed: list[str] = []
        with self._lock:
            for key in allowed_keys:
                if key not in updates:
                    continue
                raw_val = updates.get(key)
                if raw_val is None:
                    continue
                clean_val = str(raw_val).strip()
                if clean_val:
                    os.environ[key] = clean_val
                    changed.append(key)

            if changed and persist_dotenv:
                dotenv_path = self.project_root / ".env"
                existing: dict[str, str] = {}
                if dotenv_path.is_file():
                    try:
                        for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
                            line = raw_line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                ek, _, ev = line.partition("=")
                                existing[ek.strip()] = ev.strip()
                    except Exception:
                        pass
                for k in changed:
                    existing[k] = os.environ[k]
                try:
                    lines = [f"{k}={v}" for k, v in existing.items()]
                    dotenv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
                except Exception:
                    pass

            # Réinitialise les clients providers concernés pour prise en compte immédiate
            for prov in self.orchestrator.router.providers.values():
                if isinstance(prov, GeminiProvider) and "GEMINI_API_KEY" in changed:
                    prov._client = None
                    prov._verified = False
                elif isinstance(prov, OpenAIProvider) and "OPENAI_API_KEY" in changed:
                    prov._client = None
                elif isinstance(prov, MistralProvider) and "MISTRAL_API_KEY" in changed:
                    prov._client = None
                    prov._available_models = {}

            if "GEMINI_API_KEY" in changed:
                self.select_model("gemini")
            elif "OPENAI_API_KEY" in changed:
                self.select_model("openai")
            elif "MISTRAL_API_KEY" in changed:
                self.select_model("mistral")

        return {
            "updated": changed,
            "credentials": self.get_credentials_status(),
            "selection": self.model_registry.active_selection_summary(),
        }

    def _ensure_provider_ready(self, provider: Any, *, prefer_lite: bool = False) -> None:
        """Synchronise le modèle d'un provider réel avec la liste des modèles autorisés par sa clé API."""
        if isinstance(provider, GeminiProvider) and type(provider).list_available_models is GeminiProvider.list_available_models:
            if not os.environ.get("GEMINI_API_KEY", "").strip() or provider._verified:
                return
            try:
                models = provider.list_available_models()
                model_ids = [item["model"] for item in models]
                if not model_ids:
                    return
                if provider.model in provider._available_models:
                    provider.select_model(provider.model)
                    return
                chosen = None
                if prefer_lite or (provider.model and "lite" in provider.model.casefold()):
                    for mid in model_ids:
                        if "flash-lite" in mid.casefold() or "lite" in mid.casefold():
                            chosen = mid
                            break
                if chosen is None:
                    for mid in model_ids:
                        if "flash" in mid.casefold() and "lite" not in mid.casefold():
                            chosen = mid
                            break
                if chosen is None:
                    for mid in model_ids:
                        if "flash" in mid.casefold():
                            chosen = mid
                            break
                if chosen is None:
                    chosen = model_ids[0]
                provider.select_model(chosen)
            except Exception:
                pass
        elif isinstance(provider, MistralProvider) and type(provider).list_available_models is MistralProvider.list_available_models:
            if not os.environ.get("MISTRAL_API_KEY", "").strip() or provider._available_models:
                return
            try:
                models = provider.list_available_models()
                model_ids = [item["model"] for item in models]
                if not model_ids:
                    return
                if provider.model in provider._available_models:
                    provider.select_model(provider.model)
                elif "mistral-small-latest" in provider._available_models:
                    provider.select_model("mistral-small-latest")
                else:
                    provider.select_model(model_ids[0])
            except Exception:
                pass

    def _ensure_routed_providers_ready(self) -> None:
        """Prépare les providers actifs et redirige les routes Auto non configurées vers un provider actif."""
        router = self.orchestrator.router
        for key, prov in router.providers.items():
            self._ensure_provider_ready(prov, prefer_lite=(key == "gemini_flash_lite"))

        # Détermine le meilleur provider de repli réellement utilisable
        fallback_key: str | None = None
        if os.environ.get("GEMINI_API_KEY", "").strip() and "gemini" in router.providers:
            fallback_key = "gemini"
        elif os.environ.get("OPENAI_API_KEY", "").strip() and "openai" in router.providers:
            fallback_key = "openai"
        elif os.environ.get("MISTRAL_API_KEY", "").strip() and "mistral" in router.providers:
            fallback_key = "mistral"
        elif "ollama" in router.providers:
            fallback_key = "ollama"

        if not fallback_key:
            return

        def _is_provider_usable(prov_key: str) -> bool:
            p = router.providers.get(prov_key)
            if p is None:
                return False
            # Si c'est un double/mock de test, il est toujours utilisable
            if type(p) not in (GeminiProvider, OpenAIProvider, MistralProvider, OllamaProvider, ClaudeProvider):
                return True
            if isinstance(p, GeminiProvider):
                return bool(os.environ.get("GEMINI_API_KEY", "").strip())
            if isinstance(p, OpenAIProvider):
                return bool(os.environ.get("OPENAI_API_KEY", "").strip())
            if isinstance(p, MistralProvider):
                return bool(os.environ.get("MISTRAL_API_KEY", "").strip())
            if isinstance(p, OllamaProvider):
                return True
            return False

        if not router.automatic_routing and router.session_provider_key:
            # Si l'utilisateur a épinglé un provider mais qu'il s'agit de gemini/mistral, on s'assure qu'il est prêt
            return

        # En mode automatique, si default_provider n'a pas de clé API, basculer sur fallback_key
        if not _is_provider_usable(router.default_provider):
            router.default_provider = fallback_key

        for agent_k, target_p in list(router.agent_provider_map.items()):
            if not _is_provider_usable(target_p):
                router.agent_provider_map[agent_k] = fallback_key

        for route_k, target_p in list(router.task_provider_map.items()):
            if not _is_provider_usable(target_p):
                router.task_provider_map[route_k] = (
                    "gemini_flash_lite"
                    if route_k == "simple" and fallback_key == "gemini" and "gemini_flash_lite" in router.providers
                    else fallback_key
                )

    def _safe_load_config(self) -> dict[str, Any]:
        try:
            return load_config(str(self.config_path))
        except Exception:
            return {
                "default_provider": "ollama",
                "providers": {
                    "ollama": {"model": "qwen3:1.7b", "enabled": True},
                    "openai": {"model": "gpt-5-mini", "enabled": True},
                    "gemini": {"model": "gemini-3.8-flash", "enabled": True},
                    "mistral": {"model": "mistral-small-latest", "enabled": True},
                    "claude": {"model": "Claude", "enabled": False},
                },
                "agents": {
                    "coder": "openai",
                    "researcher": "gemini",
                    "reviewer": "openai",
                    "tester": "ollama",
                },
                "routing": {
                    "simple": "gemini-3.5-flash-lite",
                    "moderate": "gemini",
                    "complex": "openai",
                    "long_context": "gemini",
                    "structured": "gemini",
                    "coding": "openai",
                    "debugging": "openai",
                    "testing": "ollama",
                    "review": "openai",
                    "research": "gemini",
                    "file_analysis": "gemini",
                    "writing": "gemini",
                    "exam_creation": "gemini",
                    "verification": "openai",
                    "general_question": "gemini",
                    "fallback": "ollama",
                },
            }

    def _build_runtime_components(self) -> None:
        providers_cfg = self.settings.get("providers", {})
        routing_cfg = self.settings.get("routing", {})

        gemini_model = str(providers_cfg.get("gemini", {}).get("model") or "gemini-3.8-flash")
        lite_model = str(routing_cfg.get("simple") or "gemini-3.5-flash-lite")
        openai_model = str(providers_cfg.get("openai", {}).get("model") or "gpt-5-mini")
        mistral_model = str(providers_cfg.get("mistral", {}).get("model") or "mistral-small-latest")
        ollama_model = str(providers_cfg.get("ollama", {}).get("model") or OllamaProvider.DEFAULT_MODEL)

        gemini_main = GeminiProvider(model=gemini_model)
        gemini_main._available_models = {
            gemini_model: f"Gemini Flash ({gemini_model})",
            lite_model: f"Gemini Flash Lite ({lite_model})",
        }
        gemini_lite = GeminiProvider(model=lite_model)
        gemini_lite._available_models = dict(gemini_main._available_models)

        providers = {
            "gemini": gemini_main,
            "gemini_flash_lite": gemini_lite,
            "openai": OpenAIProvider(model=openai_model),
            "mistral": MistralProvider(model=mistral_model),
            "ollama": OllamaProvider(model=ollama_model),
        }

        default_prov = "gemini"
        if os.environ.get("GEMINI_API_KEY", "").strip():
            default_prov = "gemini"
        elif os.environ.get("OPENAI_API_KEY", "").strip():
            default_prov = "openai"
        elif os.environ.get("MISTRAL_API_KEY", "").strip():
            default_prov = "mistral"

        raw_agents = self.settings.get("agents", {})
        agent_routes = {
            k: (v.get("provider", default_prov) if isinstance(v, dict) else str(v))
            for k, v in raw_agents.items()
        }
        task_routes: dict[str, str] = {}
        for k, v in routing_cfg.items():
            if k == "simple" and "gemini_flash_lite" in providers:
                task_routes[k] = "gemini_flash_lite"
            else:
                task_routes[k] = str(v)

        router = ModelRouter(
            providers=providers,
            agent_provider_map=agent_routes,
            default_provider=default_prov,
            task_provider_map=task_routes,
        )

        agent_registry = AgentRegistry()
        code_agent = CodeAgent()
        research_agent = ResearchAgent()
        review_agent = ReviewAgent()
        test_agent = TestAgent()

        agent_registry.register(code_agent, key="coder")
        agent_registry.register(research_agent, key="researcher")
        agent_registry.register(review_agent, key="reviewer")
        agent_registry.register(test_agent, key="tester")

        skills_root = self.project_root / "skills"
        skill_registry = SkillRegistry.from_directory(skills_root)
        skill_loader = SkillLoader(skills_root)
        skill_router = SkillRouter(skill_registry, skill_loader)

        self.filesystem = WorkspaceFilesystem(self.workspace_path)
        self.permissions = PermissionPolicy(
            autonomous=False,
            dry_run=False,
            confirm=self._confirm_tool_action,
            mode=HarnessMode.ACCEPT.value,
            edit_preview=self._preview_edit_action,
        )
        self.tools = ToolRegistry(self.filesystem, permissions=self.permissions)
        planner = Planner()
        planner.set_agent_registry(agent_registry)
        verifier = Verifier()

        self.agent_loop = AgentLoop(
            tools=self.tools,
            planner=planner,
            verifier=verifier,
            max_iterations=15,
            max_retries=2,
            max_tool_calls=20,
            emit=lambda _msg: None,
            event_sink=self.event_bus.handle_harness_event,
            stream_callback=lambda delta, acc: self.event_bus.emit_stream_delta(
                delta=delta, accumulated=acc
            ),
        )
        self.orchestrator = Orchestrator(
            agents=agent_registry,
            router=router,
            default_agent="researcher",
        )
        self.orchestrator.skill_registry = skill_registry
        self.orchestrator.skill_loader = skill_loader
        self.orchestrator.skill_router = skill_router

    # ------------------------------------------------------------------
    # APPROBATIONS HUMAINES & APERÇU DIFF
    # ------------------------------------------------------------------

    def _preview_edit_action(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.event_bus.emit_normalized(
            event="AGENT_STEP",
            raw_event="edit.preview",
            summary=f"Aperçu de modification préparé ({tool_name}) sur {arguments.get('path', '')}",
            tool=tool_name,
            details={"path": arguments.get("path", ""), "tool": tool_name},
        )

    def _confirm_tool_action(self, tool_name: str, risk: RiskLevel) -> bool:
        if tool_name in self._always_approved_tools or tool_name in self._task_approved_tools:
            return True
        if self.auto_approve_in_headless:
            return True

        approval_id = f"appr-{uuid.uuid4().hex[:8]}"
        evt = threading.Event()
        record = {
            "id": approval_id,
            "task_id": self.current_task_id or "session",
            "tool": tool_name,
            "risk_level": risk.name,
            "status": "pending",
            "decision": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "message": f"L'agent demande l'autorisation d'exécuter l'outil '{tool_name}' (risque : {risk.name}).",
        }
        with self._lock:
            self._pending_approvals[approval_id] = record
            self._approval_events[approval_id] = evt
            previous_status = self.current_task_status
            self.current_task_status = "Attente validation"

        self.event_bus.emit_normalized(
            event="APPROVAL_REQUIRED",
            raw_event="permission.approval_required",
            summary=f"Validation humaine requise pour {tool_name} ({risk.name})",
            tool=tool_name,
            status="waiting_approval",
            details=record,
        )

        evt.wait(timeout=self.approval_timeout_seconds)

        with self._lock:
            self.current_task_status = previous_status
            final_record = self._pending_approvals.pop(approval_id, record)
            self._approval_events.pop(approval_id, None)

        decision = final_record.get("decision") or "deny"
        if decision == "allow_always":
            self._always_approved_tools.add(tool_name)
            return True
        if decision == "allow_task":
            self._task_approved_tools.add(tool_name)
            return True
        if decision == "allow_once":
            return True
        return False

    def resolve_approval(self, approval_id: str, decision: str) -> dict[str, Any]:
        valid = {"allow_once", "allow_task", "allow_always", "deny"}
        if decision not in valid:
            raise ValueError(f"Décision invalide '{decision}'. Attendu : {', '.join(sorted(valid))}.")
        with self._lock:
            if approval_id not in self._pending_approvals:
                raise KeyError(f"Aucune demande d'approbation en attente avec l'identifiant {approval_id}.")
            record = self._pending_approvals[approval_id]
            record["decision"] = decision
            record["status"] = "approved" if decision != "deny" else "denied"
            evt = self._approval_events.get(approval_id)
            if evt is not None:
                evt.set()
        self.event_bus.emit_normalized(
            event="AGENT_STEP",
            raw_event="permission.resolved",
            summary=f"Approbation {record['tool']} : {decision}",
            tool=record["tool"],
            status=record["status"],
            details={"approval_id": approval_id, "decision": decision},
        )
        return record

    def list_pending_approvals(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._pending_approvals.values()]

    # ------------------------------------------------------------------
    # CONVERSATIONS
    # ------------------------------------------------------------------

    def _load_conversations(self) -> list[dict[str, Any]]:
        if self._conversations_path.is_file():
            try:
                raw = json.loads(self._conversations_path.read_text(encoding="utf-8"))
                if isinstance(raw, list) and raw:
                    return raw
            except Exception:
                pass
        return [self._create_default_conversation(persist=False)]

    def _save_conversations(self) -> None:
        try:
            self._conversations_path.parent.mkdir(parents=True, exist_ok=True)
            self._conversations_path.write_text(
                json.dumps(self.conversations, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _create_default_conversation(self, *, persist: bool = True) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        conv = {
            "id": f"conv-{uuid.uuid4().hex[:8]}",
            "title": "Nouvelle tâche",
            "pinned": False,
            "archived": False,
            "project": "NeoHarness AI",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        if hasattr(self, "conversations"):
            self.conversations.insert(0, conv)
            if persist:
                self._save_conversations()
        return conv

    def list_conversations(
        self,
        *,
        query: str = "",
        include_archived: bool = True,
    ) -> list[dict[str, Any]]:
        needle = query.strip().casefold()
        result = []
        for conv in self.conversations:
            if not include_archived and conv.get("archived", False):
                continue
            if needle:
                in_title = needle in str(conv.get("title", "")).casefold()
                in_msgs = any(
                    needle in str(m.get("content", "")).casefold()
                    for m in conv.get("messages", [])
                )
                if not (in_title or in_msgs):
                    continue
            result.append(conv)
        return result

    def create_conversation(self, title: str = "Nouvelle tâche", project: str = "NeoHarness AI") -> dict[str, Any]:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            conv = {
                "id": f"conv-{uuid.uuid4().hex[:8]}",
                "title": title.strip() or "Nouvelle tâche",
                "pinned": False,
                "archived": False,
                "project": project.strip() or "NeoHarness AI",
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            self.conversations.insert(0, conv)
            self.active_conversation_id = conv["id"]
            self._save_conversations()
            return conv

    def get_conversation(self, conversation_id: str | None = None) -> dict[str, Any]:
        cid = conversation_id or self.active_conversation_id
        for conv in self.conversations:
            if conv["id"] == cid:
                return conv
        if self.conversations:
            self.active_conversation_id = self.conversations[0]["id"]
            return self.conversations[0]
        return self.create_conversation()

    def update_conversation(
        self,
        conversation_id: str,
        *,
        title: str | None = None,
        pinned: bool | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            for conv in self.conversations:
                if conv["id"] == conversation_id:
                    if title is not None and title.strip():
                        conv["title"] = title.strip()
                    if pinned is not None:
                        conv["pinned"] = bool(pinned)
                    if archived is not None:
                        conv["archived"] = bool(archived)
                    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._save_conversations()
                    return conv
        raise KeyError(f"Conversation introuvable : {conversation_id}")

    def delete_conversation(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            for index, conv in enumerate(self.conversations):
                if conv["id"] == conversation_id:
                    removed = self.conversations.pop(index)
                    if not self.conversations:
                        self._create_default_conversation(persist=False)
                    if self.active_conversation_id == conversation_id:
                        self.active_conversation_id = self.conversations[0]["id"]
                    self._save_conversations()
                    return removed
            # Si déjà supprimée ou inexistante, retourner un succès idempotent sans erreur 400
            if not self.conversations:
                self._create_default_conversation(persist=True)
            return {
                "id": conversation_id,
                "title": "",
                "deleted": False,
                "status": "already_deleted",
            }

    # ------------------------------------------------------------------
    # PROJETS, AGENTS, SKILLS, TOOLS, MODÈLES
    # ------------------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        """Retourne uniquement les projets et dossiers de travail réellement présents."""
        projects = [
            {
                "id": "neoharness",
                "name": "NeoHarness AI",
                "path": str(self.project_root),
                "workspace": str(self.workspace_path),
                "type": "Harness Principal",
                "active": True,
            }
        ]
        if self.workspace_path.is_dir():
            for child in sorted(self.workspace_path.iterdir(), key=lambda p: p.name.casefold()):
                if child.is_dir() and not child.name.startswith("."):
                    projects.append(
                        {
                            "id": f"ws:{child.name}",
                            "name": child.name,
                            "path": str(child),
                            "workspace": str(child),
                            "type": "Dossier Workspace",
                            "active": False,
                        }
                    )
        return projects

    def list_agents(self) -> list[dict[str, Any]]:
        """Retourne la liste réelle des agents enregistrés + agents spécialisés de Skills."""
        agents_list: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        router = self.orchestrator.router

        for agent in self.orchestrator.agent_registry.list_agents():
            seen_names.add(agent.name)
            try:
                provider = router.get_provider(agent.routing_key)
                provider_label = f"{provider.get_name()} ({provider.get_model_name()})"
            except Exception:
                provider_label = "Non résolu"
            agents_list.append(
                {
                    "key": agent.routing_key,
                    "name": agent.name,
                    "role": agent.role,
                    "description": getattr(agent, "description", ""),
                    "capabilities": list(getattr(agent, "capabilities", ())),
                    "supported_intents": list(getattr(agent, "supported_intents", ())),
                    "allowed_tools": list(getattr(agent, "allowed_tools", None) or []),
                    "routed_provider": provider_label,
                    "source": "AgentRegistry (agents/)",
                }
            )

        # Ajout des agents propres aux Skills réellement présents (ex: BacBlancAgent)
        for descriptor in self.orchestrator.skill_registry.list_skills():
            try:
                definition = self.orchestrator.skill_loader.load(descriptor)
            except Exception:
                continue
            if definition.agent is not None and definition.agent.name not in seen_names:
                seen_names.add(definition.agent.name)
                try:
                    provider = router.get_provider(definition.agent.routing_key, intent="exam_creation")
                    provider_label = f"{provider.get_name()} ({provider.get_model_name()})"
                except Exception:
                    provider_label = "Non résolu"
                agents_list.append(
                    {
                        "key": definition.agent.routing_key,
                        "name": definition.agent.name,
                        "role": definition.agent.role,
                        "description": getattr(definition.agent, "description", ""),
                        "capabilities": list(getattr(definition.agent, "capabilities", ())),
                        "supported_intents": list(getattr(definition.agent, "supported_intents", ())),
                        "allowed_tools": list(definition.tools),
                        "routed_provider": provider_label,
                        "source": f"Skill /{definition.name} (skills/{definition.name}/agent.py)",
                    }
                )
        return agents_list

    def list_tools(self) -> list[dict[str, Any]]:
        """Retourne les outils réellement enregistrés dans ToolRegistry."""
        items: list[dict[str, Any]] = []
        for tool in self.tools.discover():
            items.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "risk_level": tool.risk_level.name,
                    "mutates": tool.mutates,
                    "timeout": tool.timeout,
                    "permissions": list(tool.permissions),
                    "schema": tool.schema,
                }
            )
        return items

    def select_model(self, model_identifier: str) -> dict[str, Any]:
        """Sélectionne dynamiquement un modèle ou active le mode Auto, et recalcule les Skills."""
        requested = (model_identifier or "auto").strip()
        router = self.orchestrator.router

        if requested.casefold() == "auto":
            router.enable_automatic_routing()
            compat = self.skill_compatibility.evaluate_for_model("auto")
            self.event_bus.emit_normalized(
                event="MODEL_SELECTED",
                raw_event="model.auto",
                summary="Routage de modèle basculé sur Auto (ModelRouter)",
                provider="Auto",
                model="Auto (ModelRouter)",
                status="completed",
            )
            return {
                "selection": self.model_registry.active_selection_summary(),
                "compatibility": compat,
            }

        descriptor = self.model_registry.resolve_model(requested)
        if descriptor is None:
            raise ValueError(f"Modèle ou provider inconnu : '{requested}'.")

        # Si le provider n'est pas encore dans router.providers (ex: Claude pour inspection de compatibilité),
        # on l'enregistre ou on met à jour le modèle actif.
        if descriptor.provider_key not in router.providers:
            if descriptor.provider_family == "claude":
                router.providers["claude"] = ClaudeProvider()
            elif descriptor.provider_family == "gemini":
                p = GeminiProvider(model=descriptor.model_name)
                p._available_models = {descriptor.model_name: descriptor.display_name}
                router.providers[descriptor.provider_key] = p
            elif descriptor.provider_family == "openai":
                router.providers[descriptor.provider_key] = OpenAIProvider(model=descriptor.model_name)
            elif descriptor.provider_family == "mistral":
                router.providers[descriptor.provider_key] = MistralProvider(model=descriptor.model_name)
            elif descriptor.provider_family == "ollama":
                router.providers[descriptor.provider_key] = OllamaProvider(model=descriptor.model_name)

        provider = router.providers.get(descriptor.provider_key)
        if isinstance(provider, GeminiProvider) and descriptor.model_name:
            provider._available_models[descriptor.model_name] = descriptor.display_name
            provider.model = descriptor.model_name

        if descriptor.provider_key in router.providers:
            router.set_active_provider(descriptor.provider_key)

        compat = self.skill_compatibility.evaluate_for_model(descriptor.id)

        # Désactive automatiquement les Skills manuels devenus incompatibles avec ce modèle
        compatible_names = {s["name"] for s in compat["available_skills"]}
        current_manual = self.generation_preferences.get("active_skills", [])
        if current_manual:
            self.generation_preferences["active_skills"] = [
                name for name in current_manual if name in compatible_names
            ]

        self.event_bus.emit_normalized(
            event="MODEL_SELECTED",
            raw_event="model.selected",
            summary=f"Modèle sélectionné : {descriptor.display_name} ({ len(compat['available_skills']) } Skills compatibles)",
            provider=descriptor.provider_family,
            model=descriptor.model_name,
            status="completed",
            details={
                "model_id": descriptor.id,
                "compatible_skills": len(compat["available_skills"]),
                "incompatible_skills": len(compat["unavailable_skills"]),
            },
        )
        return {
            "selection": self.model_registry.active_selection_summary(),
            "compatibility": compat,
        }

    def set_mode(self, mode_name: str) -> dict[str, Any]:
        previous, selected = self.mode_manager.set_mode(mode_name)
        return {
            "previous": previous.value,
            "current": selected.value,
            "description": ModeManager.DESCRIPTIONS[selected],
            "short_description": ModeManager.SHORT_DESCRIPTIONS[selected],
        }

    def update_preferences(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if "style" in updates and updates["style"] in {"precis", "equilibre", "creatif", "avance"}:
                self.generation_preferences["style"] = updates["style"]
                style_temps = {"precis": 0.1, "equilibre": 0.4, "creatif": 0.8}
                if updates["style"] in style_temps:
                    self.generation_preferences["temperature"] = style_temps[updates["style"]]
            if "temperature" in updates and isinstance(updates["temperature"], (int, float)):
                self.generation_preferences["temperature"] = max(0.0, min(1.5, float(updates["temperature"])))
            if "max_output_tokens" in updates:
                val = updates["max_output_tokens"]
                if val is None or val == "":
                    self.generation_preferences["max_output_tokens"] = None
                elif isinstance(val, int) and val > 0:
                    self.generation_preferences["max_output_tokens"] = min(val, 32768)
            if "skill_mode" in updates and updates["skill_mode"] in {"auto", "manual"}:
                self.generation_preferences["skill_mode"] = updates["skill_mode"]
                if updates["skill_mode"] == "auto":
                    self.generation_preferences["active_skills"] = []
            if "active_skills" in updates and isinstance(updates["active_skills"], list):
                valid_skills = set(self.orchestrator.skill_registry.names)
                self.generation_preferences["active_skills"] = [
                    str(s).strip().lstrip("/").casefold()
                    for s in updates["active_skills"]
                    if str(s).strip().lstrip("/").casefold() in valid_skills
                ]
                self.generation_preferences["skill_mode"] = (
                    "manual" if self.generation_preferences["active_skills"] else "auto"
                )
            if "developer_mode" in updates:
                self.generation_preferences["developer_mode"] = bool(updates["developer_mode"])
        return dict(self.generation_preferences)

    # ------------------------------------------------------------------
    # WORKSPACE FILES & DIFF TRACKING
    # ------------------------------------------------------------------

    def _snapshot_workspace(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        try:
            for rel in self.filesystem.list_files(".", recursive=True):
                if rel.startswith(".harness/"):
                    continue
                try:
                    snapshot[rel] = self.filesystem.read_file(rel)
                except Exception:
                    try:
                        st = self.filesystem.resolve(rel).stat()
                        snapshot[rel] = f"[binaire:{st.st_size}:{st.st_mtime_ns}]"
                    except Exception:
                        snapshot[rel] = "[binaire]"
        except Exception:
            pass
        return snapshot

    def _record_workspace_diffs(
        self,
        before: dict[str, str],
        after: dict[str, str],
        *,
        agent: str = "",
        skill: str = "",
        tool: str = "",
    ) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        new_changes: list[dict[str, Any]] = []
        all_paths = sorted(set(before) | set(after))
        for path in all_paths:
            old_content = before.get(path)
            new_content = after.get(path)
            if old_content == new_content:
                continue
            if old_content is None:
                status = "+"
                status_label = "Créé"
                old_lines: list[str] = []
                new_lines = (new_content or "").splitlines()
            elif new_content is None:
                status = "D"
                status_label = "Supprimé"
                old_lines = (old_content or "").splitlines()
                new_lines = []
            else:
                status = "M"
                status_label = "Modifié"
                old_lines = old_content.splitlines()
                new_lines = new_content.splitlines()

            unified = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
            )
            added = sum(1 for line in unified if line.startswith("+") and not line.startswith("+++"))
            removed = sum(1 for line in unified if line.startswith("-") and not line.startswith("---"))
            change = {
                "id": f"diff-{uuid.uuid4().hex[:8]}",
                "path": path,
                "status": status,
                "status_label": status_label,
                "agent": agent or "CodeAgent",
                "skill": skill or "aucun",
                "tool": tool or ("write_file" if status == "+" else "patch_file"),
                "timestamp": now,
                "added_lines": added,
                "removed_lines": removed,
                "diff": "\n".join(unified[:500]),
                "after_preview": (new_content or "")[:4000],
            }
            new_changes.append(change)
            self.file_changes.insert(0, change)
        self.file_changes = self.file_changes[:100]
        return new_changes

    def list_workspace_files(self) -> dict[str, Any]:
        files = []
        change_by_path = {item["path"]: item for item in reversed(self.file_changes)}
        for rel in self.filesystem.list_files(".", recursive=True):
            if rel.startswith(".harness/"):
                continue
            full_path = self.filesystem.resolve(rel)
            stat = full_path.stat()
            change = change_by_path.get(rel)
            files.append(
                {
                    "path": rel,
                    "name": Path(rel).name,
                    "extension": Path(rel).suffix.lower(),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "status": change["status"] if change else "",
                    "status_label": change["status_label"] if change else "Intact",
                }
            )
        return {
            "workspace_root": str(self.workspace_path),
            "files": files,
            "changes": self.file_changes,
        }

    def read_workspace_file(self, relative_path: str) -> dict[str, Any]:
        ext = Path(relative_path).suffix.lower()
        if ext in {".pdf", ".docx", ".xlsx", ".pptx"}:
            extracted = read_document(relative_path, filesystem=self.filesystem)
            return {
                "path": extracted["path"],
                "content": extracted["text"],
                "format": extracted["format"],
                "metadata": extracted["metadata"],
            }
        content = self.filesystem.read_file(relative_path)
        return {
            "path": relative_path,
            "content": content,
            "format": ext.lstrip(".") or "txt",
            "metadata": {"extraction": "utf8"},
        }

    def get_pdf_info(self, relative_path: str) -> dict[str, Any]:
        """Vérifie l'existence et la validité d'un PDF dans le workspace et retourne ses métadonnées."""
        target = self.filesystem.resolve(relative_path)
        rel = target.relative_to(self.filesystem.root).as_posix()
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Fichier PDF introuvable : {rel}")
        data = self.filesystem.read_bytes(rel)
        pages = _verify_compiled_pdf_bytes(data)
        candidate_tex = str(Path(rel).with_suffix(".tex")).replace("\\", "/")
        has_tex = False
        try:
            has_tex = self.filesystem.resolve(candidate_tex).is_file()
        except Exception:
            has_tex = False
        return {
            "path": rel,
            "name": target.name,
            "exists": True,
            "bytes": len(data),
            "size_bytes": len(data),
            "pages": pages,
            "page_count": pages,
            "source_tex": candidate_tex if has_tex else "",
            "raw_url": f"/api/files/raw?path={quote(rel)}",
            "modified_at": datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat(),
        }

    def compile_workspace_latex(
        self,
        tex_relative_path: str,
        *,
        output_relative_path: str | None = None,
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        """Compile un fichier LaTeX du workspace avec Tectonic et émet les événements d'activité réels."""
        self.event_bus.emit_normalized(
            event="TOOL_CALL",
            raw_event="tool.started",
            tool="tectonic",
            summary=f"Compilation LaTeX avec Tectonic : {tex_relative_path}",
            status="running",
            details={"path": tex_relative_path, "auto_repair": auto_repair},
        )
        res = compile_latex(
            tex_relative_path,
            filesystem=self.filesystem,
            output_relative_path=output_relative_path,
            auto_repair=auto_repair,
        )
        # Si la réparation déterministe n'a pas suffi, tentative réelle de correction via le modèle actif puis recompilation Tectonic
        if res["status"] != "success" and auto_repair:
            try:
                raw_tex = self.filesystem.read_file(tex_relative_path)
                err_log = str(res.get("log") or res.get("error") or "")[-1800:]
                self.event_bus.emit_normalized(
                    event="AGENT_STEP",
                    raw_event="latex.llm_repair",
                    summary=f"Correction intelligente du source LaTeX suite à l'erreur Tectonic sur {tex_relative_path}",
                    tool="tectonic",
                    status="running",
                )
                self._ensure_routed_providers_ready()
                repair_provider = self.orchestrator.router.get_provider("coder", intent="writing")
                repair_prompt = (
                    "Tu es un expert LaTeX / Tectonic. Le fichier LaTeX ci-dessous a échoué à la compilation Tectonic.\n"
                    "Corrige uniquement les erreurs LaTeX pour qu'il compile sans erreur avec Tectonic (pdflatex/xelatex standard, "
                    "utilise \\usepackage[T1]{fontenc}, \\usepackage{lmodern}, \\usepackage{amsmath,amssymb}).\n"
                    "Renvoie EXCLUSIVEMENT le code LaTeX complet corrigé entre \\documentclass et \\end{document}, sans explication.\n\n"
                    f"=== ERREUR TECTONIC ===\n{err_log}\n\n"
                    f"=== SOURCE LATEX ===\n{raw_tex}"
                )
                fixed_reply = str(repair_provider.generate(repair_prompt) or "").strip()
                m_tex = re.search(r"```(?:latex|tex)?\s*\r?\n([\s\S]*?)```", fixed_reply, re.IGNORECASE)
                candidate_tex = m_tex.group(1).strip() if m_tex else fixed_reply
                if "\\documentclass" in candidate_tex and "\\end{document}" in candidate_tex:
                    start_idx = candidate_tex.find("\\documentclass")
                    end_idx = candidate_tex.rfind("\\end{document}") + len("\\end{document}")
                    candidate_tex = candidate_tex[start_idx:end_idx]
                    self.filesystem.write_file(tex_relative_path, candidate_tex, overwrite=True)
                    retry_res = compile_latex(
                        tex_relative_path,
                        filesystem=self.filesystem,
                        output_relative_path=output_relative_path,
                        auto_repair=True,
                    )
                    if retry_res.get("status") == "success":
                        notes = list(retry_res.get("repair_notes") or [])
                        notes.append("Correction assistée par le modèle suite au diagnostic Tectonic.")
                        retry_res["repaired"] = True
                        retry_res["repair_notes"] = notes
                        res = retry_res
            except Exception:
                pass
        if res["status"] == "success":
            pdf_rel = str(res["pdf_path"])
            res["raw_url"] = f"/api/files/raw?path={quote(pdf_rel)}"
            res["type"] = "pdf"
            res["title"] = Path(pdf_rel).name
            res["page_count"] = int(res.get("pages") or 1)
            res["size_bytes"] = int(res.get("bytes") or 0)
            res["source_tex"] = str(res.get("source_path") or tex_relative_path)
            res["auto_repaired"] = bool(res.get("repaired", False))
            self.event_bus.emit_normalized(
                event="TOOL_RESULT",
                raw_event="tool.completed",
                tool="tectonic",
                summary=(
                    f"Compilation Tectonic réussie : {pdf_rel} ({res['pages']} page(s), {res['bytes']} octets)"
                    + (" [réparé automatiquement]" if res.get("repaired") else "")
                ),
                status="completed",
                details={
                    "pdf_path": pdf_rel,
                    "source_path": res["source_path"],
                    "pages": res["pages"],
                    "repaired": res.get("repaired", False),
                    "repair_notes": res.get("repair_notes", []),
                },
            )
            self.event_bus.emit_normalized(
                event="ARTIFACT_READY",
                raw_event="artifact.ready",
                summary=f"Document PDF prêt : {pdf_rel}",
                status="completed",
                details=res,
            )
        else:
            self.event_bus.emit_normalized(
                event="ERROR",
                raw_event="tool.error",
                tool="tectonic",
                summary=f"Échec de compilation Tectonic sur {tex_relative_path} : {res.get('error', '')}",
                status="error",
                error=str(res.get("error") or "compilation_failed"),
                details={"source_path": tex_relative_path, "log": str(res.get("log", ""))[:500]},
            )
        return res

    def compile_workspace_html(
        self,
        html_relative_path: str,
        *,
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        """Compile et valide un fichier HTML du workspace (HTML5, CSS, JS) avec auto-réparation et émet les événements d'activité réels."""
        self.event_bus.emit_normalized(
            event="TOOL_CALL",
            raw_event="tool.started",
            tool="html_compiler",
            summary=f"Validation & compilation HTML : {html_relative_path}",
            status="running",
            details={"path": html_relative_path, "auto_repair": auto_repair},
        )
        res = compile_html(
            html_relative_path,
            filesystem=self.filesystem,
            auto_repair=auto_repair,
        )
        # Si la réparation déterministe n'a pas suffi, tentative réelle de correction via le modèle actif puis recompilation
        if res.get("status") != "success" and auto_repair:
            try:
                raw_html = self.filesystem.read_file(html_relative_path)
                err_log = str(res.get("log") or res.get("error") or "")[-1800:]
                self.event_bus.emit_normalized(
                    event="AGENT_STEP",
                    raw_event="html.llm_repair",
                    summary=f"Correction intelligente du code HTML/JS suite à l'erreur sur {html_relative_path}",
                    tool="html_compiler",
                    status="running",
                )
                self._ensure_routed_providers_ready()
                repair_provider = self.orchestrator.router.get_provider("coder", intent="writing")
                repair_prompt = (
                    "Tu es un expert développeur Web frontend (HTML5, CSS3, JavaScript ES2022).\n"
                    "Le fichier HTML ci-dessous contient une erreur de syntaxe ou de structure détectée lors de la compilation.\n"
                    "Corrige les erreurs de syntaxe HTML/JS/CSS pour que le document soit parfaitement valide et exécutable sans erreur.\n"
                    "Renvoie EXCLUSIVEMENT le code HTML complet corrigé (commençant par <!DOCTYPE html>), sans balises Markdown autour ou avec ```html.\n\n"
                    f"=== ERREUR DÉTECTÉE ===\n{err_log}\n\n"
                    f"=== SOURCE HTML ===\n{raw_html}"
                )
                fixed_reply = str(repair_provider.generate(repair_prompt) or "").strip()
                m_html = re.search(r"```(?:html)?\s*\r?\n([\s\S]*?)```", fixed_reply, re.IGNORECASE)
                candidate_html = m_html.group(1).strip() if m_html else fixed_reply
                if "<!DOCTYPE" in candidate_html.upper() or "<html" in candidate_html.lower():
                    self.filesystem.write_file(html_relative_path, candidate_html, overwrite=True)
                    retry_res = compile_html(
                        html_relative_path,
                        filesystem=self.filesystem,
                        auto_repair=True,
                    )
                    if retry_res.get("status") == "success":
                        notes = list(retry_res.get("repair_notes") or [])
                        notes.append("Correction assistée par le modèle suite au diagnostic HTML/JS.")
                        retry_res["repaired"] = True
                        retry_res["repair_notes"] = notes
                        res = retry_res
            except Exception:
                pass

        if res.get("status") == "success":
            html_rel = str(res["html_path"])
            res["preview_url"] = f"/api/preview/workspace/{quote(html_rel)}"
            res["raw_url"] = f"/api/files/raw?path={quote(html_rel)}"
            res["type"] = "html"
            res["title"] = Path(html_rel).name
            res["size_bytes"] = int(res.get("bytes") or 0)
            res["source_html"] = html_rel
            res["auto_repaired"] = bool(res.get("repaired", False))
            self.event_bus.emit_normalized(
                event="TOOL_RESULT",
                raw_event="tool.completed",
                tool="html_compiler",
                summary=(
                    f"Validation & compilation HTML réussie : {html_rel} ({res['size_bytes']} octets)"
                    + (" [réparé automatiquement]" if res.get("repaired") else "")
                ),
                status="completed",
                details={
                    "html_path": html_rel,
                    "size_bytes": res["size_bytes"],
                    "repaired": res.get("repaired", False),
                    "repair_notes": res.get("repair_notes", []),
                    "scripts_checked": res.get("scripts_checked", 0),
                    "styles_checked": res.get("styles_checked", 0),
                },
            )
            self.event_bus.emit_normalized(
                event="ARTIFACT_READY",
                raw_event="artifact.ready",
                summary=f"Aperçu HTML prêt : {html_rel}",
                status="completed",
                details=res,
            )
        else:
            self.event_bus.emit_normalized(
                event="ERROR",
                raw_event="tool.error",
                tool="html_compiler",
                summary=f"Échec de validation HTML sur {html_relative_path} : {res.get('error', '')}",
                status="error",
                error=str(res.get("error") or "compilation_failed"),
                details={"source_path": html_relative_path, "log": str(res.get("log", ""))[:500]},
            )
        return res

    def write_workspace_file(
        self,
        relative_path: str,
        content: str,
        *,
        compile_if_latex: bool = False,
        compile_if_html: bool = True,
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        """Écrit ou met à jour un fichier dans le workspace, enregistre le diff et prépare l'aperçu."""
        if self.permissions.dry_run or self.mode_manager.current == HarnessMode.PLAN:
            raise PermissionError("Écriture refusée en mode PLAN (dry-run actif).")
        before = self._snapshot_workspace()
        info = self.filesystem.write_file(relative_path, content, overwrite=True)
        rel = info["path"]
        after = self._snapshot_workspace()
        diffs = self._record_workspace_diffs(before, after, agent="Utilisateur / Runtime", tool="write_file")
        ext = Path(rel).suffix.lower()
        artifact: dict[str, Any] | None = None
        compilation: dict[str, Any] | None = None
        if ext in {".html", ".htm"}:
            if compile_if_html:
                compilation = self.compile_workspace_html(rel, auto_repair=auto_repair)
                if compilation.get("status") == "success":
                    artifact = compilation
                else:
                    artifact = {
                        "type": "html",
                        "title": Path(rel).name,
                        "path": rel,
                        "bytes": info["bytes"],
                        "sha256": info["sha256"],
                        "preview_url": f"/api/preview/workspace/{quote(rel)}",
                        "raw_url": f"/api/files/raw?path={quote(rel)}",
                        "error": compilation.get("error"),
                        "log": compilation.get("log"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            else:
                artifact = {
                    "type": "html",
                    "title": Path(rel).name,
                    "path": rel,
                    "bytes": info["bytes"],
                    "sha256": info["sha256"],
                    "preview_url": f"/api/preview/workspace/{quote(rel)}",
                    "raw_url": f"/api/files/raw?path={quote(rel)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self.event_bus.emit_normalized(
                    event="ARTIFACT_READY",
                    raw_event="artifact.ready",
                    summary=f"Aperçu HTML mis à jour : {rel}",
                    status="completed",
                    details=artifact,
                )
        elif ext == ".tex" and compile_if_latex:
            compilation = self.compile_workspace_latex(rel, auto_repair=auto_repair)
            if compilation.get("status") == "success":
                artifact = compilation
        return {
            "file": info,
            "diffs": diffs,
            "artifact": artifact,
            "compilation": compilation,
        }

    def upload_workspace_file(
        self,
        filename: str,
        *,
        content_base64: str | None = None,
        content_text: str | None = None,
        mime_type: str = "",
    ) -> dict[str, Any]:
        """Enregistre une pièce jointe réelle (fichier, PDF, image, code) dans workspace/uploads/."""
        raw_name = Path(filename or "piece_jointe.txt").name
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", raw_name).strip("._") or f"fichier_{uuid.uuid4().hex[:6]}"
        rel_path = f"uploads/{safe_name}"
        before = self._snapshot_workspace()

        if content_base64:
            clean_b64 = content_base64.strip()
            if "," in clean_b64 and clean_b64.lower().startswith("data:"):
                clean_b64 = clean_b64.split(",", 1)[1]
            data = base64.b64decode(clean_b64)
            info = self.filesystem.write_bytes(rel_path, data, overwrite=True)
        elif content_text is not None:
            info = self.filesystem.write_file(rel_path, str(content_text), overwrite=True)
        else:
            raise ValueError("Contenu de fichier manquant (content_base64 ou content_text requis).")

        after = self._snapshot_workspace()
        diffs = self._record_workspace_diffs(before, after, agent="Utilisateur", tool="upload_file")
        saved_rel = str(info["path"])
        ext = Path(saved_rel).suffix.lower()

        extracted_preview = ""
        try:
            if ext in {".pdf", ".docx", ".xlsx", ".pptx"}:
                doc = read_document(saved_rel, filesystem=self.filesystem)
                extracted_preview = str(doc.get("text") or "")[:2000]
            elif ext in {".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".csv", ".tex", ".html", ".css"}:
                extracted_preview = self.filesystem.read_file(saved_rel)[:2000]
        except Exception:
            extracted_preview = ""

        if extracted_preview:
            self.orchestrator.context.remember_file(saved_rel, extracted_preview)

        self.event_bus.emit_normalized(
            event="AGENT_STEP",
            raw_event="file.uploaded",
            summary=f"Pièce jointe ajoutée au workspace : {saved_rel} ({info.get('bytes', 0)} octets)",
            status="completed",
            details={"path": saved_rel, "bytes": info.get("bytes", 0), "mime_type": mime_type},
        )
        return {
            "path": saved_rel,
            "name": Path(saved_rel).name,
            "extension": ext,
            "bytes": info.get("bytes", 0),
            "sha256": info.get("sha256", ""),
            "mime_type": mime_type,
            "preview": extracted_preview[:500],
            "diffs": diffs,
        }

    @staticmethod
    def _markdown_to_latex_document(title: str, markdown_body: str) -> str:
        """Convertit un contenu Markdown/texte en source LaTeX propre compilable par Tectonic."""
        def _esc(text: str) -> str:
            out = text
            out = out.replace("\\", "\\textbackslash{}")
            for ch, rep in (
                ("&", "\\&"),
                ("%", "\\%"),
                ("$", "\\$"),
                ("#", "\\#"),
                ("_", "\\_"),
                ("{", "\\{"),
                ("}", "\\}"),
                ("~", "\\textasciitilde{}"),
                ("^", "\\textasciicircum{}"),
            ):
                out = out.replace(ch, rep)
            return out

        def _format_inline(line_str: str) -> str:
            # Préserve les segments math $...$ simples s'ils existent
            parts = re.split(r"(\$[^$\n]+\$)", line_str)
            rendered: list[str] = []
            for p in parts:
                if p.startswith("$") and p.endswith("$") and len(p) >= 3:
                    rendered.append(p)
                else:
                    escaped = _esc(p)
                    escaped = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", escaped)
                    escaped = re.sub(r"\*([^*]+)\*", r"\\textit{\1}", escaped)
                    escaped = re.sub(r"`([^`]+)`", r"\\texttt{\1}", escaped)
                    rendered.append(escaped)
            return "".join(rendered)

        clean_title = _esc((title or "Document NeoHarness AI").strip()[:90])
        lines = (markdown_body or "").splitlines()
        body_tex: list[str] = []
        in_itemize = False
        in_code = False

        for raw in lines:
            stripped = raw.strip()
            if stripped.startswith("```"):
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                if not in_code:
                    body_tex.append("\\begin{verbatim}")
                    in_code = True
                else:
                    body_tex.append("\\end{verbatim}")
                    in_code = False
                continue
            if in_code:
                body_tex.append(raw)
                continue
            if not stripped:
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                body_tex.append("")
                continue
            if stripped.startswith("# "):
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                body_tex.append(f"\\section*{{{_format_inline(stripped[2:].strip())}}}")
            elif stripped.startswith("## "):
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                body_tex.append(f"\\subsection*{{{_format_inline(stripped[3:].strip())}}}")
            elif stripped.startswith("### "):
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                body_tex.append(f"\\subsubsection*{{{_format_inline(stripped[4:].strip())}}}")
            elif stripped.startswith(("- ", "* ", "• ")):
                if not in_itemize:
                    body_tex.append("\\begin{itemize}")
                    in_itemize = True
                body_tex.append(f"  \\item {_format_inline(stripped[2:].strip())}")
            else:
                if in_itemize:
                    body_tex.append("\\end{itemize}")
                    in_itemize = False
                body_tex.append(_format_inline(stripped))

        if in_itemize:
            body_tex.append("\\end{itemize}")
        if in_code:
            body_tex.append("\\end{verbatim}")

        joined_body = "\n".join(body_tex).strip() or "Document généré par NeoHarness AI."
        return (
            "\\documentclass[11pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage[T1]{fontenc}\n"
            "\\usepackage{lmodern}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage[margin=2.2cm]{geometry}\n"
            "\\usepackage{hyperref}\n"
            f"\\title{{{clean_title}}}\n"
            "\\author{NeoHarness AI}\n"
            "\\date{\\today}\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            f"{joined_body}\n\n"
            "\\end{document}\n"
        )

    def _build_education_latex_document(
        self,
        skill: str,
        prompt: str,
        content: str,
    ) -> str:
        """Construit un document LaTeX complet, typographiquement rigoureux et directement
        compilable par Tectonic pour les Skills d'éducation (/exercice, /dm, /bacblanc)."""
        # 1. Si la réponse contient déjà un document LaTeX complet avec documentclass, le réutiliser
        tex_match = re.search(r"```(?:latex|tex)\s*\r?\n([\s\S]*?)```", content, re.IGNORECASE)
        raw_code = tex_match.group(1).strip() if tex_match else ""
        if raw_code and "\\documentclass" in raw_code and "\\begin{document}" in raw_code:
            return raw_code

        # 2. Détection du niveau et du sujet
        prompt_lower = prompt.casefold()
        if "première" in prompt_lower or "1ere" in prompt_lower or "1ère" in prompt_lower:
            classe_str = "Première Spécialité Mathématiques"
        elif "seconde" in prompt_lower or "2nde" in prompt_lower:
            classe_str = "Seconde Générale"
        elif "experte" in prompt_lower:
            classe_str = "Terminale -- Option Mathématiques Expertes"
        elif "complémentaire" in prompt_lower:
            classe_str = "Terminale -- Option Mathématiques Complémentaires"
        elif "terminale" in prompt_lower or "tle" in prompt_lower:
            classe_str = "Terminale Spécialité Mathématiques"
        else:
            classe_str = "Lycée -- Mathématiques"

        # Titre propre sans les slash commands
        title_clean = re.sub(r"^/(?:exercice|dm|bacblanc)\s*", "", prompt.strip(), flags=re.IGNORECASE)
        title_clean = title_clean.strip(" .:-_") or "Exercice de Mathématiques"
        if len(title_clean) > 80:
            title_clean = title_clean[:77] + "…"

        display_type = "Devoir Maison" if skill == "dm" else ("Bac Blanc" if skill == "bacblanc" else "Exercice")

        # 3. Récupération obligatoire du gabarit officiel existant (aucune improvisation tolérée)
        tmpl_map = {
            "exercice": PROJECT_ROOT / "skills" / "education" / "exercice" / "templates" / "template_exercice.tex",
            "dm": PROJECT_ROOT / "skills" / "education" / "dm" / "templates" / "template_dm.tex",
            "bacblanc": PROJECT_ROOT / "skills" / "education" / "bacblanc" / "templates" / "sujet_bacblanc.tex",
        }
        tmpl_path = tmpl_map.get(skill)
        if not tmpl_path or not tmpl_path.is_file():
            raise FileNotFoundError(
                f"Gabarit LaTeX officiel obligatoire introuvable pour /{skill} (chemin attendu : {tmpl_path}). "
                "Le Skill refuse formellement d'improviser un document LaTeX hors template."
            )

        raw_tmpl = tmpl_path.read_text(encoding="utf-8")
        if "\\begin{document}" not in raw_tmpl:
            raise ValueError(f"Le gabarit officiel de /{skill} est invalide : balise \\begin{{document}} absente.")

        preamble = raw_tmpl.split("\\begin{document}")[0].strip()
        preamble = re.sub(r"\\lhead\{[^}]*\}", "\\\\lhead{NeoHarness AI}", preamble)
        preamble = re.sub(r"\\rhead\{[^}]*\}", f"\\\\rhead{{{classe_str}}}", preamble)

        # 4. Préparation du corps du document
        body_tex: list[str] = []
        body_source = raw_code if raw_code else content

        if raw_code and ("\\exo" in raw_code or "\\partie" in raw_code or "\\item" in raw_code):
            body_tex.append(raw_code)
        else:
            def _format_markdown_for_latex(text: str) -> str:
                # 1. Backticks -> \texttt{...} avec échappement interne
                text = re.sub(
                    r"`([^`]+)`",
                    lambda m: r"\texttt{" + m.group(1).replace("_", r"\_").replace("#", r"\#").replace("&", r"\&").replace("%", r"\%") + "}",
                    text,
                )
                # 2. Gras et italique
                text = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", text)
                text = re.sub(r"\*([^*]+)\*", r"\\textit{\1}", text)
                # 3. Échappement des caractères spéciaux hors mode mathématique
                parts = text.split("$")
                for i in range(0, len(parts), 2):
                    parts[i] = parts[i].replace("#", r"\#").replace("&", r"\&").replace("%", r"\%")
                    parts[i] = re.sub(r"(?<!\\)_", r"\_", parts[i])
                return "$".join(parts)

            exo_counter = 1
            in_enumerate = False
            for line in body_source.splitlines():
                stripped = line.strip()
                if not stripped:
                    if in_enumerate:
                        body_tex.append("\\end{enumerate}")
                        in_enumerate = False
                    body_tex.append("")
                    continue
                if re.match(r"^#{1,3}\s*(?:Exercice\s*\d*[:.-]?\s*)?(.*)$", stripped, re.IGNORECASE) and (
                    "exercice" in stripped.casefold() or "problème" in stripped.casefold() or "sujet" in stripped.casefold()
                ):
                    if in_enumerate:
                        body_tex.append("\\end{enumerate}")
                        in_enumerate = False
                    sub_title = re.sub(r"^#{1,3}\s*(?:Exercice\s*\d*[:.-]?\s*)?", "", stripped, flags=re.IGNORECASE).strip() or title_clean
                    sub_title = _format_markdown_for_latex(sub_title)
                    body_tex.append(f"\\exo{{{exo_counter}}}{{{sub_title}}}")
                    exo_counter += 1
                elif re.match(r"^#{2,4}\s*(Partie\s+[A-Z0-9].*)$", stripped, re.IGNORECASE):
                    if in_enumerate:
                        body_tex.append("\\end{enumerate}")
                        in_enumerate = False
                    part_title = re.sub(r"^#{2,4}\s*", "", stripped).strip()
                    part_title = _format_markdown_for_latex(part_title)
                    body_tex.append(f"\\partie{{{part_title}}}")
                elif re.match(r"^#{1,6}\s*(.*)$", stripped):
                    if in_enumerate:
                        body_tex.append("\\end{enumerate}")
                        in_enumerate = False
                    sec_title = re.sub(r"^#{1,6}\s*", "", stripped).strip()
                    sec_title = _format_markdown_for_latex(sec_title)
                    body_tex.append(f"\\vspace{{0.35cm}}\\noindent\\textbf{{\\large {sec_title}}}\\par\\vspace{{0.15cm}}")
                elif re.match(r"^(?:\d+[\.)]|\*\s+|\-\s+)(.*)$", stripped):
                    if not in_enumerate:
                        body_tex.append("\\begin{enumerate}")
                        in_enumerate = True
                    item_text = re.sub(r"^(?:\d+[\.)]|\*\s+|\-\s+)", "", stripped).strip()
                    item_text = _format_markdown_for_latex(item_text)
                    body_tex.append(f"  \\item {item_text}")
                else:
                    if in_enumerate:
                        body_tex.append("\\end{enumerate}")
                        in_enumerate = False
                    p_text = _format_markdown_for_latex(stripped)
                    body_tex.append(p_text)

            if in_enumerate:
                body_tex.append("\\end{enumerate}")

        joined_body = "\n".join(body_tex).strip()
        if not joined_body:
            joined_body = f"\\exo{{1}}{{{title_clean}}}\n\nÉnoncé préparé par le Skill /{skill}."

        return (
            f"{preamble}\n\n"
            "\\begin{document}\n\n"
            "\\begin{center}\n"
            f"  {{\\LARGE \\textbf{{{display_type} : {title_clean}}}}}\\\\[0.5em]\n"
            f"  {{\\large {classe_str}}}\n"
            "\\end{center}\n\n"
            f"{joined_body}\n\n"
            "\\end{document}\n"
        )

    def _collect_and_compile_task_artifacts(
        self,
        *,
        clean_prompt: str,
        answer_text: str,
        before_snapshot: dict[str, str],
        after_snapshot: dict[str, str],
        recorded_diffs: list[dict[str, Any]],
        agent: str = "",
        skill: str = "",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Détecte les fichiers HTML/LaTeX/PDF produits pendant la tâche, extrait les blocs HTML/LaTeX
        si l'utilisateur a demandé un livrable sans écriture d'outil, compile les .tex avec Tectonic
        et retourne (preview_artifacts, compilation_errors, updated_diffs)."""
        preview_artifacts: list[dict[str, Any]] = []
        compilation_errors: list[dict[str, Any]] = []
        can_write = not self.permissions.dry_run and self.mode_manager.current != HarnessMode.PLAN

        modified_paths = [d["path"] for d in recorded_diffs if d.get("status") != "D"]
        prompt_lower = clean_prompt.casefold()

        # 1. Si l'utilisateur demande explicitement une page/aperçu HTML ou que le modèle a produit du HTML/CSS/JS,
        # et qu'aucun fichier .html n'a été écrit par outil, enregistrer le vrai fichier dans le workspace (ex: index.html ou nom demandé)
        has_html_file = any(p.lower().endswith((".html", ".htm")) for p in modified_paths)
        wants_html = any(
            kw in prompt_lower
            for kw in (
                "html",
                "page web",
                "interface web",
                "tableau interactif",
                "dashboard",
                "aperçu web",
                "site web",
                "css",
                "javascript",
                "convertisseur",
            )
        )
        if not has_html_file and can_write and answer_text:
            html_match = re.search(r"```(?:html|htm)?\s*\r?\n([\s\S]*?)```", answer_text, re.IGNORECASE)
            candidate_code = html_match.group(1).strip() if html_match else ""
            if candidate_code and (
                wants_html
                or "<!doctype" in candidate_code.casefold()
                or "<html" in candidate_code.casefold()
                or "<div" in candidate_code.casefold()
                or "<body" in candidate_code.casefold()
            ):
                name_match = re.search(r"\b([a-zA-Z0-9_-]+\.html?)\b", clean_prompt, re.IGNORECASE)
                rel_html = name_match.group(1) if name_match else "index.html"
                try:
                    self.filesystem.write_file(rel_html, candidate_code, overwrite=True)
                    modified_paths.append(rel_html)
                    has_html_file = True
                except Exception:
                    pass
            elif wants_html and not has_html_file:
                if "<!doctype" in answer_text.casefold() or "<html" in answer_text.casefold():
                    rel_html = "index.html"
                    try:
                        self.filesystem.write_file(rel_html, answer_text.strip(), overwrite=True)
                        modified_paths.append(rel_html)
                        has_html_file = True
                    except Exception:
                        pass

        # 2. Détection des livrables LaTeX / PDF et des Skills d'éducation obligatoires (/exercice, /dm, /bacblanc)
        has_tex_file = any(p.lower().endswith(".tex") for p in modified_paths)
        has_pdf_file = any(p.lower().endswith(".pdf") for p in modified_paths)
        is_education_skill = (
            skill in ("bacblanc", "exercice", "dm")
            or bool(re.search(r"^/(?:bacblanc|exercice|dm)\b", clean_prompt.strip(), re.IGNORECASE))
        )
        wants_latex = is_education_skill or any(
            kw in prompt_lower
            for kw in ("latex", ".tex", "tectonic", "compile", "pdf", "bacblanc", "sujet", "exercice", "dm", "devoir maison")
        )

        # 2a. Si skill éducatif (/exercice, /dm, /bacblanc) et qu'aucun .tex n'a été produit,
        # obligatoirement générer le fichier .tex basé sur le gabarit officiel
        if is_education_skill and not has_tex_file and can_write and answer_text and not answer_text.startswith("⚠️"):
            stem = f"{skill}_maths" if skill in ("exercice", "dm") else "bacblanc_sujet"
            rel_tex = f"{stem}.tex"
            try:
                auto_tex = self._build_education_latex_document(skill or "exercice", clean_prompt, answer_text)
                self.filesystem.write_file(rel_tex, auto_tex, overwrite=True)
                modified_paths.append(rel_tex)
                has_tex_file = True
            except Exception as exc:
                compilation_errors.append(
                    {
                        "source_path": rel_tex,
                        "compiler": "template_validator",
                        "error": str(exc),
                        "log": str(exc),
                    }
                )

        if not has_tex_file and can_write and answer_text and (wants_latex or "\\documentclass" in answer_text):
            tex_match = re.search(r"```(?:latex|tex)\s*\r?\n([\s\S]*?)```", answer_text, re.IGNORECASE)
            if tex_match and ("\\documentclass" in tex_match.group(1) or "\\begin{document}" in tex_match.group(1)):
                tex_code = tex_match.group(1).strip()
                if tex_code:
                    name_match = re.search(r"\b([a-zA-Z0-9_-]+\.tex)\b", clean_prompt, re.IGNORECASE)
                    rel_tex = name_match.group(1) if name_match else f"generated/document_{uuid.uuid4().hex[:6]}.tex"
                    try:
                        self.filesystem.write_file(rel_tex, tex_code, overwrite=True)
                        modified_paths.append(rel_tex)
                        has_tex_file = True
                    except Exception:
                        pass
                        pass

        # 2b. Si l'utilisateur demande explicitement de créer/générer un PDF en langage naturel et qu'aucun .tex/.pdf n'a encore été produit,
        # convertir la réponse en document LaTeX propre et le compiler avec Tectonic
        wants_pdf_deliverable = bool(
            re.search(
                r"\b(crée|creer|créer|génère|generer|générer|fais|produis|rédige|redige|exporte)\b[\s\S]{0,40}\bpdf\b|\bdocument\s+pdf\b|\ben\s+pdf\b",
                prompt_lower,
            )
        )
        if wants_pdf_deliverable and not has_tex_file and not has_pdf_file and can_write and answer_text and not answer_text.startswith("⚠️"):
            name_match = re.search(r"\b([a-zA-Z0-9_-]+)\.pdf\b", clean_prompt, re.IGNORECASE)
            stem = name_match.group(1) if name_match else f"document_{uuid.uuid4().hex[:6]}"
            rel_tex = f"generated/{stem}.tex"
            try:
                auto_tex = self._markdown_to_latex_document(clean_prompt[:80], answer_text)
                self.filesystem.write_file(rel_tex, auto_tex, overwrite=True)
                modified_paths.append(rel_tex)
                has_tex_file = True
            except Exception:
                pass

        # 3. Compilation automatique avec Tectonic des fichiers .tex créés ou modifiés durant la tâche
        compiled_pdf_paths: set[str] = set()
        for rel_path in list(modified_paths):
            if rel_path.lower().endswith(".tex") and can_write:
                comp = self.compile_workspace_latex(rel_path, auto_repair=True)
                if comp.get("status") == "success" and comp.get("pdf_path"):
                    pdf_p = str(comp["pdf_path"])
                    compiled_pdf_paths.add(pdf_p)
                    preview_artifacts.append(
                        {
                            "type": "pdf",
                            "title": Path(pdf_p).name,
                            "path": pdf_p,
                            "pdf_path": pdf_p,
                            "source_path": str(comp.get("source_path") or rel_path),
                            "source_tex": str(comp.get("source_path") or rel_path),
                            "compiler": str(comp.get("compiler") or "tectonic"),
                            "pages": int(comp.get("pages") or 1),
                            "page_count": int(comp.get("pages") or 1),
                            "bytes": int(comp.get("bytes") or 0),
                            "size_bytes": int(comp.get("bytes") or 0),
                            "sha256": str(comp.get("sha256") or ""),
                            "repaired": bool(comp.get("repaired", False)),
                            "auto_repaired": bool(comp.get("repaired", False)),
                            "repair_notes": list(comp.get("repair_notes") or []),
                            "raw_url": f"/api/files/raw?path={quote(pdf_p)}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                else:
                    compilation_errors.append(
                        {
                            "source_path": rel_path,
                            "compiler": str(comp.get("compiler") or "tectonic"),
                            "error": str(comp.get("error") or "Échec de compilation LaTeX."),
                            "log": str(comp.get("log") or "")[-1500:],
                        }
                    )

        if is_education_skill and not compiled_pdf_paths and not compilation_errors:
            compilation_errors.append(
                {
                    "source_path": f"{skill}_maths.tex",
                    "compiler": "tectonic",
                    "error": f"La compilation Tectonic du livrable obligatoire pour /{skill} n'a produit aucun fichier PDF valide.",
                    "log": "Vérifiez la validité du document LaTeX ou l'installation de Tectonic.",
                }
            )

        # Recalculer les diffs si de nouveaux fichiers (.html, .tex, .pdf) ont été écrits
        latest_snapshot = self._snapshot_workspace()
        if latest_snapshot != after_snapshot:
            extra_diffs = self._record_workspace_diffs(
                after_snapshot,
                latest_snapshot,
                agent=agent or "NeoHarness Runtime",
                skill=skill,
                tool="tectonic" if compiled_pdf_paths else "write_file",
            )
            recorded_diffs.extend(extra_diffs)
            for d in extra_diffs:
                if d.get("status") != "D" and d["path"] not in modified_paths:
                    modified_paths.append(d["path"])

        # 4. Collecter les fichiers .pdf directs (ex: /export pdf) et les fichiers .html/.htm créés/modifiés
        for rel_path in modified_paths:
            lower_p = rel_path.lower()
            if lower_p.endswith(".pdf") and rel_path not in compiled_pdf_paths:
                try:
                    pdf_info = self.get_pdf_info(rel_path)
                    artifact_item = {
                        "type": "pdf",
                        "title": pdf_info["name"],
                        "path": pdf_info["path"],
                        "pdf_path": pdf_info["path"],
                        "source_path": "",
                        "compiler": "export",
                        "pages": pdf_info["pages"],
                        "bytes": pdf_info["bytes"],
                        "repaired": False,
                        "repair_notes": [],
                        "raw_url": pdf_info["raw_url"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    preview_artifacts.append(artifact_item)
                    self.event_bus.emit_normalized(
                        event="ARTIFACT_READY",
                        raw_event="artifact.ready",
                        summary=f"Document PDF généré : {pdf_info['path']}",
                        status="completed",
                        details=artifact_item,
                    )
                except Exception:
                    pass
            elif lower_p.endswith((".html", ".htm")):
                try:
                    if can_write:
                        comp = self.compile_workspace_html(rel_path, auto_repair=True)
                        if comp.get("status") == "success":
                            preview_artifacts.append(
                                {
                                    "type": "html",
                                    "title": Path(rel_path).name,
                                    "path": rel_path,
                                    "size_bytes": int(comp.get("bytes") or comp.get("size_bytes") or 0),
                                    "bytes": int(comp.get("bytes") or comp.get("size_bytes") or 0),
                                    "preview_url": f"/api/preview/workspace/{quote(rel_path)}",
                                    "raw_url": f"/api/files/raw?path={quote(rel_path)}",
                                    "repaired": bool(comp.get("repaired", False)),
                                    "auto_repaired": bool(comp.get("repaired", False)),
                                    "repair_notes": list(comp.get("repair_notes") or []),
                                    "scripts_checked": int(comp.get("scripts_checked") or 0),
                                    "styles_checked": int(comp.get("styles_checked") or 0),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                        else:
                            compilation_errors.append(
                                {
                                    "source_path": rel_path,
                                    "compiler": "html_compiler",
                                    "error": str(comp.get("error") or "Échec de validation/compilation HTML."),
                                    "log": str(comp.get("log") or "")[-1500:],
                                }
                            )
                    else:
                        full_html = self.filesystem.resolve(rel_path)
                        html_content = self.filesystem.read_file(rel_path)
                        if full_html.is_file() and html_content.strip():
                            artifact_item = {
                                "type": "html",
                                "title": full_html.name,
                                "path": rel_path,
                                "bytes": full_html.stat().st_size,
                                "preview_url": f"/api/preview/workspace/{quote(rel_path)}",
                                "raw_url": f"/api/files/raw?path={quote(rel_path)}",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            preview_artifacts.append(artifact_item)
                            self.event_bus.emit_normalized(
                                event="ARTIFACT_READY",
                                raw_event="artifact.ready",
                                summary=f"Aperçu HTML prêt : {rel_path}",
                                status="completed",
                                details=artifact_item,
                            )
                except Exception:
                    pass

        return preview_artifacts, compilation_errors, recorded_diffs

    # ------------------------------------------------------------------
    # MEMORY & RAG
    # ------------------------------------------------------------------

    def get_memory_state(self, *, query: str = "") -> dict[str, Any]:
        needle = query.strip().casefold()

        def _filter_list(items: list[str]) -> list[str]:
            if not needle:
                return list(items)
            return [item for item in items if needle in item.casefold()]

        prefs = {
            k: v
            for k, v in self.memory.preferences.items()
            if not needle or needle in k.casefold() or needle in str(v).casefold()
        }
        return {
            "session": _filter_list(self.memory.session),
            "project": _filter_list(self.memory.project),
            "project_path": f"workspace/{self.memory.PROJECT_PATH}",
            "decisions": _filter_list(self.memory.decisions),
            "preferences": prefs,
            "task_memory": self.orchestrator.context.mission_memory or None,
            "long_term": {
                "configured": False,
                "status": "Non configuré",
                "detail": "Aucune base de mémoire long-terme externe n'est configurée dans le projet.",
            },
            "procedural": {
                "configured": False,
                "status": "Non configuré",
                "detail": "Les procédures métier sont portées par les manifestes skill.md et rules.md.",
            },
        }

    def mutate_memory(self, action: str, scope: str = "session", value: str = "") -> dict[str, Any]:
        act = action.strip().casefold()
        if act == "clear_session":
            self.memory.clear_session()
            return {"message": "Mémoire de session effacée ; notes projet conservées.", "memory": self.get_memory_state()}
        if act == "remember":
            msg = self.memory.remember(scope.strip().casefold(), value)
            return {"message": msg, "memory": self.get_memory_state()}
        raise ValueError(f"Action mémoire inconnue : {action}")

    def get_rag_state(self, *, query: str = "") -> dict[str, Any]:
        """Inspecte réellement les collections RAG des Skills, les templates et les documents du workspace."""
        collections: list[dict[str, Any]] = []
        all_documents: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []

        for descriptor in self.orchestrator.skill_registry.list_skills():
            try:
                definition = self.orchestrator.skill_loader.load(descriptor)
            except Exception:
                continue

            rag_docs = []
            for path in definition.rag_resources:
                rel = path.relative_to(definition.rag_path).as_posix() if definition.rag_path else path.name
                extracted_text = definition.rag_contents.get(rel, "")
                doc_entry = {
                    "name": path.name,
                    "path": f"skills/{definition.name}/rag/{rel}",
                    "collection": f"Skill /{definition.name} — RAG",
                    "skill": definition.name,
                    "type": "RAG Resource",
                    "characters": len(extracted_text),
                    "preview": extracted_text[:400],
                }
                rag_docs.append(doc_entry)
                all_documents.append(doc_entry)

            tpl_docs = []
            for path in definition.available_templates:
                rel = path.name
                extracted_text = definition.template_contents.get(rel, "")
                doc_entry = {
                    "name": path.name,
                    "path": f"skills/{definition.name}/templates/{rel}",
                    "collection": f"Skill /{definition.name} — Templates",
                    "skill": definition.name,
                    "type": "Template de production",
                    "characters": len(extracted_text),
                    "preview": extracted_text[:400],
                }
                tpl_docs.append(doc_entry)
                all_documents.append(doc_entry)

            if rag_docs or tpl_docs or definition.name == "bacblanc":
                collections.append(
                    {
                        "id": f"skill:{definition.name}",
                        "name": f"/{definition.name} ({definition.display_name})",
                        "rag_path": f"skills/{definition.name}/rag",
                        "rag_count": len(rag_docs),
                        "templates_count": len(tpl_docs),
                        "rag_documents": rag_docs,
                        "templates": tpl_docs,
                        "errors": definition.resource_errors,
                    }
                )

        # Documents présents dans le workspace
        ws_docs: list[dict[str, Any]] = []
        for rel in self.filesystem.list_files(".", recursive=True):
            if rel.startswith(".harness/"):
                continue
            ws_entry = {
                "name": Path(rel).name,
                "path": f"workspace/{rel}",
                "collection": "Workspace Local",
                "skill": "",
                "type": f"Fichier ({Path(rel).suffix or 'texte'})",
                "characters": self.filesystem.resolve(rel).stat().st_size,
                "preview": "",
            }
            ws_docs.append(ws_entry)
            all_documents.append(ws_entry)

        collections.append(
            {
                "id": "workspace",
                "name": "Workspace Local",
                "rag_path": "workspace/",
                "rag_count": len(ws_docs),
                "templates_count": 0,
                "rag_documents": ws_docs,
                "templates": [],
                "errors": {},
            }
        )

        # Recherche réelle si query est fournie
        search_hits: list[dict[str, Any]] = []
        needle = query.strip()
        if needle:
            self.event_bus.emit_normalized(
                event="RAG_SEARCH",
                raw_event="rag.search",
                summary=f"Recherche documentaire RAG & Workspace : '{needle}'",
                status="completed",
                details={"query": needle},
            )
            # 1. Recherche dans le workspace
            try:
                for hit in self.filesystem.search_files(needle, limit=25):
                    search_hits.append(
                        {
                            "source": f"workspace/{hit['path']}",
                            "line": hit["line"],
                            "snippet": hit["text"],
                            "collection": "Workspace Local",
                        }
                    )
            except Exception:
                pass
            # 2. Recherche dans les contenus RAG et Templates des Skills
            lowered_needle = needle.casefold()
            for col in collections:
                for doc in col.get("rag_documents", []) + col.get("templates", []):
                    if doc["collection"] == "Workspace Local":
                        continue
                    skill_name = doc.get("skill")
                    if not skill_name:
                        continue
                    desc = self.orchestrator.skill_registry.get(skill_name)
                    if not desc:
                        continue
                    try:
                        defn = self.orchestrator.skill_loader.load(desc)
                        merged = {**defn.rag_contents, **defn.template_contents}
                        for fname, text_body in merged.items():
                            for idx, line in enumerate(text_body.splitlines(), 1):
                                if lowered_needle in line.casefold():
                                    search_hits.append(
                                        {
                                            "source": f"skills/{skill_name}/{fname}",
                                            "line": idx,
                                            "snippet": line[:300],
                                            "collection": col["name"],
                                        }
                                    )
                                    if len(search_hits) >= 40:
                                        break
                    except Exception:
                        continue

        # Sources réellement consultées durant la session
        if self.orchestrator.context.skill_rag_resources:
            for res in self.orchestrator.context.skill_rag_resources:
                sources.append({"type": "RAG Skill", "reference": res})
        if self.orchestrator.context.skill_templates:
            for tpl in self.orchestrator.context.skill_templates:
                sources.append({"type": "Template Skill", "reference": tpl})
        for fpath in self.orchestrator.context.files:
            sources.append({"type": "Fichier Workspace", "reference": fpath})

        return {
            "knowledge_status": "Actif (RAG documentaire de Skills + extraction Workspace)",
            "embeddings": {
                "configured": False,
                "status": "Non configuré",
                "detail": (
                    "Aucun moteur d'embeddings vectoriels n'est configuré. "
                    "Le RAG fonctionne par extraction documentaire directe (SkillLoader + read_document) "
                    "et recherche lexicale confinée (search_files)."
                ),
            },
            "collections": collections,
            "documents": all_documents,
            "active_sources": sources,
            "search_query": needle,
            "search_results": search_hits,
        }

    # ------------------------------------------------------------------
    # EXÉCUTION D'UNE TÂCHE / MISSION
    # ------------------------------------------------------------------

    def execute_task(
        self,
        prompt: str,
        *,
        conversation_id: str | None = None,
        attached_files: list[str] | None = None,
        explicit_skill: str | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """Exécute une requête utilisateur à travers le pipeline réel de NeoHarness AI."""
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            raise ValueError("La requête ne peut pas être vide.")

        conv = self.get_conversation(conversation_id)
        if model_id:
            self.select_model(model_id)

        # Si un Skill est sélectionné manuellement et que le prompt ne commence pas déjà par /
        active_skills = list(self.generation_preferences.get("active_skills", []))
        chosen_skill = explicit_skill or (active_skills[0] if active_skills else None)
        effective_prompt = clean_prompt
        if chosen_skill and not effective_prompt.startswith("/"):
            skill_norm = chosen_skill.strip().lstrip("/").casefold()
            if self.orchestrator.skill_registry.get(skill_norm) is not None:
                effective_prompt = f"/{skill_norm} {effective_prompt}"

        # Si des fichiers du workspace sont joints au composer, on les indique proprement et on précharge leur extrait réel
        attachments = [f for f in (attached_files or []) if isinstance(f, str) and f.strip()]
        if attachments and not effective_prompt.startswith(("/mode", "/model", "/context", "/diagnostic", "/memory", "/export")):
            files_clause = ", ".join(attachments)
            snippets: list[str] = []
            for att in attachments[:5]:
                try:
                    ext = Path(att).suffix.lower()
                    if ext in {".pdf", ".docx", ".xlsx", ".pptx"}:
                        doc = read_document(att, filesystem=self.filesystem)
                        txt = str(doc.get("text") or "").strip()
                        if txt:
                            self.orchestrator.context.remember_file(att, txt[:4000])
                            snippets.append(f"--- Contenu extrait de {att} ---\n{txt[:2500]}")
                    elif ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
                        st = self.filesystem.resolve(att).stat()
                        snippets.append(f"--- Image jointe : {att} ({st.st_size} octets) ---")
                    else:
                        txt = self.filesystem.read_file(att).strip()
                        if txt:
                            self.orchestrator.context.remember_file(att, txt[:4000])
                            snippets.append(f"--- Contenu de {att} ---\n{txt[:2500]}")
                except Exception:
                    pass
            effective_prompt = f"{effective_prompt}\n\n[Fichiers du workspace joints : {files_clause}]"
            if snippets:
                effective_prompt = f"{effective_prompt}\n\n" + "\n\n".join(snippets)

        self._task_approved_tools.clear()
        self._stop_requested = False
        self.agent_loop._stop_requested = False
        started_mono = monotonic()

        task_id = self.event_bus.start_task(
            objective=clean_prompt,
            skill=chosen_skill or "",
            mode=self.mode_manager.current.value,
        )
        self.current_task_id = task_id
        self.current_task_status = "Planification"

        # Ajout du message utilisateur dans la conversation
        user_msg = {
            "id": f"msg-{uuid.uuid4().hex[:8]}",
            "role": "user",
            "content": clean_prompt,
            "effective_prompt": effective_prompt,
            "attachments": attachments,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conv["messages"].append(user_msg)
        if conv["title"] == "Nouvelle tâche" and len(conv["messages"]) == 1:
            conv["title"] = clean_prompt[:52] + ("…" if len(clean_prompt) > 52 else "")

        # Snapshot des fichiers du workspace avant exécution pour calcul de diff réel
        before_snapshot = self._snapshot_workspace()

        # 1. Événements de contexte et mémoire
        self.event_bus.emit_normalized(
            event="CONTEXT_LOADING",
            raw_event="context.loading",
            summary=f"Chargement du contexte ({len(self.orchestrator.context.history)} entrées, {len(attachments)} fichier(s) joint(s))",
            status="completed",
            details={"history_count": len(self.orchestrator.context.history), "attachments": attachments},
        )
        if self.memory.session or self.memory.project or self.memory.decisions:
            self.event_bus.emit_normalized(
                event="MEMORY_RETRIEVAL",
                raw_event="memory.retrieval",
                summary=f"Mémoire active consultée ({len(self.memory.session)} session, {len(self.memory.project)} projet)",
                status="completed",
            )

        # 2. Planification uniquement si la requête n'est pas une commande système locale directe
        local_only_prefixes = ("/export", "/model", "/mode", "/memory", "/diagnostic", "/context")
        is_local_command = effective_prompt.strip().casefold().startswith(local_only_prefixes)
        planned_state: TaskState | None = None
        if not is_local_command:
            self.event_bus.emit_normalized(
                event="PLANNER_STARTED",
                raw_event="planner.started",
                summary="Analyse de l'intention et construction du plan d'exécution",
                status="running",
            )
            preview_task = Task(description=clean_prompt, mode=self.mode_manager.current.value)
            try:
                planned_state = self.agent_loop.planner.plan(preview_task)
            except ClarificationRequired:
                planned_state = TaskState(
                    user_request=clean_prompt,
                    mode=self.mode_manager.current.value,
                    intent="general_question",
                    complexity="simple",
                    objective=clean_prompt,
                    assigned_agent="researcher",
                    plan=[PlanStep("Clarifier la demande avec l'utilisateur.", agent="researcher")],
                )
            self.event_bus.emit_normalized(
                event="PLAN_CREATED",
                raw_event="planner.created",
                summary=f"Plan créé : intention '{planned_state.intent}' ({len(planned_state.plan)} étapes)",
                status="completed",
                details={
                    "intent": planned_state.intent,
                    "complexity": planned_state.complexity,
                    "steps": [step.description for step in planned_state.plan],
                    "required_tools": planned_state.intent_decision.get("required_tools", []),
                },
            )

        # 3. Exécution réelle via la logique de mission (_executer_mission compatible)
        self.current_task_status = "Exécution"
        captured_stdout = io.StringIO()
        result_obj: AgentResult | None = None
        answer_text = ""
        error_text = ""
        used_skill = ""
        used_agent = ""
        used_provider = ""
        used_model = ""
        used_tools: list[str] = []
        used_sources: list[dict[str, str]] = []
        verification_summary = ""

        try:
            self._ensure_routed_providers_ready()
            with contextlib.redirect_stdout(captured_stdout):
                result_obj, used_skill, used_agent = self._dispatch_mission(effective_prompt)
        except Exception as error:
            error_text = f"{type(error).__name__}: {error}"
            self.event_bus.emit_normalized(
                event="ERROR",
                raw_event="task.error",
                summary=f"Erreur pendant l'exécution : {error_text}",
                status="error",
                error=error_text,
            )

        stdout_text = captured_stdout.getvalue().strip()

        if result_obj is not None:
            answer_text = (result_obj.answer or result_obj.summary or stdout_text).strip()
            used_agent = used_agent or (planned_state.assigned_agent if planned_state else "") or ""
            used_tools = [
                str(obs.get("tool", ""))
                for obs in (result_obj.observations or [])
                if isinstance(obs, dict) and obs.get("kind") == "tool_result" and obs.get("tool")
            ]
            if not used_tools:
                used_tools = [
                    str(obs.get("tool", ""))
                    for obs in (result_obj.observations or [])
                    if isinstance(obs, dict) and obs.get("tool")
                ]
            for obs in (result_obj.observations or []):
                if isinstance(obs, dict) and obs.get("kind") == "source" and obs.get("url"):
                    source_item = {
                        "title": str(obs.get("title") or obs.get("url")),
                        "url": str(obs.get("url")),
                        "snippet": str(obs.get("snippet") or ""),
                        "source": str(obs.get("source") or ""),
                        "published_at": str(obs.get("published_at") or ""),
                    }
                    if source_item not in used_sources:
                        used_sources.append(source_item)
            if result_obj.verification and isinstance(result_obj.verification, dict):
                verification_summary = str(
                    result_obj.verification.get("summary")
                    or result_obj.verification.get("status")
                    or "vérifié"
                )
            if result_obj.errors and not error_text:
                error_text = "; ".join(
                    str(e.get("message") if isinstance(e, dict) else e)
                    for e in result_obj.errors
                )
        else:
            answer_text = stdout_text

        # Modèle effectivement sollicité
        if not is_local_command:
            last_prov_key = self.orchestrator.router.last_provider_key or self.orchestrator.router.session_provider_key
            if last_prov_key and last_prov_key in self.orchestrator.router.providers:
                prov_inst = self.orchestrator.router.providers[last_prov_key]
                used_provider = prov_inst.get_name()
                used_model = prov_inst.get_model_name()

        if not answer_text and error_text:
            answer_text = (
                f"⚠️ **Exécution interrompue**\n\n"
                f"Cause : `{error_text}`\n\n"
                f"Vérifiez la disponibilité du modèle (`{used_provider or 'Provider'}` / `{used_model or 'Modèle'}`) "
                f"ou configurez la clé API correspondante dans **Paramètres (⚙)**."
            )

        after_snapshot = self._snapshot_workspace()
        recorded_diffs = self._record_workspace_diffs(
            before_snapshot,
            after_snapshot,
            agent=used_agent,
            skill=used_skill,
            tool=used_tools[-1] if used_tools else "",
        )
        preview_artifacts, compilation_errors, recorded_diffs = self._collect_and_compile_task_artifacts(
            clean_prompt=clean_prompt,
            answer_text=answer_text,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            recorded_diffs=recorded_diffs,
            agent=used_agent,
            skill=used_skill,
        )

        elapsed_ms = int((monotonic() - started_mono) * 1000)
        is_education_skill = (used_skill or "").lower() in {"dm", "exercice", "bacblanc"}
        is_html_error = any(e.get("compiler") == "html_compiler" for e in compilation_errors)
        if error_text and (result_obj is None or result_obj.status == "failed"):
            final_status = "Erreur"
        elif compilation_errors and (is_education_skill or is_html_error):
            final_status = "Erreur"
            if not error_text:
                error_text = compilation_errors[0].get("error", "Échec de compilation.")
        elif result_obj is not None and result_obj.status in {"incomplete", "clarification_required"}:
            final_status = "Partiel"
        else:
            final_status = "Terminé"
        self.current_task_status = final_status

        self.event_bus.complete_task(
            status="error" if final_status == "Erreur" else ("partial" if final_status == "Partiel" else "completed"),
            duration_ms=elapsed_ms,
            summary=f"Tâche terminée en {elapsed_ms} ms ({final_status})",
            error=error_text,
            details={
                "agent": used_agent,
                "skill": used_skill,
                "provider": used_provider,
                "model": used_model,
                "tools_used": used_tools,
                "sources_count": len(used_sources),
                "files_modified": [d["path"] for d in recorded_diffs],
                "preview_artifacts_count": len(preview_artifacts),
            },
        )

        assistant_msg = {
            "id": f"msg-{uuid.uuid4().hex[:8]}",
            "role": "assistant",
            "content": answer_text,
            "runtime_logs": stdout_text if result_obj is not None else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": task_id,
            "status": final_status,
            "duration_ms": elapsed_ms,
            "agent": used_agent,
            "skill": used_skill,
            "provider": used_provider,
            "model": used_model,
            "intent": planned_state.intent if planned_state else "local_command",
            "plan_steps": [s.description for s in planned_state.plan] if planned_state else [],
            "tools_used": used_tools,
            "sources": used_sources,
            "files_modified": recorded_diffs,
            "preview_artifacts": preview_artifacts,
            "compilation_errors": compilation_errors,
            "verification": verification_summary,
            "events": self.event_bus.list_events(task_id=task_id),
        }
        conv["messages"].append(assistant_msg)
        conv["updated_at"] = assistant_msg["timestamp"]
        self._save_conversations()

        return {
            "task_id": task_id,
            "status": final_status,
            "conversation": conv,
            "user_message": user_msg,
            "assistant_message": assistant_msg,
            "diffs": recorded_diffs,
            "preview_artifacts": preview_artifacts,
            "compilation_errors": compilation_errors,
        }

    def stop_active_task(self) -> dict[str, Any]:
        """Interrompt immédiatement la tâche ou l'itération en cours de l'agent."""
        self._stop_requested = True
        self.agent_loop._stop_requested = True
        self.current_task_status = "Arrêté"
        self.event_bus.emit_normalized(
            event="TASK_STOPPED",
            raw_event="task.stopped",
            summary="Arrêt demandé par l'utilisateur",
            status="cancelled",
        )
        return {"ok": True, "task_id": self.current_task_id, "status": "Arrêté"}

    def _dispatch_mission(self, prompt: str) -> tuple[AgentResult | None, str, str]:
        """Exécute la mission en respectant exactement la logique de main._executer_mission."""
        runtime = SkillRuntime(
            orchestrator=self.orchestrator,
            agent_loop=self.agent_loop,
            settings=self.settings,
            mode="api",
            args=None,
            memory=self.memory,
            mode_manager=self.mode_manager,
        )

        self.event_bus.emit_normalized(
            event="SKILL_DISCOVERY",
            raw_event="skill.discovery",
            summary=f"Inspection du registre de Skills ({len(self.orchestrator.skill_registry.names)} Skills disponibles)",
            status="completed",
        )

        direct_agent_task: Task | None = None
        try:
            launch = self.orchestrator.skill_router.resolve(prompt)
        except SkillCommandError as error:
            command = None
            try:
                command = self.orchestrator.skill_router.parse(prompt)
            except SkillCommandError:
                command = None
            if command is None:
                raise
            try:
                _agent_key, direct_agent = self.orchestrator.agent_registry.resolve(command.name)
            except KeyError:
                raise error from None
            if not command.mission.strip():
                raise SkillCommandError(f"Décris la mission après /{command.name}.") from None
            direct_agent_task = Task(
                description=command.mission.strip(),
                type=direct_agent.routing_key,
                explicit_agent=True,
                mode=self.mode_manager.current.value,
            )
            launch = None

        if launch is not None:
            skill = launch.skill
            mission_body = launch.command.mission
            self.orchestrator.context.last_skill = skill.name
            self.orchestrator.context.skill_rag_resources = sorted(skill.rag_contents)
            self.orchestrator.context.skill_templates = sorted(skill.template_contents)
            self.agent_loop._event(
                "skill.loaded",
                skill=skill.name,
                rag_count=len(skill.rag_resources),
                templates=[path.name for path in skill.available_templates],
            )
            if skill.rag_resources or skill.available_templates:
                self.event_bus.emit_normalized(
                    event="RAG_SEARCH",
                    raw_event="skill.rag_loaded",
                    summary=f"Ressources de /{skill.name} chargées : {len(skill.rag_resources)} RAG, {len(skill.available_templates)} template(s)",
                    skill=skill.name,
                    status="completed",
                )

            if skill.command_handler is not None:
                res = skill.command_handler(runtime, mission_body, skill)
                if isinstance(res, AgentResult):
                    return res, skill.name, skill.dispatch_agent or "Auto"
                return None, skill.name, "Runtime Local"

            if not mission_body.strip():
                raise SkillCommandError(f"Usage : /{skill.name} <mission>.")

            if skill.agent is not None:
                skill_task = Task(
                    description=mission_body,
                    type=skill.agent.routing_key,
                    explicit_agent=True,
                    instructions="\n\n".join(part for part in (skill.instructions, skill.rules) if part),
                    allowed_tools=tuple(skill.tools),
                    skill_name=skill.name,
                    skill=skill,
                    mode=self.mode_manager.current.value,
                )
                res = self.orchestrator.run_agentic(skill_task, self.agent_loop)
                return res, skill.name, skill.agent.name

            if skill.dispatch_agent is not None or skill.config.get("auto_route"):
                res = runtime.run_task(
                    mission_body,
                    agent_key=skill.dispatch_agent,
                    instructions=str(skill.config.get("task_instructions", "")),
                    allowed_tools=skill.tools,
                    automatic=bool(skill.config.get("auto_route")),
                    skill=skill,
                )
                return res, skill.name, skill.dispatch_agent or "Auto"

            raise SkillCommandError(f"/{skill.name} ne définit ni command.py ni agent exécutable.")

        # Requête standard (sans slash command de Skill)
        if direct_agent_task is not None:
            task = direct_agent_task
        else:
            known_agents = set(self.orchestrator.agent_registry.agents) | set(self.orchestrator.agent_registry.aliases)
            prefix, separator, description = prompt.partition(":")
            agent_type = prefix.strip().lower()
            if separator and agent_type in known_agents and description.strip():
                resolved_key, _ = self.orchestrator.agent_registry.resolve(agent_type)
                task = Task(
                    description=description.strip(),
                    type=resolved_key,
                    explicit_agent=True,
                    mode=self.mode_manager.current.value,
                )
            else:
                task = Task(
                    description=prompt.strip(),
                    type="researcher",
                    mode=self.mode_manager.current.value,
                )
        try:
            res = self.orchestrator.run_agentic(task, self.agent_loop)
        except ClarificationRequired as error:
            res = AgentResult(
                status="clarification_required",
                answer=f"Clarification nécessaire : {error}",
                summary=str(error),
            )
        return res, "", task.type

    # ------------------------------------------------------------------
    # RECHERCHE GLOBALE (Ctrl+K) & ÉTAT COMPLET DE L'UI
    # ------------------------------------------------------------------

    def global_search(self, query: str) -> dict[str, Any]:
        needle = (query or "").strip()
        lowered = needle.casefold()
        convs = self.list_conversations(query=needle)[:10]
        all_skills = self.skill_compatibility.evaluate_for_model()["skills"]
        if not needle:
            return {
                "query": "",
                "conversations": self.list_conversations()[:5],
                "skills": all_skills[:6],
                "agents": self.list_agents(),
                "tools": self.list_tools()[:6],
                "models": [m.to_dict() for m in self.model_registry.list_models()],
                "files": self.list_workspace_files()["files"][:6],
                "memory": [],
            }
        skills = [
            s for s in all_skills
            if lowered in s["name"].casefold()
            or lowered in s["display_name"].casefold()
            or lowered in s["description"].casefold()
            or any(lowered in tag.casefold() for tag in s.get("domain_tags", []))
        ]
        agents = [
            a for a in self.list_agents()
            if lowered in a["name"].casefold()
            or lowered in a["role"].casefold()
            or lowered in a["description"].casefold()
        ]
        tools = [
            t for t in self.list_tools()
            if lowered in t["name"].casefold() or lowered in t["description"].casefold()
        ]
        models = [
            m.to_dict()
            for m in self.model_registry.list_models()
            if lowered in m.display_name.casefold()
            or lowered in m.model_name.casefold()
            or lowered in m.provider_family.casefold()
        ]
        files = [
            f for f in self.list_workspace_files()["files"]
            if lowered in f["path"].casefold()
        ]
        mem_state = self.get_memory_state(query=needle)
        mem_hits = (
            [{"scope": "session", "text": x} for x in mem_state["session"]]
            + [{"scope": "project", "text": x} for x in mem_state["project"]]
            + [{"scope": "decision", "text": x} for x in mem_state["decisions"]]
        )
        return {
            "query": needle,
            "conversations": convs,
            "skills": skills,
            "agents": agents,
            "tools": tools,
            "models": models,
            "files": files,
            "memory": mem_hits,
        }

    def get_full_state(self, *, selected_model: str | None = None) -> dict[str, Any]:
        selection = self.model_registry.active_selection_summary()
        target_model = selected_model or selection.get("selected_id") or "auto"
        compatibility = self.skill_compatibility.evaluate_for_model(target_model)
        ctx = self.orchestrator.context
        mgr = self.orchestrator.context_manager

        return {
            "app_name": "NeoHarness AI",
            "subtitle": "AI Agent Operating Environment",
            "creator": "Djamel BENMAKHLOUF",
            "author": "Djamel BENMAKHLOUF",
            "current_time": datetime.now(timezone.utc).isoformat(),
            "local_time_display": datetime.now().strftime("%A %d %B %Y, %H:%M:%S"),
            "task_status": self.current_task_status,
            "current_task_id": self.current_task_id,
            "mode": {
                "current": self.mode_manager.current.value,
                "description": ModeManager.DESCRIPTIONS[self.mode_manager.current],
                "short_description": ModeManager.SHORT_DESCRIPTIONS[self.mode_manager.current],
                "available_modes": [
                    {
                        "id": m.value,
                        "description": ModeManager.DESCRIPTIONS[m],
                        "short_description": ModeManager.SHORT_DESCRIPTIONS[m],
                    }
                    for m in ModeManager.CYCLE
                ],
            },
            "preferences": dict(self.generation_preferences),
            "credentials": self.get_credentials_status(),
            "model_selection": selection,
            "models": [m.to_dict() for m in self.model_registry.list_models()],
            "compatibility": compatibility,
            "projects": self.list_projects(),
            "conversations": self.list_conversations(),
            "active_conversation": self.get_conversation(),
            "agents": self.list_agents(),
            "tools": self.list_tools(),
            "context": {
                "history_entries": len(ctx.history),
                "history_characters": sum(len(x) for x in ctx.history),
                "tracked_files": list(ctx.files),
                "last_result_length": len(ctx.last_result),
                "max_items": mgr.max_items,
                "max_characters": mgr.max_characters,
                "last_skill": ctx.last_skill or "aucun",
                "skill_rag_resources": list(ctx.skill_rag_resources),
                "skill_templates": list(ctx.skill_templates),
                "mission_memory": ctx.mission_memory or None,
            },
            "workspace": self.list_workspace_files(),
            "memory": self.get_memory_state(),
            "rag": self.get_rag_state(),
            "pending_approvals": self.list_pending_approvals(),
            "events": self.event_bus.list_events(limit=150),
        }


class NeoHarnessUIApp:
    """Façade applicative exposant les routes REST/JSON de l'interface."""

    def __init__(self, bridge: NeoHarnessRuntimeBridge | None = None) -> None:
        self.bridge = bridge or NeoHarnessRuntimeBridge()

    def handle_api_get(self, path: str, query_params: dict[str, list[str]]) -> tuple[int, dict[str, Any]]:
        def _first(key: str, default: str = "") -> str:
            vals = query_params.get(key)
            return vals[0] if vals else default

        if path == "/api/state":
            model_param = _first("model") or None
            return HTTPStatus.OK, self.bridge.get_full_state(selected_model=model_param)
        if path == "/api/models":
            return HTTPStatus.OK, {
                "selection": self.bridge.model_registry.active_selection_summary(),
                "models": [m.to_dict() for m in self.bridge.model_registry.list_models()],
            }
        if path == "/api/skills":
            model_param = _first("model") or None
            return HTTPStatus.OK, self.bridge.skill_compatibility.evaluate_for_model(model_param)
        if path == "/api/agents":
            return HTTPStatus.OK, {"agents": self.bridge.list_agents()}
        if path == "/api/tools":
            return HTTPStatus.OK, {"tools": self.bridge.list_tools()}
        if path == "/api/projects":
            return HTTPStatus.OK, {"projects": self.bridge.list_projects()}
        if path == "/api/conversations":
            q = _first("q")
            return HTTPStatus.OK, {
                "conversations": self.bridge.list_conversations(query=q),
                "active_id": self.bridge.active_conversation_id,
            }
        if path == "/api/files":
            return HTTPStatus.OK, self.bridge.list_workspace_files()
        if path == "/api/files/content":
            rel = _first("path")
            if not rel:
                return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'path' requis."}
            try:
                return HTTPStatus.OK, self.bridge.read_workspace_file(rel)
            except FileNotFoundError as error:
                return HTTPStatus.NOT_FOUND, {"error": str(error)}
            except Exception as error:
                return HTTPStatus.BAD_REQUEST, {"error": str(error)}
        if path == "/api/files/pdf-info":
            rel = _first("path")
            if not rel:
                return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'path' requis."}
            try:
                return HTTPStatus.OK, self.bridge.get_pdf_info(rel)
            except FileNotFoundError as error:
                return HTTPStatus.NOT_FOUND, {"error": str(error)}
            except Exception as error:
                return HTTPStatus.BAD_REQUEST, {"error": str(error)}
        if path == "/api/memory":
            q = _first("q")
            return HTTPStatus.OK, self.bridge.get_memory_state(query=q)
        if path == "/api/rag":
            q = _first("q")
            return HTTPStatus.OK, self.bridge.get_rag_state(query=q)
        if path == "/api/events":
            tid = _first("task_id") or None
            return HTTPStatus.OK, {"events": self.bridge.event_bus.list_events(task_id=tid)}
        if path == "/api/search":
            q = _first("q")
            return HTTPStatus.OK, self.bridge.global_search(q)
        if path == "/api/approvals":
            return HTTPStatus.OK, {"approvals": self.bridge.list_pending_approvals()}
        if path == "/api/credentials":
            return HTTPStatus.OK, {"credentials": self.bridge.get_credentials_status()}

        return HTTPStatus.NOT_FOUND, {"error": f"Route GET inconnue : {path}"}

    def handle_api_post(self, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            if path == "/api/credentials":
                return HTTPStatus.OK, self.bridge.update_credentials(body)

            if path == "/api/models/select":
                model_id = str(body.get("model") or "auto")
                return HTTPStatus.OK, self.bridge.select_model(model_id)

            if path == "/api/mode":
                mode_name = str(body.get("mode") or "")
                return HTTPStatus.OK, self.bridge.set_mode(mode_name)

            if path == "/api/preferences":
                return HTTPStatus.OK, {"preferences": self.bridge.update_preferences(body)}

            if path == "/api/conversations/create":
                title = str(body.get("title") or "Nouvelle tâche")
                project = str(body.get("project") or "NeoHarness AI")
                conv = self.bridge.create_conversation(title=title, project=project)
                return HTTPStatus.OK, {"conversation": conv, "conversations": self.bridge.list_conversations()}

            if path == "/api/conversations/select":
                cid = str(body.get("id") or "")
                conv = self.bridge.get_conversation(cid)
                self.bridge.active_conversation_id = conv["id"]
                return HTTPStatus.OK, {"conversation": conv}

            if path == "/api/conversations/update":
                cid = str(body.get("id") or "")
                conv = self.bridge.update_conversation(
                    cid,
                    title=body.get("title"),
                    pinned=body.get("pinned"),
                    archived=body.get("archived"),
                )
                return HTTPStatus.OK, {"conversation": conv, "conversations": self.bridge.list_conversations()}

            if path == "/api/conversations/delete":
                cid = str(body.get("id") or "")
                removed = self.bridge.delete_conversation(cid)
                return HTTPStatus.OK, {
                    "deleted": removed,
                    "conversations": self.bridge.list_conversations(),
                    "active_conversation": self.bridge.get_conversation(),
                }

            if path == "/api/tasks/run":
                prompt = str(body.get("prompt") or "")
                cid = body.get("conversation_id")
                attachments = body.get("attachments") or []
                skill = body.get("skill")
                model_id = body.get("model")
                result = self.bridge.execute_task(
                    prompt,
                    conversation_id=cid,
                    attached_files=attachments,
                    explicit_skill=skill,
                    model_id=model_id,
                )
                return HTTPStatus.OK, result

            if path == "/api/tasks/stop":
                res = self.bridge.stop_active_task()
                return HTTPStatus.OK, res

            if path == "/api/approvals/resolve":
                approval_id = str(body.get("id") or "")
                decision = str(body.get("decision") or "deny")
                resolved = self.bridge.resolve_approval(approval_id, decision)
                return HTTPStatus.OK, {"approval": resolved}

            if path == "/api/memory":
                action = str(body.get("action") or "remember")
                scope = str(body.get("scope") or "session")
                value = str(body.get("value") or "")
                return HTTPStatus.OK, self.bridge.mutate_memory(action, scope, value)

            if path == "/api/files/compile-html":
                html_path = str(body.get("path") or "").strip()
                if not html_path:
                    return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'path' requis."}
                if body.get("content") is not None:
                    self.bridge.write_workspace_file(
                        html_path,
                        str(body.get("content")),
                        compile_if_latex=False,
                        compile_if_html=False,
                    )
                auto_repair = bool(body.get("auto_repair", True))
                comp = self.bridge.compile_workspace_html(
                    html_path,
                    auto_repair=auto_repair,
                )
                if comp.get("status") != "success":
                    err_msg = str(comp.get("error") or "Échec de validation/compilation HTML.")
                    log_tail = str(comp.get("log") or "").strip()
                    if log_tail:
                        err_msg = f"{err_msg}\n\nJournal compilateur :\n{log_tail[-1200:]}"
                    return HTTPStatus.BAD_REQUEST, {**comp, "error": err_msg}
                return HTTPStatus.OK, comp

            if path == "/api/files/compile-latex":
                tex_path = str(body.get("path") or "").strip()
                if not tex_path:
                    return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'path' requis."}
                if body.get("content") is not None:
                    self.bridge.write_workspace_file(
                        tex_path,
                        str(body.get("content")),
                        compile_if_latex=False,
                    )
                out_path = str(body.get("output_path") or "").strip() or None
                auto_repair = bool(body.get("auto_repair", True))
                comp = self.bridge.compile_workspace_latex(
                    tex_path,
                    output_relative_path=out_path,
                    auto_repair=auto_repair,
                )
                if comp.get("status") != "success":
                    err_msg = str(comp.get("error") or "Échec de compilation Tectonic.")
                    log_tail = str(comp.get("log") or "").strip()
                    if log_tail:
                        err_msg = f"{err_msg}\n\nJournal Tectonic :\n{log_tail[-1200:]}"
                    return HTTPStatus.BAD_REQUEST, {**comp, "error": err_msg}
                return HTTPStatus.OK, comp

            if path == "/api/files/write":
                rel_path = str(body.get("path") or "").strip()
                if not rel_path:
                    return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'path' requis."}
                content = str(body.get("content") or "")
                compile_tex = bool(body.get("compile", False))
                auto_repair = bool(body.get("auto_repair", True))
                res = self.bridge.write_workspace_file(
                    rel_path,
                    content,
                    compile_if_latex=compile_tex,
                    auto_repair=auto_repair,
                )
                return HTTPStatus.OK, res

            if path == "/api/files/upload":
                filename = str(body.get("filename") or body.get("name") or "").strip()
                if not filename:
                    return HTTPStatus.BAD_REQUEST, {"error": "Paramètre 'filename' requis."}
                content_b64 = body.get("content_base64")
                content_txt = body.get("content_text")
                mime_t = str(body.get("mime_type") or "")
                uploaded = self.bridge.upload_workspace_file(
                    filename,
                    content_base64=str(content_b64) if content_b64 is not None else None,
                    content_text=str(content_txt) if content_txt is not None else None,
                    mime_type=mime_t,
                )
                return HTTPStatus.OK, uploaded

            return HTTPStatus.NOT_FOUND, {"error": f"Route POST inconnue : {path}"}
        except FileNotFoundError as error:
            return HTTPStatus.NOT_FOUND, {"error": str(error)}
        except (ValueError, KeyError, PermissionError, SkillCommandError) as error:
            return HTTPStatus.BAD_REQUEST, {"error": str(error)}
        except Exception as error:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"{type(error).__name__}: {error}"}


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    app: NeoHarnessUIApp | None = None,
) -> ThreadingHTTPServer:
    ui_app = app or NeoHarnessUIApp()

    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _serve_static(self, rel_path: str) -> None:
            target = (STATIC_ROOT / rel_path).resolve()
            try:
                target.relative_to(STATIC_ROOT.resolve())
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            mime, _ = mimetypes.guess_type(str(target))
            content_type = mime or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
                content_type += "; charset=utf-8"
            raw = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(raw)

        def _serve_workspace_file(self, rel_path: str, *, download: bool = False, for_preview: bool = False) -> None:
            clean_rel = (rel_path or "").strip().lstrip("/")
            if not clean_rel or clean_rel.startswith(".harness"):
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Accès au chemin refusé."})
                return
            try:
                target = ui_app.bridge.filesystem.resolve(clean_rel)
                raw = ui_app.bridge.filesystem.read_bytes(clean_rel)
            except FileNotFoundError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Fichier introuvable : {clean_rel}"})
                return
            except Exception as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return

            mime, _ = mimetypes.guess_type(str(target))
            ext = target.suffix.lower()
            if ext == ".pdf":
                content_type = "application/pdf"
            elif ext in {".html", ".htm"}:
                content_type = "text/html; charset=utf-8"
                if for_preview:
                    try:
                        html_text = raw.decode("utf-8", errors="replace")
                        bridge_script = (
                            '<script id="__neoharness_runtime_bridge__">\n'
                            '(function() {\n'
                            '  function notifyHost(type, err) {\n'
                            '    try {\n'
                            '      window.parent.postMessage({\n'
                            '        type: "NEOHARNESS_HTML_RUNTIME_ERROR",\n'
                            '        error: {\n'
                            '          message: err.message || String(err),\n'
                            '          filename: err.filename || "",\n'
                            '          lineno: err.lineno || 0,\n'
                            '          colno: err.colno || 0,\n'
                            '          stack: err.stack || "",\n'
                            '          errorType: type\n'
                            '        }\n'
                            '      }, "*");\n'
                            '    } catch(e) {}\n'
                            '  }\n'
                            '  window.addEventListener("error", function(e) {\n'
                            '    notifyHost("uncaught_error", {\n'
                            '      message: e.message,\n'
                            '      filename: e.filename,\n'
                            '      lineno: e.lineno,\n'
                            '      colno: e.colno,\n'
                            '      stack: e.error ? e.error.stack : ""\n'
                            '    });\n'
                            '  });\n'
                            '  window.addEventListener("unhandledrejection", function(e) {\n'
                            '    var reason = e.reason || "Unhandled Promise Rejection";\n'
                            '    notifyHost("unhandled_rejection", {\n'
                            '      message: typeof reason === "object" ? (reason.message || JSON.stringify(reason)) : String(reason),\n'
                            '      stack: (reason && reason.stack) ? reason.stack : ""\n'
                            '    });\n'
                            '  });\n'
                            '})();\n'
                            '</script>'
                        )
                        lower_text = html_text.lower()
                        if "</head>" in lower_text:
                            idx = lower_text.rfind("</head>")
                            html_text = html_text[:idx] + bridge_script + "\n" + html_text[idx:]
                        elif "</body>" in lower_text:
                            idx = lower_text.rfind("</body>")
                            html_text = html_text[:idx] + bridge_script + "\n" + html_text[idx:]
                        else:
                            html_text = bridge_script + "\n" + html_text
                        raw = html_text.encode("utf-8")
                    except Exception:
                        pass
            elif ext == ".css":
                content_type = "text/css; charset=utf-8"
            elif ext in {".js", ".mjs"}:
                content_type = "application/javascript; charset=utf-8"
            elif ext == ".svg":
                content_type = "image/svg+xml"
            elif ext in {".tex", ".md", ".txt", ".py", ".csv"}:
                content_type = "text/plain; charset=utf-8"
            else:
                content_type = mime or "application/octet-stream"

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if for_preview:
                # Permet aux sous-ressources CSS/JS locales d'être chargées par un iframe sandbox="allow-scripts" (origine null)
                self.send_header("Access-Control-Allow-Origin", "*")
            else:
                disp = "attachment" if download else "inline"
                safe_name = target.name.replace('"', "")
                self.send_header("Content-Disposition", f'{disp}; filename="{safe_name}"')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            route = unquote(parsed.path)

            if route == "/api/files/raw":
                params = parse_qs(parsed.query)
                rel = (params.get("path") or [""])[0]
                dl = (params.get("download") or ["0"])[0] in {"1", "true", "yes"}
                self._serve_workspace_file(rel, download=dl, for_preview=False)
                return

            if route.startswith("/api/preview/workspace/"):
                rel = route[len("/api/preview/workspace/") :]
                self._serve_workspace_file(rel, download=False, for_preview=True)
                return

            if route == "/api/events/stream":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                sub = ui_app.bridge.event_bus.subscribe()
                try:
                    while True:
                        try:
                            evt = sub.get(timeout=15.0)
                            chunk = f"data: {json.dumps(evt, ensure_ascii=False, default=str)}\n\n"
                            self.wfile.write(chunk.encode("utf-8"))
                            self.wfile.flush()
                        except queue.Empty:
                            self.wfile.write(b": keepalive\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    ui_app.bridge.event_bus.unsubscribe(sub)
                return

            if route.startswith("/api/"):
                params = parse_qs(parsed.query)
                status, payload = ui_app.handle_api_get(route, params)
                self._send_json(status, payload)
                return

            if route in {"/", "/index.html"}:
                self._serve_static("index.html")
                return

            rel = route.lstrip("/")
            self._serve_static(rel)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            route = unquote(parsed.path)
            length = int(self.headers.get("Content-Length", "0") or 0)
            origin = (self.headers.get("Origin") or "").strip().lower()
            if origin == "null":
                if length > 0:
                    _ = self.rfile.read(length)
                self._send_json(
                    HTTPStatus.FORBIDDEN,
                    {"error": "Accès aux API refusé depuis un contexte d'aperçu sandboxé (Origin: null)."},
                )
                return
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Corps JSON invalide."})
                return
            status, payload = ui_app.handle_api_post(route, body if isinstance(body, dict) else {})
            self._send_json(status, payload)

    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.ui_app = ui_app  # type: ignore[attr-defined]
    return server


def run_ui_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    open_browser: bool = False,
) -> None:
    server = create_http_server(host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"NeoHarness AI — Operating Environment démarré sur {url}")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur UI NeoHarness AI.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_ui_server()
