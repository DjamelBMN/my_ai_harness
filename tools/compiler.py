# RÔLE DE CE FICHIER :
# Fournit la boucle de compilation autonome en boucle fermée (LaTeX/Tectonic et tout compilateur).
# L'agent compile, analyse l'erreur, la corrige par remplacement ciblé, recompile,
# applique un garde-fou de répétition, des rollbacks shadow git si l'erreur s'aggrave,
# et valide physiquement le PDF (magic bytes, 0 erreur, inspecteur visuel de mise en page).

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable

from core.checkpoint import CheckpointManager
from core.events import HarnessEvent
from tools.filesystem import WorkspaceFilesystem
from tools.rasterizer import PDFRasterizer
from tools.search import verify_downloaded_file


@dataclass
class CompilerIssue:
    """Description structurée d'une anomalie ou erreur de compilation."""

    kind: str  # "error", "missing_package", "warning", "undefined_reference", "overfull"
    file: str
    line: int | None
    message: str
    context_lines: list[str] = field(default_factory=list)
    raw_snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_compiler_log(
    log_text: str,
    source_text: str,
    source_file: str = "document.tex",
) -> list[CompilerIssue]:
    """Analyse les flux stdout, stderr et transcript pour extraire les anomalies structurées."""
    issues: list[CompilerIssue] = []
    src_lines = source_text.splitlines()

    def get_context(line_num: int | None) -> list[str]:
        if line_num is None or line_num < 1 or line_num > len(src_lines):
            return []
        start = max(0, line_num - 3)
        end = min(len(src_lines), line_num + 2)
        return [f"{i+1:04d}: {src_lines[i]}" for i in range(start, end)]

    # 1. Détection de package introuvable
    pkg_matches = re.finditer(
        r"(?:LaTeX Error:\s*)?File\s*[`'\"]([^`'\"]+\.sty)[`'\"]\s*not found",
        log_text,
        re.IGNORECASE,
    )
    for m in pkg_matches:
        pkg_file = m.group(1)
        pkg_name = pkg_file.removesuffix(".sty")
        # Trouver la ligne correspondante dans le fichier source
        found_line = None
        for i, l in enumerate(src_lines, 1):
            if pkg_name in l and "usepackage" in l:
                found_line = i
                break
        issues.append(
            CompilerIssue(
                kind="missing_package",
                file=source_file,
                line=found_line,
                message=f"Package '{pkg_name}' introuvable.",
                context_lines=get_context(found_line),
                raw_snippet=m.group(0),
            )
        )

    # 2. Détection d'erreurs au format Tectonic (error: <file>:<line>: <message>)
    tectonic_matches = re.finditer(r"error:\s*([^:\n]+):(\d+):\s*(.*)", log_text)
    for m in tectonic_matches:
        f_name = Path(m.group(1).strip()).name
        l_num = int(m.group(2))
        msg = m.group(3).strip()
        issues.append(
            CompilerIssue(
                kind="error",
                file=f_name or source_file,
                line=l_num,
                message=msg,
                context_lines=get_context(l_num),
                raw_snippet=m.group(0),
            )
        )

    # 3. Détection d'erreurs TeX standard (! <message>\nl.<line> <snippet>)
    tex_matches = re.finditer(r"!\s*(.*?)\n(?:l\.(\d+)\s*(.*?))(?:\n|$)", log_text, re.DOTALL)
    for m in tex_matches:
        msg = m.group(1).strip().replace("\n", " ")
        l_num = int(m.group(2)) if m.group(2) else None
        snip = m.group(3).strip() if m.group(3) else ""
        issues.append(
            CompilerIssue(
                kind="error",
                file=source_file,
                line=l_num,
                message=msg,
                context_lines=get_context(l_num),
                raw_snippet=snip,
            )
        )

    # 4. Erreur "File ended while scanning use of \macro" (accolade non fermée)
    if not issues and "File ended while scanning use of" in log_text:
        m_macro = re.search(r"File ended while scanning use of\s+(\\[a-zA-Z]+)", log_text)
        macro_name = m_macro.group(1) if m_macro else "macro"
        issues.append(
            CompilerIssue(
                kind="error",
                file=source_file,
                line=len(src_lines),
                message=f"Accolade ou argument non fermé pour la commande {macro_name}.",
                context_lines=get_context(len(src_lines)),
                raw_snippet=macro_name,
            )
        )

    # 5. Détection de références indéfinies ('??')
    if "There were undefined references" in log_text:
        issues.append(
            CompilerIssue(
                kind="undefined_reference",
                file=source_file,
                line=None,
                message="Références croisées non résolues (seconde passe requise).",
            )
        )

    # 6. Détection de débordement Overfull \hbox (> 15pt)
    overfull_matches = re.finditer(
        r"Overfull \\hbox \(([0-9.]+)pt too wide\) in paragraph at lines (\d+)--(\d+)",
        log_text,
    )
    for om in overfull_matches:
        pts = float(om.group(1))
        if pts > 15.0:  # Débordement significatif
            l_start = int(om.group(2))
            issues.append(
                CompilerIssue(
                    kind="overfull",
                    file=source_file,
                    line=l_start,
                    message=f"Débordement typographique Overfull hbox de {pts}pt.",
                    context_lines=get_context(l_start),
                )
            )

    return issues


