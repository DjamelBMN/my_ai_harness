# RÔLE DE CE FICHIER :
# Décrit, découvre, valide et exécute les outils. Tous les appels du modèle passent
# ici, afin d'appliquer schémas et permissions avant d'atteindre un handler local.

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Callable

from core.permissions import PermissionPolicy, RiskLevel
from tools.documents import read_document
from tools.filesystem import WorkspaceFilesystem
from tools.git import GitWorkspace
from tools.search import web_search
from tools.terminal import run_python_script, run_test_suite


@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    execute: Callable[..., Any]
    permissions: tuple[str, ...] = ("workspace",)
    timeout: float = 10.0
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    mutates: bool = False

    def public_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.schema,
        }


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class ToolExecution:
    tool: str
    status: str
    summary: str
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    risk_level: str = "READ_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _object_schema(
    properties: dict[str, dict[str, Any]], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "arguments") -> None:
    expected = schema.get("type")
    type_checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
    }
    if expected in type_checks and not type_checks[expected](value):
        raise ValueError(f"{path} doit être de type {expected}.")
    if expected == "object":
        properties = schema.get("properties", {})
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise ValueError(f"{path} manque les champs requis : {', '.join(missing)}.")
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise ValueError(f"{path} contient des champs inconnus : {', '.join(sorted(extra))}.")
        for key, child in value.items():
            if key in properties:
                _validate_schema(child, properties[key], f"{path}.{key}")
    if expected == "array" and "items" in schema:
        for index, child_value in enumerate(value):
            _validate_schema(child_value, schema["items"], f"{path}[{index}]")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} doit être l'une de : {', '.join(map(str, schema['enum']))}.")


