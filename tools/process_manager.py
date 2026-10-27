# RÔLE DE CE FICHIER :
# Gestionnaire de processus Windows pour NeoHarness AI.
# Permet de lister les processus actifs, démarrer une application ou un processus
# sans bloquer, vérifier qu'il ne s'est pas terminé prématurément, surveiller son
# état, récupérer sa sortie et l'arrêter de manière contrôlée.

from __future__ import annotations

import csv
import io
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.process_utils import safe_subprocess_environment


@dataclass
class ManagedProcessRecord:
    pid: int
    executable: str
    arguments: list[str]
    cwd: str
    started_at: float
    process: subprocess.Popen[str]
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)


class ProcessManager:
    """Registre et contrôleur des processus Windows lancés ou inspectés par l'agent."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._managed: dict[int, ManagedProcessRecord] = {}

    @staticmethod
    def _drain_stream(stream: Any, target: list[str], lock: threading.Lock) -> None:
        try:
            for line in iter(stream.readline, ""):
                if not line:
                    break
                with lock:
                    target.append(line.rstrip("\r\n"))
                    if len(target) > 500:
                        del target[: len(target) - 500]
        except Exception:
            pass

    def list_processes(self, filter_name: str = "", limit: int = 50) -> dict[str, Any]:
        """Liste les processus actifs sur Windows via tasklist."""
        needle = (filter_name or "").strip().casefold()
        max_items = max(1, min(int(limit or 50), 250))
        processes: list[dict[str, Any]] = []

        if os.name == "nt":
            try:
                res = subprocess.run(
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=10,
                    shell=False,
                    check=False,
                )
                reader = csv.reader(io.StringIO(res.stdout or ""))
                for row in reader:
                    if len(row) < 5:
                        continue
                    name, pid_str, session_name, _session_num, mem_str = row[:5]
                    if needle and needle not in name.casefold() and needle != pid_str.strip():
                        continue
                    try:
                        pid_val = int(pid_str.strip())
                    except ValueError:
                        continue
                    processes.append(
                        {
                            "pid": pid_val,
                            "name": name.strip(),
                            "session": session_name.strip(),
                            "memory": mem_str.strip(),
                            "managed_by_neoharness": pid_val in self._managed,
                        }
                    )
                    if len(processes) >= max_items:
                        break
            except Exception as err:
                return {
                    "status": "error",
                    "error": f"Impossible de lister les processus Windows : {err}",
                    "processes": [],
                }

        return {
            "status": "success",
            "count": len(processes),
            "filter": filter_name,
            "processes": processes,
        }

    def start_process(
        self,
        executable: str,
        arguments: list[str] | None = None,
        cwd: str | Path | None = None,
        startup_check_ms: int = 250,
    ) -> dict[str, Any]:
        """Démarre un processus Windows en arrière-plan et vérifie qu'il reste vivant."""
        exe_clean = (executable or "").strip()
        if not exe_clean:
            raise ValueError("Le nom de l'exécutable ou de l'application est requis.")

        args = [str(a) for a in (arguments or [])]
        resolved_exe = shutil.which(exe_clean) or exe_clean
        work_dir = str(Path(cwd).resolve()) if cwd else os.getcwd()

        try:
            proc = subprocess.Popen(
                [resolved_exe, *args],
                cwd=work_dir,
                env=safe_subprocess_environment(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
        except FileNotFoundError:
            return {
                "status": "error",
                "verified": False,
                "error_code": "application_not_found",
                "error": f"Application ou exécutable introuvable : '{exe_clean}'.",
            }
        except Exception as err:
            return {
                "status": "error",
                "verified": False,
                "error_code": "application_start_failed",
                "error": f"Impossible de démarrer '{exe_clean}' : {err}",
            }

        record = ManagedProcessRecord(
            pid=proc.pid,
            executable=exe_clean,
            arguments=args,
            cwd=work_dir,
            started_at=time.time(),
            process=proc,
        )
        with self._lock:
            self._managed[proc.pid] = record

        if proc.stdout is not None:
            threading.Thread(
                target=self._drain_stream,
                args=(proc.stdout, record.stdout_lines, self._lock),
                daemon=True,
            ).start()
        if proc.stderr is not None:
            threading.Thread(
                target=self._drain_stream,
                args=(proc.stderr, record.stderr_lines, self._lock),
                daemon=True,
            ).start()

        wait_s = max(0.05, min(float(startup_check_ms) / 1000.0, 3.0))
        time.sleep(wait_s)
        exit_code = proc.poll()

        with self._lock:
            stdout_preview = "\n".join(record.stdout_lines[-20:])
            stderr_preview = "\n".join(record.stderr_lines[-20:])

        # Certains lanceurs Windows (ex: code.cmd) rendent la main avec code 0 après avoir ouvert la fenêtre
        premature_failure = exit_code is not None and exit_code != 0
        return {
            "status": "error" if premature_failure else "success",
            "verified": not premature_failure,
            "pid": proc.pid,
            "executable": exe_clean,
            "arguments": args,
            "alive": exit_code is None,
            "exit_code": exit_code,
            "stdout": stdout_preview,
            "stderr": stderr_preview,
            "error_code": "process_exited_prematurely" if premature_failure else "",
        }

    def get_process_status(self, pid: int) -> dict[str, Any]:
        """Surveille l'état et la sortie d'un processus par son PID."""
        pid_val = int(pid)
        with self._lock:
            managed = self._managed.get(pid_val)

        if managed is not None:
            exit_code = managed.process.poll()
            with self._lock:
                stdout_text = "\n".join(managed.stdout_lines[-50:])
                stderr_text = "\n".join(managed.stderr_lines[-50:])
            return {
                "status": "success",
                "pid": pid_val,
                "executable": managed.executable,
                "managed_by_neoharness": True,
                "alive": exit_code is None,
                "exit_code": exit_code,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }

        listing = self.list_processes(filter_name=str(pid_val), limit=5)
        matches = [p for p in listing.get("processes", []) if p.get("pid") == pid_val]
        if matches:
            return {
                "status": "success",
                "pid": pid_val,
                "name": matches[0].get("name", ""),
                "memory": matches[0].get("memory", ""),
                "managed_by_neoharness": False,
                "alive": True,
                "exit_code": None,
            }
        return {
            "status": "success",
            "pid": pid_val,
            "managed_by_neoharness": False,
            "alive": False,
            "exit_code": None,
        }

    def stop_process(self, pid: int, force: bool = False) -> dict[str, Any]:
        """Arrête un processus Windows par son PID."""
        pid_val = int(pid)
        with self._lock:
            managed = self._managed.get(pid_val)

        if managed is not None:
            proc = managed.process
            if proc.poll() is None:
                try:
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                        proc.wait(timeout=2)
                    except Exception:
                        pass
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception:
                        pass
            exit_code = proc.poll()
            return {
                "status": "success",
                "verified": exit_code is not None,
                "pid": pid_val,
                "stopped": exit_code is not None,
                "exit_code": exit_code,
            }

        if os.name == "nt":
            cmd = ["taskkill", "/PID", str(pid_val), "/T"]
            if force:
                cmd.append("/F")
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                shell=False,
                check=False,
            )
            ok = res.returncode == 0
            return {
                "status": "success" if ok else "error",
                "verified": ok,
                "pid": pid_val,
                "stopped": ok,
                "output": (res.stdout or res.stderr or "").strip(),
            }

        return {
            "status": "error",
            "verified": False,
            "pid": pid_val,
            "error": f"Processus {pid_val} introuvable.",
        }


_GLOBAL_PROCESS_MANAGER = ProcessManager()


def process_list(filter_name: str = "", limit: int = 50) -> dict[str, Any]:
    return _GLOBAL_PROCESS_MANAGER.list_processes(filter_name=filter_name, limit=limit)


def process_start(
    executable: str,
    arguments: list[str] | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    return _GLOBAL_PROCESS_MANAGER.start_process(executable, arguments=arguments, cwd=cwd)


def process_status(pid: int) -> dict[str, Any]:
    return _GLOBAL_PROCESS_MANAGER.get_process_status(pid)


def process_stop(pid: int, force: bool = False) -> dict[str, Any]:
    return _GLOBAL_PROCESS_MANAGER.stop_process(pid, force=force)