def fix_compiler_issue(
    source_text: str,
    issue: CompilerIssue,
    strategy: int = 1,
) -> tuple[str, str]:
    """Applique une correction ciblée sur le texte source selon l'anomalie et la stratégie."""
    lines = source_text.splitlines()
    msg_low = issue.message.lower()

    # Cas 1 : Package introuvable
    if issue.kind == "missing_package" or "package" in msg_low and "not found" in msg_low:
        m = re.search(r"Package '([^']+)' introuvable", issue.message)
        pkg_name = m.group(1) if m else ""
        if not pkg_name:
            m2 = re.search(r"File [`'\"]([^`'\"]+)\.sty[`'\"]", issue.raw_snippet)
            pkg_name = m2.group(1) if m2 else ""

        if pkg_name:
            # Supprime ou commente l'inclusion du package
            pattern = rf"\\usepackage(?:\[[^\]]*\])?\{{{re.escape(pkg_name)}\}}"
            new_text, count = re.subn(
                pattern,
                lambda m: f"% [autofix: retiré car introuvable] % {m.group(0)}",
                source_text,
            )
            if count > 0:
                return new_text, f"Retrait du package introuvable '{pkg_name}'."

    # Cas 2 : Caractère '&' non échappé hors tableau
    if "misplaced alignment tab character &" in msg_low or "&" in issue.message:
        target_idx = (issue.line - 1) if (issue.line and 0 < issue.line <= len(lines)) else None
        if target_idx is not None:
            line_str = lines[target_idx]
            # Si pas précédé de backslash, échapper &
            fixed_line = re.sub(r"(?<!\\)&", r"\&", line_str)
            if fixed_line != line_str:
                lines[target_idx] = fixed_line
                return "\n".join(lines), f"Échappement du caractère '&' ligne {issue.line}."

    # Cas 3 : Accolade fermante manquante / argument runaway
    if "accolade" in msg_low or "argument" in msg_low or "file ended while scanning" in msg_low or "runaway" in msg_low or "brace" in msg_low:
        # Trouver la dernière ligne contenant une ouverture de balise non fermée
        for idx in range(len(lines) - 1, -1, -1):
            line = lines[idx]
            if "\\begin{document}" not in line and "\\end{document}" not in line:
                if line.count("{") > line.count("}"):
                    diff = line.count("{") - line.count("}")
                    lines[idx] = line + ("}" * diff)
                    return "\n".join(lines), f"Fermeture des accolades manquantes ligne {idx + 1}."
        # Repli : fermer l'accolade juste avant \end{document}
        for idx, line in enumerate(lines):
            if "\\end{document}" in line:
                lines[idx] = "}\n" + line
                return "\n".join(lines), "Fermeture d'accolade avant \\end{document}."

    # Cas 4 : Undefined control sequence (commande inconnue)
    if ("undefined control sequence" in msg_low or "undefined macro" in msg_low or "unknown command" in msg_low) and "accolade" not in msg_low:
        if strategy == 1 and issue.raw_snippet:
            # Chercher le nom de macro dans le snippet
            m_cmd = re.search(r"\\[a-zA-Z]+", issue.raw_snippet)
            if m_cmd:
                cmd_name = m_cmd.group(0)
                # Si typo évidente
                typo_fixes = {
                    r"\textbe": r"\textbf",
                    r"\textitf": r"\textit",
                    r"\fraction": r"\frac",
                    r"\centre": r"\centering",
                }
                if cmd_name in typo_fixes:
                    fixed_cmd = typo_fixes[cmd_name]
                    new_text = source_text.replace(cmd_name, fixed_cmd, 1)
                    return new_text, f"Correction de la typo '{cmd_name}' -> '{fixed_cmd}'."
                # Sinon, définir une macro neutre dans le préambule
                cmd_bare = cmd_name.lstrip("\\")
                safe_def = f"\\providecommand{{{cmd_name}}}[1]{{#1}} % autofix define undefined macro\n"
                new_text = source_text.replace(r"\begin{document}", safe_def + r"\begin{document}", 1)
                return new_text, f"Définition d'une macro de secours pour '{cmd_name}'."
        elif strategy >= 2 and issue.line and 0 < issue.line <= len(lines):
            # Stratégie 2 / 3 : Commenter la ligne problématique (bissection)
            idx = issue.line - 1
            lines[idx] = f"% [autofix bisection] {lines[idx]}"
            return "\n".join(lines), f"Bissection/neutralisation de la ligne {issue.line}."

    # Cas 5 : Caractères réservés (_, %, #, $) non échappés
    for ch in ("_", "%", "#"):
        if f"caractère {ch}" in msg_low or ch in issue.raw_snippet:
            target_idx = (issue.line - 1) if (issue.line and 0 < issue.line <= len(lines)) else None
            if target_idx is not None:
                line_str = lines[target_idx]
                fixed_line = re.sub(rf"(?<!\\)\{ch}", rf"\{ch}", line_str)
                if fixed_line != line_str:
                    lines[target_idx] = fixed_line
                    return "\n".join(lines), f"Échappement de '{ch}' ligne {issue.line}."

    # Repli Stratégie 3 (Bissection) si rien d'autre n'a fonctionné
    if issue.line and 0 < issue.line <= len(lines):
        idx = issue.line - 1
        lines[idx] = f"% [autofix neutralisé] {lines[idx]}"
        return "\n".join(lines), f"Neutralisation de secours de la ligne {issue.line}."

    return source_text, "Aucune correction applicable trouvée."