class ToolRegistry:
    """Registre extensible dont l'API publique ne révèle que des outils actifs."""

    def __init__(
        self,
        filesystem: WorkspaceFilesystem,
        permissions: PermissionPolicy | None = None,
        *,
        max_output_chars: int = 12_000,
    ) -> None:
        self.filesystem = filesystem
        self.permissions = permissions or PermissionPolicy()
        self.max_output_chars = max_output_chars
        self._tools: dict[str, Tool] = {}
        self._register_workspace_tools()

    def register(self, tool: Tool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"Nom d'outil vide ou déjà enregistré : {tool.name!r}.")
        self._tools[tool.name] = tool

    def discover(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.public_schema() for tool in self.discover()]

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Outil inconnu : {name}.") from None

    def execute(self, call: ToolCall) -> ToolExecution:
        started = monotonic()
        try:
            tool = self.get(call.name)
            if not isinstance(call.arguments, dict):
                raise ValueError("Les arguments d'un outil doivent être un objet JSON.")
            _validate_schema(call.arguments, tool.schema)
        except Exception as error:
            return ToolExecution(
                tool=call.name,
                status="error",
                summary=f"Arguments refusés : {error}",
                elapsed_seconds=monotonic() - started,
                risk_level="READ_ONLY",
            )

        if (
            self.permissions.mode == "EDIT"
            and tool.name in {"write_file", "patch_file"}
            and self.permissions.edit_preview is not None
        ):
            try:
                self.permissions.edit_preview(tool.name, call.arguments)
            except Exception as error:
                return ToolExecution(
                    tool=tool.name,
                    status="denied",
                    summary=f"Aperçu EDIT impossible : {type(error).__name__}.",
                    risk_level=tool.risk_level.name,
                )

        allowed, reason = self.permissions.authorize(
            tool.name, tool.risk_level, tool.mutates
        )
        if not allowed:
            status = "dry_run" if self.permissions.dry_run and tool.mutates else "denied"
            return ToolExecution(
                tool=tool.name,
                status=status,
                summary=reason,
                data={"requested_arguments": call.arguments},
                elapsed_seconds=monotonic() - started,
                risk_level=tool.risk_level.name,
            )

        try:
            if tool.mutates:
                # Écritures et suppressions restent synchrones; leurs handlers
                # utilisent des opérations atomiques ou des subprocess bornés.
                result = tool.execute(**call.arguments)
            else:
                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(tool.execute, **call.arguments)
                try:
                    result = future.result(timeout=tool.timeout)
                except FutureTimeoutError:
                    future.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise TimeoutError(
                        f"L'outil {tool.name} a dépassé {tool.timeout:g} secondes."
                    ) from None
                else:
                    executor.shutdown(wait=True)
            if isinstance(result, dict):
                data = result
                output = json.dumps(result, ensure_ascii=False, default=str)
            else:
                data = {"result": result}
                output = result if isinstance(result, str) else json.dumps(
                    result, ensure_ascii=False, default=str
                )
            if len(output) > self.max_output_chars:
                output = output[: self.max_output_chars] + "\n[sortie tronquée]"
            files = []
            for key in ("path", "source", "destination"):
                candidate = data.get(key)
                if isinstance(candidate, str) and candidate not in files:
                    files.append(candidate)
            if isinstance(data.get("files"), list):
                files.extend(item for item in data["files"] if isinstance(item, str))
            return ToolExecution(
                tool=tool.name,
                status="success",
                summary="Outil exécuté.",
                output=output,
                data=data,
                files=files,
                elapsed_seconds=monotonic() - started,
                risk_level=tool.risk_level.name,
            )
        except Exception as error:
            # Les erreurs d'outil sont données au modèle pour qu'il puisse diagnostiquer.
            message = str(error).replace("\n", " ")[:1000]
            return ToolExecution(
                tool=tool.name,
                status="error",
                summary=f"{type(error).__name__}: {message}",
                output=f"Erreur de l'outil {tool.name}: {message}",
                elapsed_seconds=monotonic() - started,
                risk_level=tool.risk_level.name,
            )

    def execute_many(self, calls: list[ToolCall]) -> list[ToolExecution]:
        """Parallélise uniquement un lot sans effet de bord."""
        if len(calls) > 1 and all(
            call.name in self._tools
            and not self._tools[call.name].mutates
            and self._tools[call.name].risk_level <= RiskLevel.LOW
            for call in calls
        ):
            with ThreadPoolExecutor(max_workers=min(len(calls), 4)) as executor:
                return list(executor.map(self.execute, calls))
        return [self.execute(call) for call in calls]

    def _register_workspace_tools(self) -> None:
        fs = self.filesystem
        git = GitWorkspace(fs.root)
        string = {"type": "string"}
        optional_string = {"type": "string"}
        boolean = {"type": "boolean"}
        string_array = {"type": "array", "items": string}

        def add(
            name: str,
            description: str,
            properties: dict[str, dict[str, Any]],
            required: list[str],
            handler: Callable[..., Any],
            *,
            risk: RiskLevel = RiskLevel.READ_ONLY,
            mutates: bool = False,
            timeout: float = 10.0,
        ) -> None:
            self.register(
                Tool(
                    name=name,
                    description=description,
                    schema=_object_schema(properties, required),
                    execute=handler,
                    timeout=timeout,
                    risk_level=risk,
                    mutates=mutates,
                )
            )

        add(
            "list_files",
            "Liste les fichiers du workspace. Les chemins sont relatifs à sa racine.",
            {"path": optional_string, "recursive": boolean},
            [],
            lambda path=".", recursive=False: {"files": fs.list_files(path, recursive)},
        )
        add(
            "find_file",
            "Recherche les noms de fichiers dans le workspace.",
            {"name": string},
            ["name"],
            lambda name: {"files": fs.find_file(name)},
        )
        add(
            "search_files",
            "Recherche un texte dans les fichiers lisibles du workspace.",
            {"query": string, "extensions": string_array},
            ["query"],
            lambda query, extensions=None: {"matches": fs.search_files(query, extensions)},
        )
        add(
            "read_file",
            "Lit un fichier texte UTF-8 dans le workspace.",
            {"path": string},
            ["path"],
            lambda path: {"path": path, "content": fs.read_file(path)},
        )
        add(
            "read_document",
            "Extrait du texte d'un fichier pris en charge sans le modifier.",
            {"path": string},
            ["path"],
            lambda path: read_document(path, filesystem=fs),
            timeout=180.0,
        )
        add(
            "write_file",
            "Crée un fichier ou remplace un fichier après confirmation humaine.",
            {"path": string, "content": string, "overwrite": boolean},
            ["path", "content"],
            lambda path, content, overwrite=False: fs.write_file(
                path, content, overwrite=overwrite
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "patch_file",
            "Remplace un texte exact dans un fichier après confirmation humaine.",
            {
                "path": string,
                "old_text": string,
                "new_text": string,
                "replace_all": boolean,
            },
            ["path", "old_text", "new_text"],
            lambda path, old_text, new_text, replace_all=False: fs.patch_file(
                path, old_text, new_text, replace_all=replace_all
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "delete_file",
            "Supprime un fichier unique après confirmation explicite.",
            {"path": string},
            ["path"],
            lambda path: fs.delete_file(path),
            risk=RiskLevel.DESTRUCTIVE,
            mutates=True,
        )
        add(
            "move_file",
            "Déplace un fichier sans écraser une destination existante.",
            {"source": string, "destination": string},
            ["source", "destination"],
            lambda source, destination: fs.move_file(source, destination),
            risk=RiskLevel.HIGH,
            mutates=True,
        )
        add(
            "run_tests",
            "Lance unittest discover uniquement depuis la racine du workspace.",
            {},
            [],
            lambda: run_test_suite(fs.root),
            risk=RiskLevel.HIGH,
            mutates=True,
            timeout=180.0,
        )
        add(
            "run_python",
            "Exécute un script .py du workspace sans shell; une confirmation HIGH est requise.",
            {"script_path": string, "arguments": string_array},
            ["script_path"],
            lambda script_path, arguments=None: run_python_script(
                fs.root, script_path, arguments
            ),
            risk=RiskLevel.HIGH,
            mutates=True,
            timeout=125.0,
        )
        add(
            "git_status",
            "Lit le statut du dépôt Git situé exactement à la racine du workspace.",
            {},
            [],
            lambda: git.status(),
            timeout=30.0,
        )
        add(
            "git_current_branch",
            "Retourne la branche courante sans la modifier.",
            {},
            [],
            lambda: git.current_branch(),
            timeout=30.0,
        )
        add(
            "git_create_branch",
            "Crée et sélectionne une branche après confirmation humaine.",
            {"name": string},
            ["name"],
            lambda name: git.create_branch(name),
            risk=RiskLevel.HIGH,
            mutates=True,
            timeout=30.0,
        )
        add(
            "git_commit_staged",
            "Crée un commit des seules modifications déjà staged après confirmation.",
            {"message": string},
            ["message"],
            lambda message: git.commit_staged(message),
            risk=RiskLevel.HIGH,
            mutates=True,
            timeout=60.0,
        )
        add(
            "git_merge",
            "Fusionne une branche dans la branche courante après confirmation.",
            {"branch_name": string},
            ["branch_name"],
            lambda branch_name: git.merge(branch_name),
            risk=RiskLevel.DESTRUCTIVE,
            mutates=True,
            timeout=60.0,
        )
        add(
            "web_search",
            "Exécute une recherche Internet réelle et retourne les résultats (titres, URLs, extraits, dates).",
            {"query": string, "max_results": {"type": "integer"}},
            ["query"],
            lambda query, max_results=5: web_search(query, max_results=max_results),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=25.0,
        )

