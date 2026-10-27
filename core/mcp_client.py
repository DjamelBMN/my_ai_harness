# RÔLE DE CE FICHIER :
# Adaptateur client MCP (Model Context Protocol) JSON-RPC 2.0 sur stdio.
# Permet de connecter proprement des serveurs d'outils MCP externes et d'exposer
# leurs outils dans le ToolRegistry / ToolGateway sous contrôle strict du PolicyEngine
# et du Human-In-The-Loop (HITL).

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.permissions import RiskLevel
from tools.process_utils import safe_subprocess_environment

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


@dataclass
class MCPToolSpec:
    server_name: str
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def registered_name(self) -> str:
        clean_srv = self.server_name.strip().lower().replace("-", "_")
        clean_tool = self.name.strip().lower().replace("-", "_")
        return f"mcp_{clean_srv}_{clean_tool}"


class MCPStdioClient:
    """Client JSON-RPC 2.0 léger pour communiquer avec un serveur MCP local via stdio."""

    def __init__(
        self,
        server_name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        if not command or not isinstance(command, list):
            raise ValueError("La commande du serveur MCP doit être une liste non vide.")
        self.server_name = server_name
        self.command = command
        self.cwd = cwd
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._request_id = 0

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return {"status": "already_running", "server": self.server_name}
            self._process = subprocess.Popen(
                self.command,
                cwd=self.cwd,
                env=safe_subprocess_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
        init_res = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "NeoHarnessAI", "version": "2.0.0"},
            },
        )
        return {"status": "started", "server": self.server_name, "server_info": init_res}

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                raise RuntimeError(f"Le serveur MCP '{self.server_name}' n'est pas démarré.")
            self._request_id += 1
            req_id = self._request_id
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params or {},
            }
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
            raw_line = self._process.stdout.readline()
            if not raw_line:
                raise RuntimeError(f"Aucune réponse reçue du serveur MCP '{self.server_name}'.")
            response = json.loads(raw_line)
            if "error" in response:
                raise RuntimeError(f"Erreur MCP ({self.server_name}) : {response['error']}")
            res = response.get("result")
            return res if isinstance(res, dict) else {"result": res}

    def list_tools(self) -> list[MCPToolSpec]:
        res = self.request("tools/list", {})
        raw_tools = res.get("tools", [])
        specs: list[MCPToolSpec] = []
        if isinstance(raw_tools, list):
            for item in raw_tools:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                schema = item.get("inputSchema") or {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": True,
                }
                specs.append(
                    MCPToolSpec(
                        server_name=self.server_name,
                        name=str(item["name"]),
                        description=str(item.get("description") or f"Outil MCP {item['name']}"),
                        input_schema=schema,
                    )
                )
        return specs

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        res = self.request("tools/call", {"name": tool_name, "arguments": arguments or {}})
        return {
            "status": "error" if res.get("isError") else "success",
            "server": self.server_name,
            "tool": tool_name,
            "content": res.get("content", []),
            "raw": res,
        }

    def close(self) -> None:
        with self._lock:
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=3)
                except Exception:
                    try:
                        self._process.kill()
                    except Exception:
                        pass
                finally:
                    self._process = None


class MCPClientManager:
    """Gère les serveurs MCP externes et enregistre leurs outils dans ToolRegistry."""

    def __init__(self, tool_registry: "ToolRegistry") -> None:
        self.tool_registry = tool_registry
        self.clients: dict[str, MCPStdioClient] = {}

    def register_server(
        self,
        server_name: str,
        command: list[str],
        *,
        cwd: str | None = None,
        risk_level: RiskLevel = RiskLevel.MODERATE,
    ) -> list[str]:
        from tools.registry import Tool

        client = MCPStdioClient(server_name, command, cwd=cwd)
        client.start()
        self.clients[server_name] = client
        registered: list[str] = []
        for spec in client.list_tools():
            reg_name = spec.registered_name
            if reg_name in {t.name for t in self.tool_registry.discover()}:
                continue

            def _make_handler(c: MCPStdioClient, t_name: str):
                def _handler(**kwargs: Any) -> dict[str, Any]:
                    return c.call_tool(t_name, kwargs)

                return _handler

            self.tool_registry.register(
                Tool(
                    name=reg_name,
                    description=f"[MCP:{server_name}] {spec.description}",
                    schema=spec.input_schema,
                    execute=_make_handler(client, spec.name),
                    permissions=("mcp",),
                    timeout=30.0,
                    risk_level=risk_level,
                    mutates=True,
                )
            )
            registered.append(reg_name)
        return registered

    def close_all(self) -> None:
        for client in list(self.clients.values()):
            client.close()
        self.clients.clear()