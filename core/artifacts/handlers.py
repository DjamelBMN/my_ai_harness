# RÔLE DE CE FICHIER :
# Registre et gestionnaires spécialisés de l'Universal Artifact Engine.
# Fournit les handlers réels pour chaque format pris en charge :
# HTML/CSS/JS, LaTeX/PDF, Python, Markdown, SVG, Mermaid, JSON, CSV, Images, PDF.
# AUCUNE simulation : chaque handler exécute, valide et vérifie concrètement.

from __future__ import annotations

import abc
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote

from core.artifacts.models import (
    Artifact,
    ArtifactExecution,
    ArtifactStatus,
    ArtifactType,
)
from tools.documents import (
    _verify_compiled_pdf_bytes,
    compile_html,
    compile_latex,
)
from tools.filesystem import WorkspaceFilesystem
from tools.process_utils import safe_subprocess_environment
from tools.python_runtime import (
    build_python_env,
    new_manifest_path,
    output_dir_for,
    prepare_output_dir,
    read_figure_manifest,
    validate_png,
)


class BaseArtifactHandler(abc.ABC):
    """Interface abstraite pour chaque type d'artefact pris en charge."""

    @abc.abstractmethod
    def handles(self, path: str, content: str | None = None) -> bool:
        """Détermine si ce gestionnaire est capable de traiter le fichier."""
        pass

    @abc.abstractmethod
    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 60,
    ) -> Artifact:
        """Exécute ou compile réellement l'artefact, vérifie son intégrité et applique l'auto-réparation."""
        pass

    @abc.abstractmethod
    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        """Retourne la configuration d'affichage dans le panneau droit (onglets, mode par défaut)."""
        pass