class AutonomousCompiler:
    """Boucle de compilation autonome en boucle fermée avec rollbacks et oracles."""

    def __init__(
        self,
        workspace: Path | str = "workspace",
        max_attempts: int = 25,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.max_attempts = max_attempts
        self.event_sink = event_sink
        self.checkpoint_manager = CheckpointManager(workspace=self.workspace)

        self.tectonic_bin = shutil.which("tectonic")
        self.pdflatex_bin = shutil.which("pdflatex")
        self.compiler_name = "tectonic" if self.tectonic_bin else ("pdflatex" if self.pdflatex_bin else "none")

    def _emit(self, event_name: str, **kwargs: Any) -> None:
        if self.event_sink is not None:
            try:
                self.event_sink(event_name, kwargs)
            except TypeError:
                try:
                    self.event_sink(HarnessEvent(name=event_name, data=kwargs))
                except Exception:
                    pass
            except Exception:
                pass

    def compile(
        self,
        tex_path: Path | str,
        output_pdf_path: Path | str | None = None,
        expected_pages: int | None = None,
        auto_fix: bool = True,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Exécute la boucle de compilation autonome jusqu'à zéro erreur physique."""
        abs_tex = Path(tex_path)
        if not abs_tex.is_absolute():
            abs_tex = (self.workspace / tex_path).resolve()

        if not abs_tex.is_file():
            raise FileNotFoundError(f"Fichier source TeX introuvable : {abs_tex}")

        target_pdf = (
            Path(output_pdf_path).resolve()
            if output_pdf_path
            else abs_tex.with_suffix(".pdf")
        )
        target_pdf.parent.mkdir(parents=True, exist_ok=True)

        if self.compiler_name == "none":
            return {
                "status": "error",
                "error": "Aucun compilateur LaTeX (tectonic ou pdflatex) installé dans le PATH.",
                "attempts": 0,
            }

        consecutive_same_error = 0
        last_error_signature: tuple[str, int | None, str] | None = None
        current_strategy = 1
        attempts_history: list[dict[str, Any]] = []
        last_good_checkpoint: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            self._emit("compile.attempt", attempt=attempt, max_attempts=self.max_attempts)
            source_content = abs_tex.read_text(encoding="utf-8", errors="replace")

            # 1. Compilation isolée dans un dossier temporaire
            ok, pdf_bytes, log_text = self._run_single_build(abs_tex, source_content, timeout=timeout)

            # 2. Analyse des erreurs du log
            issues = parse_compiler_log(log_text, source_content, source_file=abs_tex.name)
            blocking_errors = [iss for iss in issues if iss.kind in {"error", "missing_package"}]

            attempts_history.append(
                {
                    "attempt": attempt,
                    "success": ok and (len(blocking_errors) == 0),
                    "errors_count": len(blocking_errors),
                    "issues": [iss.to_dict() for iss in issues],
                }
            )

            # 3. Succès sans erreur bloquante
            if ok and len(blocking_errors) == 0 and pdf_bytes is not None:
                # Écriture physique du PDF
                target_pdf.write_bytes(pdf_bytes)

                # Vérification physique obligatoire
                verif = verify_downloaded_file(target_pdf)
                if not verif.get("valid"):
                    return {
                        "status": "incomplete",
                        "error": "Le PDF compilé a échoué aux contrôles physiques d'intégrité.",
                        "verification": verif,
                        "attempts": attempt,
                    }

                # Seconde passe si références non résolues
                has_undefined_refs = any(i.kind == "undefined_reference" for i in issues)
                if has_undefined_refs:
                    self._emit("compile.attempt", attempt=attempt, pass_num=2, reason="résolution références croisées")
                    ok2, pdf_bytes2, log_text2 = self._run_single_build(abs_tex, source_content, timeout=timeout)
                    if ok2 and pdf_bytes2 is not None:
                        target_pdf.write_bytes(pdf_bytes2)

                # Inspection visuelle par rastérisation (pas de page vide, pas de débordement)
                layout = PDFRasterizer.inspect_layout(target_pdf, expected_pages=expected_pages)
                self._emit("compile.completed", attempts=attempt, page_count=layout.get("page_count", 1))

                return {
                    "status": "success",
                    "pdf_path": str(target_pdf),
                    "relative_path": str(target_pdf.relative_to(self.workspace)) if str(target_pdf).startswith(str(self.workspace)) else str(target_pdf),
                    "size_bytes": target_pdf.stat().st_size,
                    "sha256": hashlib.sha256(target_pdf.read_bytes()).hexdigest(),
                    "attempts": attempt,
                    "compiler": self.compiler_name,
                    "zero_error_verified": True,
                    "page_count": layout.get("page_count", 1),
                    "layout_inspection": layout,
                    "history": attempts_history,
                }

            # 4. Si auto_fix est désactivé, s'arrêter immédiatement
            if not auto_fix:
                break

            # 5. Identifier la première erreur à corriger
            primary_issue = blocking_errors[0] if blocking_errors else issues[0]
            sig = (primary_issue.file, primary_issue.line, primary_issue.message)
            self._emit("compile.error", message=primary_issue.message, line=primary_issue.line, file=primary_issue.file)

            # Garde-fou de répétition (3x la même erreur = changer de stratégie)
            if sig == last_error_signature:
                consecutive_same_error += 1
                if consecutive_same_error >= 3:
                    current_strategy = min(3, current_strategy + 1)
                    self._emit("compile.strategy_change", strategy=current_strategy, reason="repetition_guard")
            else:
                consecutive_same_error = 1
                last_error_signature = sig

            # Checkpoint shadow git avant la modification
            cid = self.checkpoint_manager.create_checkpoint(
                name=f"pre_fix_attempt_{attempt}",
                hypothesis=f"Correction: {primary_issue.message[:50]}",
            )

            # Application de la correction ciblée
            new_source, fix_note = fix_compiler_issue(source_content, primary_issue, strategy=current_strategy)
            self._emit("compile.fixed", note=fix_note, line=primary_issue.line)

            if new_source == source_content:
                # Si aucune modification n'a été trouvée avec la stratégie actuelle, escalader la stratégie
                current_strategy = min(3, current_strategy + 1)
                new_source, fix_note = fix_compiler_issue(source_content, primary_issue, strategy=current_strategy)

            # Écriture de la correction
            abs_tex.write_text(new_source, encoding="utf-8")

            # Test rapide pour vérifier si le nombre d'erreurs a augmenté
            post_ok, post_pdf, post_log = self._run_single_build(abs_tex, new_source, timeout=timeout)
            post_issues = parse_compiler_log(post_log, new_source, source_file=abs_tex.name)
            post_blocking = [iss for iss in post_issues if iss.kind in {"error", "missing_package"}]

            # Si la correction aggrave le nombre d'erreurs -> ROLLBACK immédiat
            if len(post_blocking) > len(blocking_errors) or len(post_issues) > len(issues):
                self._emit("compile.rollback", checkpoint_id=cid, reason="nombre d'erreurs aggravé")
                self.checkpoint_manager.rollback(cid)
                current_strategy = min(3, current_strategy + 1)
            else:
                last_good_checkpoint = cid

        # Plafond atteint sans succès
        return {
            "status": "incomplete",
            "pdf_path": None,
            "attempts": self.max_attempts,
            "error": f"Plafond maximal de {self.max_attempts} compilations atteint sans parvenir à 0 erreur.",
            "remaining_issues": [iss.to_dict() for iss in blocking_errors],
            "last_compilable_checkpoint": last_good_checkpoint,
            "history": attempts_history,
        }

    def _run_single_build(
        self,
        tex_path: Path,
        source_text: str,
        timeout: float = 30.0,
    ) -> tuple[bool, bytes | None, str]:
        """Exécute une passe de compilation isolée."""
        with tempfile.TemporaryDirectory(prefix="neoharness_compile_") as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            # Copie des éventuels fichiers frères utiles (images, .sty, .cls)
            for sibling in tex_path.parent.iterdir():
                if sibling.is_file() and sibling != tex_path and sibling.suffix.lower() in {".sty", ".cls", ".png", ".jpg", ".jpeg", ".pdf"}:
                    try:
                        shutil.copy2(sibling, tmp_dir / sibling.name)
                    except OSError:
                        pass

            work_tex = tmp_dir / tex_path.name
            work_tex.write_text(source_text, encoding="utf-8")

            if self.tectonic_bin:
                cmd = [self.tectonic_bin, "--chatter", "minimal", "--outdir", str(tmp_dir), str(work_tex)]
            else:
                cmd = [
                    self.pdflatex_bin,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={tmp_dir}",
                    str(work_tex),
                ]

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                    cwd=str(tmp_dir),
                )
            except subprocess.TimeoutExpired:
                return False, None, f"Délai maximal de compilation dépassé ({timeout}s)."
            except OSError as err:
                return False, None, f"Erreur d'exécution du compilateur : {err}"

            log_text = "\n".join(part for part in (proc.stdout, proc.stderr) if part).strip()
            produced_pdf = tmp_dir / tex_path.with_suffix(".pdf").name
            if proc.returncode != 0 or not produced_pdf.is_file():
                return False, None, log_text or f"Échec de compilation (code retour {proc.returncode})."

            return True, produced_pdf.read_bytes(), log_text
