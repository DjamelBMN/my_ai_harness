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
from tools.search import download_resource, fetch_url, web_search
from tools.terminal import run_python_script, run_test_suite
from tools.editor import edit_file
from tools.viewer import view_file
from tools.code_search import search_code
from tools.browser import DynamicBrowser
from tools.compiler import AutonomousCompiler
from tools.math_tikz import generate_math_figure
from tools.docx import generate_docx
from tools.vision import transcribe_image


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



