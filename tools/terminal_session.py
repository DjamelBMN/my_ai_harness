# RÔLE DE CE FICHIER :
# Terminal interactif persistant Windows (PowerShell / CMD) avec support ConPTY
# (via pywinpty si disponible) et flux asynchrones temps réel non-bloquants.
# Permet à l'agent de :
#   - démarrer un shell ou un serveur persistant (ex: npm run dev) sans bloquer ;
#   - envoyer des commandes ou répondre à des prompts interactifs via stdin ;
#   - récupérer stdout et stderr en temps réel ;
#   - détecter les demandes de confirmation interactives.

from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from tools.process_utils import safe_subprocess_environment

_INTERACTIVE_PROMPT_REGEX = re.compile(
    r"(\[y/n\]|\[o/n\]|\(y/n\)|continue\?|confirm|password:|mot de passe|overwrite\?|proceed\?|"
    r"PS [A-Za-z]:[^>]*>\s*$|^[A-Za-z]:\\[^>]*>\s*$)",
    re.I | re.M,
)


class PersistentTerminalSession:
    """Session de terminal Windows vivante avec lecture asynchrone stdout/stderr."""

    def __init__(
        self,
        session_id: str = "default",
        shell: str = "powershell",
        cwd: str | Path | None = None,
    ) -> None:
        self.session_id = session_id
        self.shell = shell.strip().lower()
        self.cwd = str(Path(cwd).resolve()) if cwd else os.getcwd()
        self._lock = threading.Lock()
        self._stdout_queue: queue.Queue[str] = queue.Queue()
        self._stderr_queue: queue.Queue[str] = queue.Queue()
        self._stdout_history: list[str] = []
        self._stderr_history: list[str] = []
        self._conpty: Any = None
        self._process: subprocess.Popen[str] | None = None
        self.backend: str = "subprocess_pipe"
        self.started_at: float = time.time()
        self._start_process()

    def _build_shell_command(self) -> list[str]:
        if os.name == "nt":
            if self.shell in {"cmd", "cmd.exe"}:
                return ["cmd.exe", "/Q", "/K"]
            return [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NoExit",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "-",
            ]
        return ["/bin/sh"]

    def _start_process(self) -> None:
        cmd = self._build_shell_command()
        env = safe_subprocess_environment()
        # Tentative ConPTY native si pywinpty est installé et activé explicitement
        if os.name == "nt" and os.environ.get("NEOHARNESS_USE_WINPTY") == "1":
            try:
                from winpty import PtyProcess  # type: ignore[import-not-found]

                self._conpty = PtyProcess.spawn(" ".join(cmd), cwd=self.cwd, env=env)
                self.backend = "conpty"
                threading.Thread(target=self._read_conpty_loop, daemon=True).start()
                return
            except Exception:
                self._conpty = None

        self._process = subprocess.Popen(
            cmd,
            cwd=self.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
        )
        self.backend = "win32_async_pipe"
        if self._process.stdout is not None:
            threading.Thread(
                target=self._read_stream_loop,
                args=(self._process.stdout, self._stdout_queue, self._stdout_history),
                daemon=True,
            ).start()
        if self._process.stderr is not None:
            threading.Thread(
                target=self._read_stream_loop,
                args=(self._process.stderr, self._stderr_queue, self._stderr_history),
                daemon=True,
            ).start()

    def _read_conpty_loop(self) -> None:
        while self._conpty is not None and self._conpty.isalive():
            try:
                chunk = self._conpty.read(1024)
                if chunk:
                    for line in chunk.splitlines():
                        self._stdout_queue.put(line)
                        with self._lock:
                            self._stdout_history.append(line)
            except Exception:
                break

    def _read_stream_loop(
        self,
        stream: Any,
        q: queue.Queue[str],
        history: list[str],
    ) -> None:
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                clean = line.rstrip("\r\n")
                q.put(clean)
                with self._lock:
                    history.append(clean)
                    if len(history) > 1000:
                        del history[: len(history) - 1000]
        except Exception:
            pass

    @property
    def is_alive(self) -> bool:
        if self._conpty is not None:
            return bool(self._conpty.isalive())
        return self._process is not None and self._process.poll() is None

    @property
    def pid(self) -> int | None:
        if self._conpty is not None:
            return getattr(self._conpty, "pid", None)
        return self._process.pid if self._process is not None else None

    _DONE_MARKER = "__NEOHARNESS_CMD_DONE__"

    def send(
        self,
        command: str,
        *,
        wait_ms: int = 1500,
        add_newline: bool = True,
    ) -> dict[str, Any]:
        if not self.is_alive:
            return {
                "status": "error",
                "session_id": self.session_id,
                "alive": False,
                "error_code": "terminal_session_dead",
                "error": f"La session terminal '{self.session_id}' est terminée.",
            }

        cmd_clean = command.rstrip("\r\n")
        is_bg_server = any(
            k in cmd_clean.lower()
            for k in ("npm run dev", "npm start", "yarn dev", "pnpm dev", "http.server", "--ui")
        )
        if self.shell not in {"cmd", "cmd.exe"} and add_newline and not is_bg_server:
            payload = f"{cmd_clean}; Write-Output '{self._DONE_MARKER}'\n"
            expect_marker = True
        else:
            payload = cmd_clean + ("\n" if add_newline else "")
            expect_marker = False

        try:
            if self._conpty is not None:
                self._conpty.write(payload)
            elif self._process is not None and self._process.stdin is not None:
                self._process.stdin.write(payload)
                self._process.stdin.flush()
        except Exception as err:
            return {
                "status": "error",
                "session_id": self.session_id,
                "alive": self.is_alive,
                "error": f"Erreur d'écriture stdin : {err}",
            }

        return self.read(wait_ms=wait_ms, stop_on_marker=expect_marker)

    def read(self, *, wait_ms: int = 300, stop_on_marker: bool = False) -> dict[str, Any]:
        deadline = time.monotonic() + max(0.05, min(float(wait_ms) / 1000.0, 20.0))
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        marker_seen = False

        while time.monotonic() < deadline:
            drained = False
            while True:
                try:
                    line = self._stdout_queue.get_nowait()
                    if self._DONE_MARKER in line:
                        cleaned = line.replace(self._DONE_MARKER, "").strip()
                        if cleaned:
                            stdout_lines.append(cleaned)
                        marker_seen = True
                    else:
                        stdout_lines.append(line)
                    drained = True
                except queue.Empty:
                    break
            while True:
                try:
                    stderr_lines.append(self._stderr_queue.get_nowait())
                    drained = True
                except queue.Empty:
                    break
            if stop_on_marker and marker_seen:
                # Laisser 30ms pour drainer les dernières lignes stderr (ex: unittest écrit sur stderr)
                time.sleep(0.03)
                while True:
                    try:
                        stderr_lines.append(self._stderr_queue.get_nowait())
                    except queue.Empty:
                        break
                break
            if drained:
                time.sleep(0.02)
            else:
                time.sleep(0.02)

        stdout_text = "\n".join(stdout_lines)
        stderr_text = "\n".join(stderr_lines)
        combined = "\n".join(part for part in (stdout_text, stderr_text) if part)
        prompt_match = _INTERACTIVE_PROMPT_REGEX.search(combined)

        return {
            "status": "success",
            "session_id": self.session_id,
            "pid": self.pid,
            "backend": self.backend,
            "alive": self.is_alive,
            "stdout": stdout_text[-8000:],
            "stderr": stderr_text[-8000:],
            "output": combined[-8000:],
            "completed": marker_seen,
            "prompt_detected": bool(prompt_match),
            "detected_prompt": prompt_match.group(0).strip() if prompt_match else "",
        }

    def stop(self) -> dict[str, Any]:
        if self._conpty is not None:
            try:
                self._conpty.close(force=True)
            except Exception:
                pass
            self._conpty = None
        if self._process is not None:
            if self._process.poll() is None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=3)
                except Exception:
                    try:
                        self._process.kill()
                        self._process.wait(timeout=2)
                    except Exception:
                        pass
            for pipe in (self._process.stdin, self._process.stdout, self._process.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception:
                        pass
        return {
            "status": "success",
            "session_id": self.session_id,
            "alive": self.is_alive,
            "stopped": not self.is_alive,
        }


class PersistentTerminalManager:
    """Gestionnaire global des sessions de terminal interactives persistantes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, PersistentTerminalSession] = {}

    def start_session(
        self,
        session_id: str = "default",
        shell: str = "powershell",
        cwd: str | Path | None = None,
    ) -> dict[str, Any]:
        sid = (session_id or "default").strip()
        with self._lock:
            existing = self._sessions.get(sid)
            if existing is not None and existing.is_alive:
                return {
                    "status": "success",
                    "session_id": sid,
                    "pid": existing.pid,
                    "shell": existing.shell,
                    "cwd": existing.cwd,
                    "backend": existing.backend,
                    "alive": True,
                    "reused": True,
                }
            session = PersistentTerminalSession(session_id=sid, shell=shell, cwd=cwd)
            self._sessions[sid] = session

        initial = session.read(wait_ms=150)
        return {
            "status": "success",
            "session_id": sid,
            "pid": session.pid,
            "shell": session.shell,
            "cwd": session.cwd,
            "backend": session.backend,
            "alive": session.is_alive,
            "reused": False,
            "initial_stdout": initial.get("stdout", ""),
        }

    def send_input(
        self,
        command: str,
        session_id: str = "default",
        wait_ms: int = 600,
        cwd: str | Path | None = None,
    ) -> dict[str, Any]:
        sid = (session_id or "default").strip()
        with self._lock:
            session = self._sessions.get(sid)
            if session is None or not session.is_alive:
                session = PersistentTerminalSession(session_id=sid, shell="powershell", cwd=cwd)
                self._sessions[sid] = session
        return session.send(command, wait_ms=wait_ms)

    def read_output(self, session_id: str = "default", wait_ms: int = 300) -> dict[str, Any]:
        sid = (session_id or "default").strip()
        with self._lock:
            session = self._sessions.get(sid)
        if session is None:
            return {
                "status": "error",
                "session_id": sid,
                "error_code": "session_not_found",
                "error": f"Aucune session terminal active nommée '{sid}'.",
            }
        return session.read(wait_ms=wait_ms)

    def stop_session(self, session_id: str = "default") -> dict[str, Any]:
        sid = (session_id or "default").strip()
        with self._lock:
            session = self._sessions.pop(sid, None)
        if session is None:
            return {"status": "success", "session_id": sid, "stopped": True}
        return session.stop()

    def list_sessions(self) -> dict[str, Any]:
        with self._lock:
            items = [
                {
                    "session_id": s.session_id,
                    "pid": s.pid,
                    "shell": s.shell,
                    "cwd": s.cwd,
                    "backend": s.backend,
                    "alive": s.is_alive,
                }
                for s in self._sessions.values()
            ]
        return {"status": "success", "count": len(items), "sessions": items}


_GLOBAL_TERMINAL_MANAGER = PersistentTerminalManager()


def get_terminal_manager() -> PersistentTerminalManager:
    return _GLOBAL_TERMINAL_MANAGER