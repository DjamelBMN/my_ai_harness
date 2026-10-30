# RÔLE DE CE FICHIER :
# Décrit, découvre, valide et exécute les outils. Tous les appels du modèle passent
# ici, afin d'appliquer schémas et permissions avant d'atteindre un handler local.

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import asdict, dataclass, field
from time import monotonic
from typing import Any, Callable

import inspect

from core.permissions import PermissionPolicy, RiskLevel
from core.tool_gateway import ToolGateway
from tools.clipboard import clipboard_get, clipboard_set
from tools.computer_use import (
    computer_action_verified,
    computer_click,
    computer_click_element,
    computer_compare_screens,
    computer_drag,
    computer_hotkey,
    computer_inspect_ui,
    computer_mouse_move,
    computer_ocr,
    computer_press,
    computer_screenshot,
    computer_scroll,
    computer_type,
    copy_to_desktop,
)
from tools.documents import analyze_dataset, generate_excel_workbook, read_document
from tools.filesystem import WorkspaceFilesystem
from tools.git import GitWorkspace
from tools.process_manager import (
    process_list,
    process_start,
    process_status,
    process_stop,
)
from tools.search import deep_research, download_resource, fetch_url, web_search
from tools.terminal import (
    run_python_script,
    run_test_suite,
    terminal_list,
    terminal_read,
    terminal_send,
    terminal_start,
    terminal_stop,
)
from tools.editor import diagnose_code, edit_file
from tools.viewer import view_file
from tools.code_search import code_ast_map, search_code
from tools.browser import DynamicBrowser
from tools.compiler import AutonomousCompiler
from tools.math_tikz import generate_math_figure
from tools.docx import generate_docx
from tools.pptx import generate_pptx
from tools.vision import transcribe_image
from tools.windows import (
    window_active,
    window_close,
    window_find,
    window_focus,
    window_list,
    window_maximize,
    window_minimize,
    window_restore,
)


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
        self._browser: DynamicBrowser | None = None
        self._tools: dict[str, Tool] = {}
        self.gateway = ToolGateway(self)
        self._register_workspace_tools()

    @property
    def browser(self) -> DynamicBrowser:
        if self._browser is None:
            self._browser = DynamicBrowser(workspace_root=self.filesystem.root)
        return self._browser

    @browser.setter
    def browser(self, value: DynamicBrowser) -> None:
        self._browser = value

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

    def _authorize_call(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> tuple[bool, str]:
        try:
            sig = inspect.signature(self.permissions.authorize)
            if len(sig.parameters) >= 4:
                return self.permissions.authorize(
                    tool.name, tool.risk_level, tool.mutates, arguments
                )
        except (ValueError, TypeError):
            pass
        return self.permissions.authorize(tool.name, tool.risk_level, tool.mutates)

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

        evaluation = self.gateway.evaluate_call(call)
        self.gateway.record_pre_execution(call, evaluation)

        if (
            self.permissions.mode == "EDIT"
            and tool.name in {"write_file", "patch_file"}
            and self.permissions.edit_preview is not None
        ):
            try:
                self.permissions.edit_preview(tool.name, call.arguments)
            except Exception as error:
                denied_exec = ToolExecution(
                    tool=tool.name,
                    status="denied",
                    summary=f"Aperçu EDIT impossible : {type(error).__name__}.",
                    risk_level=tool.risk_level.name,
                )
                self.gateway.record_hitl_decision(call, evaluation, False, denied_exec.summary)
                return denied_exec

        allowed, reason = self._authorize_call(tool, call.arguments)
        self.gateway.record_hitl_decision(call, evaluation, allowed, reason)
        if not allowed:
            status = "dry_run" if self.permissions.dry_run and tool.mutates else "denied"
            denied_exec = ToolExecution(
                tool=tool.name,
                status=status,
                summary=reason,
                data={
                    "requested_arguments": call.arguments,
                    "policy_evaluation": evaluation.to_dict(),
                },
                elapsed_seconds=monotonic() - started,
                risk_level=evaluation.risk_level.name,
            )
            self.gateway.record_post_execution(call, evaluation, denied_exec)
            return denied_exec

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
            for key in ("path", "source", "destination", "before_screenshot", "after_screenshot"):
                candidate = data.get(key)
                if isinstance(candidate, str) and candidate not in files:
                    files.append(candidate)
            if isinstance(data.get("files"), list):
                files.extend(item for item in data["files"] if isinstance(item, str))
            exec_status = "error" if isinstance(data, dict) and data.get("status") == "error" else "success"
            exec_summary = (
                str(data.get("error") or "Erreur signalée par l'outil.")
                if exec_status == "error"
                else "Outil exécuté."
            )
            success_exec = ToolExecution(
                tool=tool.name,
                status=exec_status,
                summary=exec_summary,
                output=output,
                data=data,
                files=files,
                elapsed_seconds=monotonic() - started,
                risk_level=evaluation.risk_level.name,
            )
            self.gateway.record_post_execution(call, evaluation, success_exec)
            return success_exec
        except Exception as error:
            # Les erreurs d'outil sont données au modèle pour qu'il puisse diagnostiquer.
            message = str(error).replace("\n", " ")[:1000]
            err_exec = ToolExecution(
                tool=tool.name,
                status="error",
                summary=f"{type(error).__name__}: {message}",
                output=f"Erreur de l'outil {tool.name}: {message}",
                elapsed_seconds=monotonic() - started,
                risk_level=evaluation.risk_level.name,
            )
            self.gateway.record_post_execution(call, evaluation, err_exec)
            return err_exec

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
            "analyze_dataset",
            "Exécute un profilage statistique complet d'un jeu de données (.csv, .tsv, .xlsx, .json, .sqlite) : schéma, moyenne, médiane, écart-type, corrélations de Pearson et détection des valeurs aberrantes (outliers).",
            {"path": string, "sheet_name": optional_string},
            ["path"],
            lambda path, sheet_name="": analyze_dataset(path, sheet_name=sheet_name, filesystem=fs),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=30.0,
        )
        add(
            "generate_excel",
            "Génère un classeur Excel (.xlsx) professionnel stylisé avec formules natives (=SUM, =AVERAGE) et ajustement automatique des colonnes.",
            {
                "output_path": string,
                "headers": string_array,
                "rows": {"type": "array", "items": {"type": "array"}},
                "sheet_title": optional_string,
                "include_formulas": boolean,
            },
            ["output_path", "headers", "rows"],
            lambda output_path, headers, rows, sheet_title="Données", include_formulas=True: generate_excel_workbook(
                output_path=output_path,
                headers=headers,
                rows=rows,
                sheet_title=sheet_title,
                include_formulas=include_formulas,
                filesystem=fs,
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=30.0,
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
            "edit_file",
            "Remplace exactement un bloc de code unique dans un fichier avec validation syntaxique instantanée.",
            {"path": string, "old_str": string, "new_str": string},
            ["path", "old_str", "new_str"],
            lambda path, old_str, new_str: edit_file(path, old_str, new_str, filesystem=fs),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "view_file",
            "Affiche un fichier fenêtré avec numérotation de lignes (max 200 lignes).",
            {"path": string, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
            ["path"],
            lambda path, start_line=1, end_line=None: view_file(path, start_line=start_line, end_line=end_line, filesystem=fs),
            risk=RiskLevel.READ_ONLY,
        )
        add(
            "search_code",
            "Recherche de code ciblée par regex en ignorant répertoires parasites (.git, node_modules...).",
            {"pattern": string, "path": optional_string, "file_glob": optional_string},
            ["pattern"],
            lambda pattern, path=".", file_glob=None: search_code(pattern, path=path, file_glob=file_glob, filesystem=fs),
            risk=RiskLevel.READ_ONLY,
        )
        add(
            "code_ast_map",
            "Construit la carte structurelle AST du code (classes, méthodes, signatures, appels, imports) et localise les définitions et références d'un symbole.",
            {"path": optional_string, "symbol_query": optional_string, "max_files": {"type": "integer"}},
            [],
            lambda path=".", symbol_query="", max_files=40: code_ast_map(
                path=path, symbol_query=symbol_query, max_files=max_files, filesystem=fs
            ),
            risk=RiskLevel.READ_ONLY,
        )
        add(
            "diagnose_code",
            "Exécute un diagnostic statique et sémantique instantané (AST Python, code mort, arguments mutables, JSON) sur un fichier.",
            {"path": string},
            ["path"],
            lambda path: diagnose_code(path=path, filesystem=fs),
            risk=RiskLevel.READ_ONLY,
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
            "Exécute une recherche Internet réelle, navigue dans les sources ou télécharge et vérifie un document dans le workspace.",
            {
                "query": string,
                "max_results": {"type": "integer"},
                "download": boolean,
                "output_path": optional_string,
            },
            ["query"],
            lambda query, max_results=5, download=None, output_path="": web_search(
                query, max_results=max_results, download=download, output_path=output_path, workspace=fs.root
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=35.0,
        )
        add(
            "deep_research",
            "Exécute une recherche profonde en essaim parallèle (Deep Research) : lance plusieurs sous-requêtes simultanées, lit le contenu complet de multiples sources indépendantes, croise les faits et génère des citations numérotées [1]..[N].",
            {
                "query": string,
                "sub_queries": string_array,
                "max_sources": {"type": "integer"},
                "read_full_pages": boolean,
            },
            ["query"],
            lambda query, sub_queries=None, max_sources=8, read_full_pages=True: deep_research(
                query=query,
                sub_queries=sub_queries,
                max_sources=max_sources,
                read_full_pages=read_full_pages,
                workspace=fs.root,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=90.0,
        )
        add(
            "fetch_url",
            "Ouvre une page Web distante, extrait son contenu textuel et identifie tous les liens de téléchargement de documents.",
            {"url": string, "output_path": optional_string},
            ["url"],
            lambda url, output_path="": fetch_url(
                url, output_path=output_path, workspace=fs.root
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=25.0,
        )
        add(
            "download_resource",
            "Télécharge physiquement une ressource distante (PDF, document, image) dans le workspace, vérifie son intégrité et enregistre sa chaîne de provenance.",
            {"url": string, "output_path": optional_string},
            ["url"],
            lambda url, output_path="": download_resource(
                url, output_path=output_path, workspace=fs.root
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=30.0,
        )
        add(
            "navigate_url",
            "Navigue vers une page Web avec le navigateur Chromium, extrait l'arbre DOM structuré et liste les éléments interactifs.",
            {
                "url": string,
                "session_id": optional_string,
                "override_robots": boolean,
                "justification": optional_string,
            },
            ["url"],
            lambda url, session_id="default", override_robots=False, justification="": (
                self.browser.navigate(
                    url,
                    session_id=session_id or "default",
                    override_robots=override_robots,
                    justification=justification,
                )
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=30.0,
        )
        add(
            "click_element",
            "Clique sur un élément interactif de la page Web courante via son identifiant (ex. 'e_1').",
            {"element_id": string, "session_id": optional_string},
            ["element_id"],
            lambda element_id, session_id="default": (
                self.browser.click_element(element_id, session_id=session_id or "default")
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=15.0,
        )
        add(
            "fill_input",
            "Saisit du texte dans un champ de formulaire Web identifié par son ID.",
            {"element_id": string, "text": string, "session_id": optional_string},
            ["element_id", "text"],
            lambda element_id, text, session_id="default": (
                self.browser.fill_input(element_id, text, session_id=session_id or "default")
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=15.0,
        )
        add(
            "download_via_browser",
            "Télécharge un fichier distant via le navigateur dans workspace/downloads/ avec vérification d'intégrité et magic bytes.",
            {
                "url": string,
                "target_filename": optional_string,
                "session_id": optional_string,
                "task_id": optional_string,
            },
            ["url"],
            lambda url, target_filename=None, session_id="default", task_id="": (
                self.browser.download_via_browser(
                    url,
                    target_filename=target_filename,
                    session_id=session_id or "default",
                    task_id=task_id,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=40.0,
        )
        add(
            "screenshot_page",
            "Prend une capture d'écran de la page Web courante pour inspection visuelle de repli.",
            {"target_path": optional_string, "session_id": optional_string},
            [],
            lambda target_path=None, session_id="default": (
                self.browser.screenshot(target_path=target_path, session_id=session_id or "default")
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=15.0,
        )
        add(
            "compile_document",
            "Compile de façon autonome un document (LaTeX/TeX) en PDF avec boucle d'auto-correction, oracles physiques et inspection de mise en page.",
            {
                "path": string,
                "output_pdf_path": optional_string,
                "expected_pages": {"type": "integer"},
                "auto_fix": boolean,
            },
            ["path"],
            lambda path, output_pdf_path=None, expected_pages=None, auto_fix=True: (
                AutonomousCompiler(workspace=fs.root).compile(
                    tex_path=path,
                    output_pdf_path=output_pdf_path,
                    expected_pages=expected_pages,
                    auto_fix=auto_fix,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=60.0,
        )
        add(
            "generate_math_figure",
            "Génère un tableau de variations, de signes, un arbre pondéré de probabilités ou une courbe pgfplots TikZ avec calculs déterministes et oracles stricts (SymPy).",
            {
                "figure_type": string,
                "func_str": optional_string,
                "var_str": optional_string,
                "student_version": boolean,
                "compile_pdf": boolean,
                "output_path": optional_string,
            },
            ["figure_type"],
            lambda figure_type, func_str="", var_str="x", student_version=False, compile_pdf=False, output_path="": (
                generate_math_figure(
                    figure_type=figure_type,
                    func_str=func_str,
                    var_str=var_str,
                    student_version=student_version,
                    compile_pdf=compile_pdf,
                    output_path=output_path,
                    workspace=fs.root,
                )
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=45.0,
        )
        add(
            "generate_docx",
            "Génère un document Word (.docx) professionnel via Pandoc avec vérification physique d'intégrité (ZIP/XML) et déclaration ARTIFACT_READY.",
            {
                "content": string,
                "output_path": optional_string,
                "title": optional_string,
            },
            ["content"],
            lambda content, output_path="", title="": (
                generate_docx(
                    content=content,
                    output_path=output_path,
                    title=title,
                    workspace=fs.root,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=30.0,
        )
        add(
            "generate_pptx",
            "Génère une présentation PowerPoint (.pptx) professionnelle via Pandoc avec diapositives structurées et déclaration ARTIFACT_READY.",
            {
                "content": string,
                "output_path": optional_string,
                "title": optional_string,
            },
            ["content"],
            lambda content, output_path="", title="": (
                generate_pptx(
                    content=content,
                    output_path=output_path,
                    title=title,
                    workspace=fs.root,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=35.0,
        )
        add(
            "transcribe_image",
            "Transcrit fidèlement une image ou un exercice scanné via multi-passes OCR. Marque [illisible] sans inventer.",
            {
                "image_path": string,
                "min_confidence": {"type": "number"},
            },
            ["image_path"],
            lambda image_path, min_confidence=45.0: (
                transcribe_image(
                    image_path=image_path,
                    filesystem=fs,
                    min_confidence=min_confidence,
                )
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=30.0,
        )
        # ------------------------------------------------------------------
        # CAPACITÉS WINDOWS OPÉRATEUR : CLIPBOARD, PROCESS, WINDOWS, TERMINAL, COMPUTER USE
        # ------------------------------------------------------------------
        integer = {"type": "integer"}
        int_array = {"type": "array", "items": integer}

        add(
            "clipboard_get",
            "Lit le texte actuellement présent dans le presse-papiers Windows.",
            {},
            [],
            lambda: clipboard_get(),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "clipboard_set",
            "Copie du texte dans le presse-papiers Windows et vérifie l'écriture.",
            {"text": string},
            ["text"],
            lambda text: clipboard_set(text),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "process_list",
            "Liste les processus actifs sur Windows (PID, nom, mémoire).",
            {"filter_name": optional_string, "limit": integer},
            [],
            lambda filter_name="", limit=50: process_list(filter_name=filter_name, limit=limit),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "process_start",
            "Démarre une application ou un processus Windows (ex: 'code', 'notepad') et vérifie qu'il est vivant.",
            {"executable": string, "arguments": string_array, "cwd": optional_string},
            ["executable"],
            lambda executable, arguments=None, cwd=None: process_start(
                executable=executable,
                arguments=arguments,
                cwd=cwd or str(fs.root),
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=20.0,
        )
        add(
            "process_status",
            "Vérifie l'état (vivant, code retour, sortie) d'un processus Windows par son PID.",
            {"pid": integer},
            ["pid"],
            lambda pid: process_status(pid),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "process_stop",
            "Arrête un processus Windows par son PID après validation Policy Engine / HITL.",
            {"pid": integer, "force": boolean},
            ["pid"],
            lambda pid, force=False: process_stop(pid, force=force),
            risk=RiskLevel.HIGH,
            mutates=True,
        )
        add(
            "window_list",
            "Liste toutes les fenêtres Windows visibles avec titre, HWND, PID et coordonnées.",
            {"visible_only": boolean, "filter_title": optional_string},
            [],
            lambda visible_only=True, filter_title="": window_list(
                visible_only=visible_only,
                filter_title=filter_title,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "window_active",
            "Identifie la fenêtre Windows actuellement active au premier plan.",
            {},
            [],
            lambda: window_active(),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "window_find",
            "Recherche une fenêtre Windows par son titre (ex: 'Visual Studio Code').",
            {"query": string},
            ["query"],
            lambda query: window_find(query),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "window_focus",
            "Active et met au premier plan une fenêtre Windows et vérifie qu'elle est active.",
            {"title": optional_string, "hwnd": integer},
            [],
            lambda title="", hwnd=0: window_focus(title=title, hwnd=hwnd),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "window_minimize",
            "Minimise une fenêtre Windows identifiée par son titre ou HWND.",
            {"title": optional_string, "hwnd": integer},
            [],
            lambda title="", hwnd=0: window_minimize(title=title, hwnd=hwnd),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "window_maximize",
            "Maximise une fenêtre Windows identifiée par son titre ou HWND.",
            {"title": optional_string, "hwnd": integer},
            [],
            lambda title="", hwnd=0: window_maximize(title=title, hwnd=hwnd),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "window_restore",
            "Restaure une fenêtre Windows minimisée ou maximisée.",
            {"title": optional_string, "hwnd": integer},
            [],
            lambda title="", hwnd=0: window_restore(title=title, hwnd=hwnd),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "window_close",
            "Ferme proprement une fenêtre Windows (WM_CLOSE) après validation humaine.",
            {"title": optional_string, "hwnd": integer},
            [],
            lambda title="", hwnd=0: window_close(title=title, hwnd=hwnd),
            risk=RiskLevel.HIGH,
            mutates=True,
        )
        add(
            "terminal_start",
            "Démarre ou récupère une session de terminal interactif persistant Windows (PowerShell ou CMD).",
            {"session_id": optional_string, "shell": optional_string},
            [],
            lambda session_id="default", shell="powershell": terminal_start(
                session_id=session_id,
                shell=shell,
                cwd=fs.root,
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=15.0,
        )
        add(
            "terminal_send",
            "Envoie une commande ou une réponse interactive stdin au terminal persistant et lit stdout/stderr en temps réel.",
            {"command": string, "session_id": optional_string, "wait_ms": integer},
            ["command"],
            lambda command, session_id="default", wait_ms=600: terminal_send(
                command=command,
                session_id=session_id,
                wait_ms=wait_ms,
                cwd=fs.root,
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=30.0,
        )
        add(
            "terminal_read",
            "Lit les nouvelles sorties stdout/stderr d'une session de terminal persistant (ex: serveur npm run dev).",
            {"session_id": optional_string, "wait_ms": integer},
            [],
            lambda session_id="default", wait_ms=300: terminal_read(
                session_id=session_id,
                wait_ms=wait_ms,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=20.0,
        )
        add(
            "terminal_stop",
            "Arrête proprement une session de terminal persistant Windows.",
            {"session_id": optional_string},
            [],
            lambda session_id="default": terminal_stop(session_id=session_id),
            risk=RiskLevel.LOW,
            mutates=True,
        )
        add(
            "terminal_list",
            "Liste les sessions de terminal interactives actives.",
            {},
            [],
            lambda: terminal_list(),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
        )
        add(
            "computer_screenshot",
            "Prend une capture de l'écran Windows actif et la sauvegarde dans le workspace et/ou directement sur le Bureau Windows (si save_to_desktop=True).",
            {
                "region": int_array,
                "label": optional_string,
                "save_to_desktop": boolean,
                "output_path": optional_string,
            },
            [],
            lambda region=None, label="", save_to_desktop=False, output_path="": computer_screenshot(
                region=region,
                label=label,
                save_to_desktop=save_to_desktop,
                output_path=output_path,
                workspace=fs.root,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=15.0,
        )
        add(
            "copy_to_desktop",
            "Copie directement un fichier ou une capture d'écran du workspace sur le Bureau Windows de l'utilisateur.",
            {"source_path": string, "filename": optional_string},
            ["source_path"],
            lambda source_path, filename="": copy_to_desktop(
                source_path=source_path,
                filename=filename,
                workspace=fs.root,
            ),
            risk=RiskLevel.LOW,
            mutates=True,
            timeout=10.0,
        )
        add(
            "computer_ocr",
            "Extrait par OCR le texte visible à l'écran avec ses coordonnées (x, y) pour localiser un élément visuel.",
            {"image_path": optional_string, "region": int_array, "find_text": optional_string},
            [],
            lambda image_path="", region=None, find_text="": computer_ocr(
                image_path=image_path,
                region=region,
                find_text=find_text,
                workspace=fs.root,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=30.0,
        )
        add(
            "computer_compare_screens",
            "Compare deux captures d'écran avant et après une action pour vérifier si l'interface a réagi.",
            {"before_path": string, "after_path": string},
            ["before_path", "after_path"],
            lambda before_path, after_path: computer_compare_screens(
                before_path=before_path,
                after_path=after_path,
                workspace=fs.root,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=15.0,
        )
        add(
            "computer_mouse_move",
            "Déplace le curseur de la souris aux coordonnées (x, y).",
            {"x": integer, "y": integer, "relative": boolean},
            ["x", "y"],
            lambda x, y, relative=False: computer_mouse_move(x=x, y=y, relative=relative),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_click",
            "Clique avec la souris (left, right, middle, ou double-clic) aux coordonnées (x, y).",
            {"x": integer, "y": integer, "button": optional_string, "double": boolean},
            [],
            lambda x=None, y=None, button="left", double=False: computer_click(
                x=x,
                y=y,
                button=button,
                double=double,
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_drag",
            "Glisse-dépose avec la souris de (start_x, start_y) vers (end_x, end_y).",
            {"start_x": integer, "start_y": integer, "end_x": integer, "end_y": integer},
            ["start_x", "start_y", "end_x", "end_y"],
            lambda start_x, start_y, end_x, end_y: computer_drag(
                start_x=start_x,
                start_y=start_y,
                end_x=end_x,
                end_y=end_y,
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_scroll",
            "Fait défiler la molette de la souris (positif vers le haut, négatif vers le bas).",
            {"clicks": integer, "x": integer, "y": integer},
            ["clicks"],
            lambda clicks, x=None, y=None: computer_scroll(clicks=clicks, x=x, y=y),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_type",
            "Saisit du texte au clavier dans la fenêtre active.",
            {"text": string, "interval_ms": integer},
            ["text"],
            lambda text, interval_ms=8: computer_type(text=text, interval_ms=interval_ms),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_press",
            "Appuie sur une touche individuelle du clavier (ex: 'enter', 'escape', 'tab').",
            {"key": string},
            ["key"],
            lambda key: computer_press(key=key),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_hotkey",
            "Exécute un raccourci clavier combiné (ex: ['ctrl', 'c'], ['alt', 'tab'], ['win']).",
            {"keys": string_array},
            ["keys"],
            lambda keys: computer_hotkey(keys=keys),
            risk=RiskLevel.MODERATE,
            mutates=True,
        )
        add(
            "computer_inspect_ui",
            "Inspecte l'arbre d'accessibilité Windows UI Automation + Win32 de la fenêtre active et génère une capture Set-of-Mark (SoM) avec badges numérotés [1]..[N] et coordonnées exactes.",
            {
                "filter_text": optional_string,
                "annotate_screenshot": boolean,
                "max_elements": integer,
            },
            [],
            lambda filter_text="", annotate_screenshot=True, max_elements=60: computer_inspect_ui(
                filter_text=filter_text,
                annotate_screenshot=annotate_screenshot,
                max_elements=max_elements,
                workspace=fs.root,
            ),
            risk=RiskLevel.READ_ONLY,
            mutates=False,
            timeout=20.0,
        )
        add(
            "computer_click_element",
            "Clique en boucle fermée sur un élément UI identifié par son numéro Set-of-Mark [element_id] (et saisit optionnellement du texte).",
            {
                "element_id": integer,
                "button": optional_string,
                "double": boolean,
                "text_to_type": optional_string,
                "press_enter": boolean,
                "settle_ms": integer,
            },
            ["element_id"],
            lambda element_id, button="left", double=False, text_to_type="", press_enter=False, settle_ms=350: (
                computer_click_element(
                    element_id=element_id,
                    button=button,
                    double=double,
                    text_to_type=text_to_type,
                    press_enter=press_enter,
                    settle_ms=settle_ms,
                    workspace=fs.root,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=25.0,
        )
        add(
            "computer_action_verified",
            "Exécute une action Computer Use en boucle fermée (Screenshot Avant -> Action -> Screenshot Après -> Vérification du changement d'écran et de fenêtre).",
            {
                "action_type": string,
                "x": integer,
                "y": integer,
                "element_id": integer,
                "button": optional_string,
                "text": optional_string,
                "key": optional_string,
                "keys": string_array,
                "expected_window": optional_string,
                "settle_ms": integer,
            },
            ["action_type"],
            lambda action_type, x=None, y=None, element_id=None, button="left", text="", key="", keys=None, expected_window="", settle_ms=350: (
                computer_action_verified(
                    action_type=action_type,
                    x=x,
                    y=y,
                    element_id=element_id,
                    button=button,
                    text=text,
                    key=key,
                    keys=keys,
                    expected_window=expected_window,
                    settle_ms=settle_ms,
                    workspace=fs.root,
                )
            ),
            risk=RiskLevel.MODERATE,
            mutates=True,
            timeout=25.0,
        )