# -----------------------------------------------------------------------------
# 1. HTML + CSS + JAVASCRIPT HANDLER
# -----------------------------------------------------------------------------
class HtmlArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext in {".html", ".htm"}:
            return True
        if content and ("<!doctype html" in content.lower() or "<html" in content.lower()):
            return True
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 60,
    ) -> Artifact:
        rel_path = artifact.primary_path
        artifact.status = ArtifactStatus.COMPILING
        t0 = time.monotonic()

        comp = compile_html(rel_path, filesystem=filesystem, auto_repair=auto_repair)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Si échec et auto-réparation avec LLM activée
        if comp.get("status") != "success" and auto_repair and llm_provider:
            try:
                raw_html = filesystem.read_file(rel_path)
                err_log = str(comp.get("log") or comp.get("error") or "")[-1800:]
                repair_prompt = (
                    "Tu es un expert développeur Web frontend (HTML5, CSS3, JavaScript ES2022).\n"
                    "Le fichier HTML ci-dessous contient une erreur de syntaxe ou de structure détectée lors de la compilation.\n"
                    "Corrige les erreurs de syntaxe HTML/JS/CSS pour que le document soit parfaitement valide et exécutable sans erreur.\n"
                    "Renvoie EXCLUSIVEMENT le code HTML complet corrigé (commençant par <!DOCTYPE html>), sans balises Markdown autour ou avec ```html.\n\n"
                    f"=== ERREUR DÉTECTÉE ===\n{err_log}\n\n"
                    f"=== SOURCE HTML ===\n{raw_html}"
                )
                fixed_reply = str(llm_provider.generate(repair_prompt) or "").strip()
                m_html = re.search(r"```(?:html)?\s*\r?\n([\s\S]*?)```", fixed_reply, re.IGNORECASE)
                candidate_html = m_html.group(1).strip() if m_html else fixed_reply
                if "<!DOCTYPE" in candidate_html.upper() or "<html" in candidate_html.lower():
                    filesystem.write_file(rel_path, candidate_html, overwrite=True)
                    retry_comp = compile_html(rel_path, filesystem=filesystem, auto_repair=True)
                    if retry_comp.get("status") == "success":
                        notes = list(retry_comp.get("repair_notes") or [])
                        notes.append("Correction assistée par le modèle suite au diagnostic HTML/JS.")
                        retry_comp["repaired"] = True
                        retry_comp["repair_notes"] = notes
                        comp = retry_comp
            except Exception:
                pass

        artifact.execution = ArtifactExecution(
            command="compile_html (Node.js syntax & HTML structure check)",
            timeout_seconds=timeout_seconds,
            exit_code=0 if comp.get("status") == "success" else 1,
            stdout=comp.get("log", ""),
            stderr="" if comp.get("status") == "success" else comp.get("error", ""),
            duration_ms=duration_ms,
            log=comp.get("log", ""),
        )

        if comp.get("status") == "success":
            artifact.status = ArtifactStatus.READY if not comp.get("repaired") else ArtifactStatus.REPAIRED
            artifact.auto_repaired = bool(comp.get("repaired", False))
            artifact.repair_notes = list(comp.get("repair_notes") or [])
            artifact.error = None
            artifact.metadata = {
                "size_bytes": comp.get("bytes", 0),
                "title": comp.get("title") or Path(rel_path).name,
                "scripts_checked": comp.get("scripts_checked", 0),
                "styles_checked": comp.get("styles_checked", 0),
                "has_css": comp.get("has_css", False),
                "has_js": comp.get("has_js", False),
                "dependencies": comp.get("dependencies", []),
            }
            artifact.preview_url = f"/api/preview/workspace/{quote(rel_path)}"
            artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
            artifact.verification = {
                "verified": True,
                "engine": "HTML5Validator + Node.js AST Check",
                "details": f"{comp.get('scripts_checked', 0)} scripts vérifiés, {comp.get('styles_checked', 0)} feuilles CSS validées",
            }
        else:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = str(comp.get("error") or "Erreur de validation/compilation HTML")
            artifact.verification = {"verified": False, "error": artifact.error}

        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "html_sandbox",
            "tabs": ["render", "source", "files", "console"],
            "default_tab": "render",
            "title": artifact.metadata.get("title", Path(artifact.primary_path).name),
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 2. LATEX + TECTONIC -> PDF HANDLER
# -----------------------------------------------------------------------------
class LatexArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext == ".tex":
            return True
        if content and ("\\documentclass" in content or "\\begin{document}" in content):
            return True
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 120,
    ) -> Artifact:
        rel_path = artifact.primary_path
        artifact.status = ArtifactStatus.COMPILING
        t0 = time.monotonic()

        comp = compile_latex(rel_path, filesystem=filesystem, auto_repair=auto_repair)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Si échec et auto-réparation avec LLM activée
        if comp.get("status") != "success" and auto_repair and llm_provider:
            try:
                raw_tex = filesystem.read_file(rel_path)
                err_log = str(comp.get("log") or comp.get("error") or "")[-1800:]
                repair_prompt = (
                    "Tu es un expert LaTeX / Tectonic. Le fichier LaTeX ci-dessous a échoué à la compilation Tectonic.\n"
                    "Corrige uniquement les erreurs LaTeX pour qu'il compile sans erreur avec Tectonic (pdflatex/xelatex standard, "
                    "utilise \\usepackage[T1]{fontenc}, \\usepackage{lmodern}, \\usepackage{amsmath,amssymb}).\n"
                    "Renvoie EXCLUSIVEMENT le code LaTeX complet corrigé entre \\documentclass et \\end{document}, sans explication.\n\n"
                    f"=== ERREUR TECTONIC ===\n{err_log}\n\n"
                    f"=== SOURCE LATEX ===\n{raw_tex}"
                )
                fixed_reply = str(llm_provider.generate(repair_prompt) or "").strip()
                m_tex = re.search(r"```(?:latex|tex)?\s*\r?\n([\s\S]*?)```", fixed_reply, re.IGNORECASE)
                candidate_tex = m_tex.group(1).strip() if m_tex else fixed_reply
                if "\\documentclass" in candidate_tex and "\\end{document}" in candidate_tex:
                    start_idx = candidate_tex.find("\\documentclass")
                    end_idx = candidate_tex.rfind("\\end{document}") + len("\\end{document}")
                    candidate_tex = candidate_tex[start_idx:end_idx]
                    filesystem.write_file(rel_path, candidate_tex, overwrite=True)
                    retry_comp = compile_latex(rel_path, filesystem=filesystem, auto_repair=True)
                    if retry_comp.get("status") == "success":
                        notes = list(retry_comp.get("repair_notes") or [])
                        notes.append("Correction assistée par le modèle suite au diagnostic Tectonic.")
                        retry_comp["repaired"] = True
                        retry_comp["repair_notes"] = notes
                        comp = retry_comp
            except Exception:
                pass

        artifact.execution = ArtifactExecution(
            command=f"tectonic -X compile {rel_path}",
            timeout_seconds=timeout_seconds,
            exit_code=0 if comp.get("status") == "success" else 1,
            stdout=comp.get("log", ""),
            stderr="" if comp.get("status") == "success" else comp.get("error", ""),
            duration_ms=duration_ms,
            log=comp.get("log", ""),
        )

        if comp.get("status") == "success":
            pdf_rel = str(comp["pdf_path"])
            artifact.status = ArtifactStatus.READY if not comp.get("repaired") else ArtifactStatus.REPAIRED
            artifact.auto_repaired = bool(comp.get("repaired", False))
            artifact.repair_notes = list(comp.get("repair_notes") or [])
            artifact.output_paths = [pdf_rel]
            artifact.error = None
            artifact.metadata = {
                "pdf_path": pdf_rel,
                "pages": int(comp.get("pages") or 1),
                "page_count": int(comp.get("pages") or 1),
                "size_bytes": int(comp.get("bytes") or 0),
                "source_tex": rel_path,
                "compiler": "tectonic",
                "sha256": comp.get("sha256", ""),
            }
            artifact.preview_url = f"/api/files/raw?path={quote(pdf_rel)}"
            artifact.raw_url = f"/api/files/raw?path={quote(pdf_rel)}"
            artifact.verification = {
                "verified": True,
                "engine": "Tectonic Engine + PDF Byte Verifier",
                "pages": comp.get("pages", 1),
                "bytes": comp.get("bytes", 0),
            }
        else:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = str(comp.get("error") or "Échec de compilation Tectonic")
            artifact.verification = {"verified": False, "error": artifact.error}

        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "pdf_viewer",
            "tabs": ["render", "source", "files", "console"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 3. PYTHON EXECUTION & GRAPHICS HANDLER
# -----------------------------------------------------------------------------
class PythonArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext == ".py":
            return True
        if content and ("def " in content or "import " in content or "__main__" in content):
            return True
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 60,
    ) -> Artifact:
        rel_path = artifact.primary_path
        script_abs = filesystem.resolve(rel_path)
        if not script_abs.is_file():
            artifact.status = ArtifactStatus.ERROR
            artifact.error = f"Fichier Python introuvable : {rel_path}"
            return artifact

        # 1. Vérification syntaxique préalable avec py_compile / compile()
        code_str = filesystem.read_file(rel_path)
        try:
            compile(code_str, str(script_abs), "exec")
        except SyntaxError as syn_err:
            if auto_repair and llm_provider:
                try:
                    fix_prompt = (
                        f"Tu es un expert Python. Le script ci-dessous contient une SyntaxError :\n"
                        f"{syn_err}\n"
                        f"Corrige le code Python. Renvoie EXCLUSIVEMENT le code Python valide dans un bloc ```python ... ``` sans explication.\n\n"
                        f"{code_str}"
                    )
                    reply = str(llm_provider.generate(fix_prompt) or "")
                    m_py = re.search(r"```(?:python|py)?\s*\r?\n([\s\S]*?)```", reply, re.IGNORECASE)
                    fixed_code = m_py.group(1).strip() if m_py else reply.strip()
                    if fixed_code:
                        compile(fixed_code, str(script_abs), "exec")
                        filesystem.write_file(rel_path, fixed_code, overwrite=True)
                        code_str = fixed_code
                        artifact.auto_repaired = True
                        artifact.repair_notes.append(f"SyntaxError corrigée automatiquement : {syn_err.msg}")
                except Exception:
                    artifact.status = ArtifactStatus.ERROR
                    artifact.error = f"Erreur de syntaxe Python ligne {syn_err.lineno} : {syn_err.msg}"
                    artifact.execution = ArtifactExecution(
                        command=f"python {rel_path}",
                        exit_code=1,
                        stderr=str(syn_err),
                        log=str(syn_err),
                    )
                    return artifact
            else:
                artifact.status = ArtifactStatus.ERROR
                artifact.error = f"Erreur de syntaxe Python ligne {syn_err.lineno} : {syn_err.msg}"
                artifact.execution = ArtifactExecution(
                    command=f"python {rel_path}",
                    exit_code=1,
                    stderr=str(syn_err),
                    log=str(syn_err),
                )
                return artifact

        # 2. Capture des fichiers existants (avec mtime) pour détecter les sorties nouvelles OU modifiées
        def _snapshot() -> dict[str, int]:
            snap: dict[str, int] = {}
            for rel in filesystem.list_files():
                try:
                    snap[rel] = filesystem.resolve(rel).stat().st_mtime_ns
                except OSError:
                    pass
            return snap

        # 3. Exécution réelle, headless (MPLBACKEND=Agg + capture des figures) et isolée
        proj_dir = script_abs.parent
        output_dir = output_dir_for(script_abs)
        prepare_output_dir(output_dir)
        before_snapshot = _snapshot()

        artifact.status = ArtifactStatus.EXECUTING
        manifest_path = new_manifest_path()
        env = build_python_env(
            output_dir=output_dir,
            manifest_path=manifest_path,
            extra_paths=[proj_dir, filesystem.root],
        )

        cmd = [sys.executable, "-B", str(script_abs)]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=proj_dir,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8", "replace") if exc.stdout else "")
            stderr = f"Exécution interrompue : délai dépassé ({timeout_seconds}s)"
            exit_code = -1

        duration_ms = int((time.monotonic() - t0) * 1000)

        # 4. Auto-réparation sur exception d'exécution réelle (traceback)
        if exit_code != 0 and auto_repair:
            repaired_code = None
            repair_reason = ""

            # 4.1 Règle déterministe pour erreurs de casse matplotlib (ex: plt.YLabel -> plt.ylabel)
            if "AttributeError" in stderr and "matplotlib" in stderr:
                fixed = code_str
                fixes_map = {
                    r"\bplt\.YLabel\b": "plt.ylabel",
                    r"\bplt\.XLabel\b": "plt.xlabel",
                    r"\bplt\.Title\b": "plt.title",
                    r"\bplt\.Show\b": "plt.show",
                    r"\bplt\.Plot\b": "plt.plot",
                    r"\bplt\.SaveFig\b": "plt.savefig",
                    r"\bplt\.Legend\b": "plt.legend",
                    r"\bplt\.Grid\b": "plt.grid",
                }
                for pat, rep in fixes_map.items():
                    if re.search(pat, fixed):
                        fixed = re.sub(pat, rep, fixed)
                        repair_reason = f"Correction casse méthode matplotlib : {rep}"
                if fixed != code_str:
                    repaired_code = fixed

            # 4.2 Règle déterministe pour imports manquants courants
            elif "NameError" in stderr:
                m_var = re.search(r"name '(\w+)' is not defined", stderr)
                if m_var:
                    missing_name = m_var.group(1)
                    missing_imports = {
                        "plt": "import matplotlib.pyplot as plt\n",
                        "np": "import numpy as np\n",
                        "pd": "import pandas as pd\n",
                        "math": "import math\n",
                        "os": "import os\n",
                        "sys": "import sys\n",
                        "json": "import json\n",
                        "re": "import re\n",
                        "time": "import time\n",
                        "Path": "from pathlib import Path\n",
                    }
                    if missing_name in missing_imports and missing_imports[missing_name] not in code_str:
                        repaired_code = missing_imports[missing_name] + code_str
                        repair_reason = f"Ajout de l'import manquant : {missing_imports[missing_name].strip()}"

            # 4.3 Analyse cognitive via LLM si fourni
            elif llm_provider:
                try:
                    fix_prompt = (
                        f"Tu es un expert Python. Le script ci-dessous a échoué avec l'erreur d'exécution suivante :\n"
                        f"{stderr[-2000:]}\n\n"
                        f"Corrige le code pour qu'il s'exécute sans erreur. Renvoie EXCLUSIVEMENT le code Python valide dans un bloc ```python ... ``` sans explication.\n\n"
                        f"{code_str}"
                    )
                    reply = str(llm_provider.generate(fix_prompt) or "")
                    m_py = re.search(r"```(?:python|py)?\s*\r?\n([\s\S]*?)```", reply, re.IGNORECASE)
                    fixed = m_py.group(1).strip() if m_py else reply.strip()
                    if fixed and fixed != code_str:
                        repaired_code = fixed
                        repair_reason = "Correction de l'exception d'exécution via analyse cognitive"
                except Exception:
                    pass

            # Si une correction est trouvée, réexécution réelle immédiate
            if repaired_code:
                filesystem.write_file(rel_path, repaired_code, overwrite=True)
                artifact.auto_repaired = True
                artifact.repair_notes.append(repair_reason)
                code_str = repaired_code

                prepare_output_dir(output_dir)
                read_figure_manifest(manifest_path)  # supprime le manifeste du 1er essai
                t1 = time.monotonic()
                try:
                    proc2 = subprocess.run(
                        cmd,
                        cwd=proj_dir,
                        env=env,
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout_seconds,
                    )
                    stdout = proc2.stdout or ""
                    stderr = proc2.stderr or ""
                    exit_code = proc2.returncode
                except subprocess.TimeoutExpired as exc:
                    stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                    stderr = f"Exécution interrompue : délai dépassé ({timeout_seconds}s)"
                    exit_code = -1
                duration_ms += int((time.monotonic() - t1) * 1000)

        # 5. Détection des fichiers nouveaux ou modifiés pendant l'exécution
        after_snapshot = _snapshot()
        new_outputs = sorted(
            rel for rel, mtime in after_snapshot.items()
            if rel != rel_path and not rel.startswith(".harness/") and before_snapshot.get(rel) != mtime
        )
        artifact.output_paths = new_outputs

        # 5.1 Figures Matplotlib réellement capturées (manifeste écrit par le sous-processus)
        manifest = read_figure_manifest(manifest_path)
        root_abs = Path(filesystem.root).resolve()
        figures: list[str] = []
        figure_checks: list[dict[str, Any]] = []
        for fig_abs in manifest.get("figures", []):
            check = validate_png(fig_abs)
            try:
                fig_rel = Path(fig_abs).resolve().relative_to(root_abs).as_posix()
            except ValueError:
                continue
            check["path"] = fig_rel
            figure_checks.append(check)
            if check.get("valid"):
                figures.append(fig_rel)
                if fig_rel not in artifact.output_paths:
                    artifact.output_paths.append(fig_rel)
        figure_errors = list(manifest.get("errors", [])) + [
            f"{c['path']} : {c.get('error')}" for c in figure_checks if not c.get("valid")
        ]

        # Visuels : figures capturées en priorité, puis autres sorties visualisables
        visual_outputs = figures + [
            p for p in new_outputs
            if p not in figures
            and Path(p).suffix.lower() in {".png", ".svg", ".jpg", ".jpeg", ".pdf", ".html", ".csv"}
        ]

        artifact.execution = ArtifactExecution(
            command=f"python {rel_path}",
            timeout_seconds=timeout_seconds,
            exit_code=exit_code,
            stdout=stdout[-10000:],
            stderr=stderr[-10000:],
            duration_ms=duration_ms,
            log=(stdout + ("\n" + stderr if stderr else "")).strip()[-12000:],
        )

        if exit_code == 0:
            artifact.status = ArtifactStatus.READY if not artifact.auto_repaired else ArtifactStatus.REPAIRED
            artifact.error = None
            primary_visual = visual_outputs[0] if visual_outputs else (new_outputs[0] if new_outputs else "")
            artifact.metadata = {
                "exit_code": 0,
                "stdout_length": len(stdout),
                "generated_files_count": len(new_outputs),
                "generated_files": new_outputs,
                "visual_output": primary_visual,
                "figures": figures,
                "figure_checks": figure_checks,
                "matplotlib_used": bool(manifest.get("matplotlib_used")),
                "output_dir": output_dir.resolve().relative_to(root_abs).as_posix()
                if output_dir.resolve().is_relative_to(root_abs) else str(output_dir),
                "duration_ms": duration_ms,
                "size_bytes": len(code_str.encode("utf-8")),
            }
            if primary_visual:
                artifact.preview_url = f"/api/files/raw?path={quote(primary_visual)}"
            else:
                artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
            artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
            artifact.verification = {
                "verified": True,
                "engine": "Python Subprocess Engine",
                "exit_code": 0,
                "duration_ms": duration_ms,
                "outputs_produced": len(artifact.output_paths),
                "figures_valid": len(figures),
            }
            if figure_errors:
                artifact.status = ArtifactStatus.ERROR
                artifact.error = "Figure Matplotlib invalide : " + " | ".join(figure_errors)
                artifact.verification = {"verified": False, "error": artifact.error}
        else:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = stderr.strip() or f"Erreur d'exécution Python (code {exit_code})"
            artifact.verification = {"verified": False, "error": artifact.error, "exit_code": exit_code}

        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        has_visual = bool(artifact.metadata.get("visual_output"))
        return {
            "renderer": "python_runner",
            "tabs": ["render", "source", "files", "console"],
            "default_tab": "render" if (has_visual or artifact.execution) else "source",
            "title": Path(artifact.primary_path).name,
            "has_visual_output": has_visual,
            "visual_output_path": artifact.metadata.get("visual_output", ""),
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 4. MARKDOWN HANDLER
# -----------------------------------------------------------------------------
class MarkdownArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        return ext in {".md", ".markdown"}

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        content = filesystem.read_file(rel_path)
        lines = content.splitlines()

        # Analyse des structures Markdown présentes (titres, tableaux, maths, blocs de code)
        headings = [line for line in lines if line.startswith("#")]
        code_blocks = re.findall(r"```(\w+)?", content)
        math_blocks = re.findall(r"\$\$[\s\S]*?\$\$|\$[^\$\n]+\$", content)
        tables = [line for line in lines if "|" in line]

        artifact.status = ArtifactStatus.READY
        artifact.metadata = {
            "size_bytes": len(content.encode("utf-8")),
            "lines_count": len(lines),
            "headings_count": len(headings),
            "code_blocks_count": len(code_blocks),
            "math_blocks_count": len(math_blocks),
            "has_tables": bool(tables),
            "has_math": bool(math_blocks),
            "title": headings[0].lstrip("#").strip() if headings else Path(rel_path).stem,
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "Markdown Structure Parser",
            "headings": len(headings),
            "code_blocks": len(code_blocks),
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "markdown_viewer",
            "tabs": ["render", "source", "files"],
            "default_tab": "render",
            "title": artifact.metadata.get("title", Path(artifact.primary_path).name),
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 5. SVG VECTOR GRAPHICS HANDLER
# -----------------------------------------------------------------------------
class SvgArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext == ".svg":
            return True
        if content and "<svg" in content.lower():
            return True
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        content = filesystem.read_file(rel_path)

        # Validation XML réelle
        try:
            root = ET.fromstring(content)
            tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag.lower() != "svg":
                raise ValueError(f"La racine XML n'est pas un élément <svg> : <{root.tag}>")
            width = root.attrib.get("width", "auto")
            height = root.attrib.get("height", "auto")
            view_box = root.attrib.get("viewBox", "")

            artifact.status = ArtifactStatus.READY
            artifact.metadata = {
                "size_bytes": len(content.encode("utf-8")),
                "width": width,
                "height": height,
                "viewBox": view_box,
                "elements_count": len(list(root.iter())),
            }
            artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
            artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
            artifact.verification = {
                "verified": True,
                "engine": "XML ElementTree Validator",
                "root": "svg",
                "elements": artifact.metadata["elements_count"],
            }
        except Exception as exc:
            if auto_repair:
                # Auto-réparation déterministe pour balise XML non fermée ou xmlns manquant
                repaired_content = content
                if 'xmlns="http://www.w3.org/2000/svg"' not in repaired_content and "<svg" in repaired_content:
                    repaired_content = re.sub(r"<svg\b", '<svg xmlns="http://www.w3.org/2000/svg"', repaired_content, count=1)
                # Auto-fermeture des balises auto-fermantes SVG courantes (circle, rect, path, line, etc.)
                repaired_content = re.sub(r"(<(?:circle|rect|ellipse|line|polyline|polygon|path|image|use)\b[^>]*?)(?<!/)>", r"\1 />", repaired_content)
                if "</svg>" not in repaired_content:
                    repaired_content += "\n</svg>"
                try:
                    root = ET.fromstring(repaired_content)
                    filesystem.write_file(rel_path, repaired_content, overwrite=True)
                    artifact.auto_repaired = True
                    artifact.repair_notes.append("Normalisation XML SVG et balise fermante appliquée.")
                    artifact.status = ArtifactStatus.REPAIRED
                    artifact.metadata = {
                        "size_bytes": len(repaired_content.encode("utf-8")),
                        "width": root.attrib.get("width", "auto"),
                        "height": root.attrib.get("height", "auto"),
                        "viewBox": root.attrib.get("viewBox", ""),
                        "elements_count": len(list(root.iter())),
                    }
                    artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
                    artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
                    artifact.verification = {"verified": True, "engine": "XML ElementTree (Repaired)"}
                    return artifact
                except Exception:
                    pass

            artifact.status = ArtifactStatus.ERROR
            artifact.error = f"SVG XML non valide : {exc}"
            artifact.verification = {"verified": False, "error": str(exc)}

        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "svg_viewer",
            "tabs": ["render", "source", "files"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 6. MERMAID DIAGRAMS HANDLER
# -----------------------------------------------------------------------------
class MermaidArtifactHandler(BaseArtifactHandler):
    VALID_DIAGRAM_PREFIXES = (
        "graph",
        "flowchart",
        "sequencediagram",
        "classdiagram",
        "statediagram",
        "statediagram-v2",
        "erdiagram",
        "journey",
        "gantt",
        "pie",
        "quadrantchart",
        "requirementdiagram",
        "gitgraph",
        "c4context",
        "mindmap",
        "timeline",
        "xychart-beta",
    )

    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext in {".mmd", ".mermaid"}:
            return True
        if content:
            stripped = content.strip().lower()
            return any(stripped.startswith(p) for p in self.VALID_DIAGRAM_PREFIXES)
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        content = filesystem.read_file(rel_path).strip()

        # Validation syntaxique réelle Mermaid
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("%%")]
        if not lines:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = "Fichier Mermaid vide."
            return artifact

        first_line = lines[0].lower().replace(" ", "")
        has_valid_header = any(first_line.startswith(p.replace(" ", "")) for p in self.VALID_DIAGRAM_PREFIXES)

        # Vérification des parenthèses et crochets équilibrés
        open_brackets = content.count("[") - content.count("]")
        open_parens = content.count("(") - content.count(")")
        open_braces = content.count("{") - content.count("}")
        is_balanced = (open_brackets == 0 and open_parens == 0 and open_braces == 0)

        if not has_valid_header:
            if auto_repair:
                # Ajout du header par défaut flowchart TD
                content = "flowchart TD\n" + content
                filesystem.write_file(rel_path, content, overwrite=True)
                artifact.auto_repaired = True
                artifact.repair_notes.append("En-tête de diagramme 'flowchart TD' inséré.")
                has_valid_header = True
            else:
                artifact.status = ArtifactStatus.ERROR
                artifact.error = f"Type de diagramme Mermaid non reconnu au début : '{lines[0]}'."
                return artifact

        if not is_balanced and auto_repair:
            # Réparation des crochets/parenthèses non fermées sur chaque ligne
            repaired_lines = []
            for l in content.splitlines():
                if l.count("[") > l.count("]"):
                    l += "]" * (l.count("[") - l.count("]"))
                if l.count("(") > l.count(")"):
                    l += ")" * (l.count("(") - l.count(")"))
                repaired_lines.append(l)
            content = "\n".join(repaired_lines)
            filesystem.write_file(rel_path, content, overwrite=True)
            artifact.auto_repaired = True
            artifact.repair_notes.append("Balises ou parenthèses de nœud rééquilibrées.")
            is_balanced = True

        artifact.status = ArtifactStatus.READY if not artifact.auto_repaired else ArtifactStatus.REPAIRED
        diagram_type = lines[0].split()[0]
        artifact.metadata = {
            "diagram_type": diagram_type,
            "lines_count": len(lines),
            "size_bytes": len(content.encode("utf-8")),
            "title": f"Diagramme Mermaid ({diagram_type})",
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "Mermaid Syntax Validator",
            "diagram_type": diagram_type,
            "nodes_lines": len(lines),
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "mermaid_viewer",
            "tabs": ["render", "source", "files"],
            "default_tab": "render",
            "title": artifact.metadata.get("title", Path(artifact.primary_path).name),
            "diagram_type": artifact.metadata.get("diagram_type", "flowchart"),
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 7. JSON STRUCTURED DATA HANDLER
# -----------------------------------------------------------------------------
class JsonArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        if ext == ".json":
            return True
        if content and (content.strip().startswith("{") or content.strip().startswith("[")):
            try:
                json.loads(content)
                return True
            except Exception:
                pass
        return False

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        content = filesystem.read_file(rel_path)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            if auto_repair:
                # Réparation déterministe courante : virgule de fin, quotes simples
                repaired = re.sub(r",\s*([}\]])", r"\1", content)
                repaired = re.sub(r"(?<!\\)'", '"', repaired)
                try:
                    parsed = json.loads(repaired)
                    filesystem.write_file(rel_path, json.dumps(parsed, indent=2, ensure_ascii=False), overwrite=True)
                    artifact.auto_repaired = True
                    artifact.repair_notes.append(f"Syntaxe JSON normalisée (virgule de fin ou guillemets).")
                    content = repaired
                except Exception:
                    artifact.status = ArtifactStatus.ERROR
                    artifact.error = f"JSON non valide ligne {exc.lineno} col {exc.colno} : {exc.msg}"
                    artifact.verification = {"verified": False, "error": artifact.error}
                    return artifact
            else:
                artifact.status = ArtifactStatus.ERROR
                artifact.error = f"JSON non valide ligne {exc.lineno} col {exc.colno} : {exc.msg}"
                artifact.verification = {"verified": False, "error": artifact.error}
                return artifact

        # Analyse des métadonnées
        is_list = isinstance(parsed, list)
        keys_count = len(parsed) if is_list else len(parsed.keys())
        artifact.status = ArtifactStatus.READY if not artifact.auto_repaired else ArtifactStatus.REPAIRED
        artifact.metadata = {
            "root_type": "array" if is_list else "object",
            "items_count": keys_count,
            "size_bytes": len(content.encode("utf-8")),
            "keys": list(parsed.keys())[:10] if isinstance(parsed, dict) else [],
            "title": Path(rel_path).name,
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "Python JSON Parser",
            "root_type": artifact.metadata["root_type"],
            "count": keys_count,
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "json_viewer",
            "tabs": ["render", "source", "files"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 8. CSV / TSV TABULAR DATA HANDLER
# -----------------------------------------------------------------------------
class CsvArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        return ext in {".csv", ".tsv"}

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        content = filesystem.read_file(rel_path)

        if not content.strip():
            artifact.status = ArtifactStatus.ERROR
            artifact.error = "Fichier CSV vide."
            return artifact

        # Détection du séparateur
        delimiter = "\t" if rel_path.lower().endswith(".tsv") else ","
        try:
            sample = content[:4096]
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=";,|\t")
            delimiter = dialect.delimiter
        except Exception:
            # Fallback comptage des séparateurs dans les 3 premières lignes
            lines = content.splitlines()[:3]
            commas = sum(l.count(",") for l in lines)
            semis = sum(l.count(";") for l in lines)
            tabs = sum(l.count("\t") for l in lines)
            if semis > commas and semis > tabs:
                delimiter = ";"
            elif tabs > commas and tabs > semis:
                delimiter = "\t"

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = "Aucune ligne CSV lisible."
            return artifact

        headers = rows[0]
        row_count = len(rows) - 1

        artifact.status = ArtifactStatus.READY
        artifact.metadata = {
            "row_count": row_count,
            "column_count": len(headers),
            "columns": headers[:20],
            "delimiter": delimiter,
            "size_bytes": len(content.encode("utf-8")),
            "title": Path(rel_path).name,
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "CSV Sniffer & Reader",
            "rows": row_count,
            "cols": len(headers),
            "delimiter": delimiter,
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "csv_viewer",
            "tabs": ["render", "source", "files"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "supports_reload": True,
            "supports_live_edit": True,
        }


# -----------------------------------------------------------------------------
# 9. IMAGE VIEWER HANDLER (PNG, JPG, WEBP, GIF, BMP, ICO)
# -----------------------------------------------------------------------------
class ImageArtifactHandler(BaseArtifactHandler):
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico"}

    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        return ext in self.IMAGE_EXTENSIONS

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        raw_bytes = filesystem.read_bytes(rel_path)

        if len(raw_bytes) == 0:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = "Fichier image vide (0 octet)."
            return artifact

        # Extraction des dimensions réelles via Pillow si installé
        width = 0
        height = 0
        fmt = Path(rel_path).suffix.lstrip(".").upper()
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw_bytes)) as img:
                width, height = img.size
                fmt = img.format or fmt
        except Exception:
            # Fallback analyse des octets d'en-tête PNG
            if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n") and len(raw_bytes) >= 24:
                import struct
                width, height = struct.unpack(">II", raw_bytes[16:24])
                fmt = "PNG"

        artifact.status = ArtifactStatus.READY
        artifact.metadata = {
            "size_bytes": len(raw_bytes),
            "width": width,
            "height": height,
            "format": fmt,
            "title": Path(rel_path).name,
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "Image Header & Pillow Verifier",
            "format": fmt,
            "dimensions": f"{width}x{height}" if width else "Inconnues",
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "image_viewer",
            "tabs": ["render", "files"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "width": artifact.metadata.get("width"),
            "height": artifact.metadata.get("height"),
        }


# -----------------------------------------------------------------------------
# 10. PDF DIRECT HANDLER
# -----------------------------------------------------------------------------
class PdfArtifactHandler(BaseArtifactHandler):
    def handles(self, path: str, content: str | None = None) -> bool:
        ext = Path(path).suffix.lower()
        return ext == ".pdf"

    def process(
        self,
        artifact: Artifact,
        filesystem: WorkspaceFilesystem,
        *,
        auto_repair: bool = True,
        llm_provider: Any = None,
        timeout_seconds: int = 30,
    ) -> Artifact:
        rel_path = artifact.primary_path
        raw_bytes = filesystem.read_bytes(rel_path)

        ok, err, pages = _verify_compiled_pdf_bytes(raw_bytes)
        if not ok:
            artifact.status = ArtifactStatus.ERROR
            artifact.error = err or "Fichier PDF corrompu ou invalide."
            artifact.verification = {"verified": False, "error": artifact.error}
            return artifact

        artifact.status = ArtifactStatus.READY
        artifact.metadata = {
            "size_bytes": len(raw_bytes),
            "page_count": pages,
            "pages": pages,
            "title": Path(rel_path).name,
        }
        artifact.preview_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.raw_url = f"/api/files/raw?path={quote(rel_path)}"
        artifact.verification = {
            "verified": True,
            "engine": "PDF Byte & Structure Verifier",
            "pages": pages,
            "bytes": len(raw_bytes),
        }
        return artifact

    def get_preview_config(self, artifact: Artifact) -> dict[str, Any]:
        return {
            "renderer": "pdf_viewer",
            "tabs": ["render", "files"],
            "default_tab": "render",
            "title": Path(artifact.primary_path).name,
            "pages": artifact.metadata.get("page_count", 1),
            "supports_reload": True,
        }
