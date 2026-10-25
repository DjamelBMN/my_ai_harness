# RÔLE DE CE FICHIER :
# Runtime Python headless partagé par l'Artifact Engine (core/artifacts/handlers.py) et
# l'outil agent run_python (tools/terminal.py).
#   - prépare l'environnement du sous-processus : MPLBACKEND=Agg, cache Matplotlib
#     persistant (les polices ne sont indexées qu'une seule fois), PYTHONPATH incluant
#     tools/python_sandbox/ dont le sitecustomize capture les figures ;
#   - nettoie les figures obsolètes du dossier output/ avant chaque exécution ;
#   - relit le manifeste des figures réellement produites ;
#   - valide chaque PNG octet par octet (signature, chunks, CRC, IHDR, IDAT, IEND).

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import threading
import zlib
from pathlib import Path
from typing import Any

from tools.process_utils import safe_subprocess_environment

SANDBOX_DIR = Path(__file__).resolve().parent / "python_sandbox"
OUTPUT_DIRNAME = "output"
_FIGURE_NAME = re.compile(r"^figure_\d+\.png$")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def mpl_config_dir() -> Path:
    """Cache Matplotlib persistant, hors workspace (n'apparaît jamais comme sortie)."""
    path = Path(tempfile.gettempdir()) / "neoharness_mplconfig"
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_dir_for(script_abs: Path) -> Path:
    return Path(script_abs).resolve().parent / OUTPUT_DIRNAME


def prepare_output_dir(output_dir: Path) -> None:
    """Supprime uniquement les figures auto-capturées d'une exécution précédente."""
    if output_dir.is_dir():
        for child in output_dir.iterdir():
            if child.is_file() and _FIGURE_NAME.match(child.name):
                try:
                    child.unlink()
                except OSError:
                    pass


def new_manifest_path() -> Path:
    handle, name = tempfile.mkstemp(prefix="neoharness_fig_", suffix=".json")
    os.close(handle)
    Path(name).unlink(missing_ok=True)
    return Path(name)


def build_python_env(
    *,
    output_dir: Path,
    manifest_path: Path,
    extra_paths: list[str | Path] | None = None,
) -> dict[str, str]:
    env = safe_subprocess_environment()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["MPLBACKEND"] = "Agg"
    env["MPLCONFIGDIR"] = str(mpl_config_dir())
    env["NEOHARNESS_OUTPUT_DIR"] = str(output_dir)
    env["NEOHARNESS_FIGURE_MANIFEST"] = str(manifest_path)
    paths = [str(SANDBOX_DIR)] + [str(p) for p in (extra_paths or [])]
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def read_figure_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception:
        data = {"matplotlib_used": False, "figures": [], "errors": [], "manifest_missing": True}
    finally:
        try:
            Path(manifest_path).unlink(missing_ok=True)
        except OSError:
            pass
    return data


def validate_png(path: str | Path) -> dict[str, Any]:
    """Validation structurelle réelle d'un PNG : signature, CRC de chaque chunk, IHDR/IDAT/IEND."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        return {"valid": False, "path": str(p), "error": f"Lecture impossible : {exc}"}
    if not raw.startswith(_PNG_SIGNATURE):
        return {"valid": False, "path": str(p), "error": "Signature PNG absente."}
    offset, width, height, idat_bytes, seen = 8, 0, 0, 0, []
    while offset + 8 <= len(raw):
        length, ctype = struct.unpack(">I4s", raw[offset:offset + 8])
        data = raw[offset + 8:offset + 8 + length]
        crc_bytes = raw[offset + 8 + length:offset + 12 + length]
        if len(data) != length or len(crc_bytes) != 4:
            return {"valid": False, "path": str(p), "error": f"Chunk {ctype!r} tronqué."}
        if zlib.crc32(ctype + data) & 0xFFFFFFFF != struct.unpack(">I", crc_bytes)[0]:
            return {"valid": False, "path": str(p), "error": f"CRC invalide sur le chunk {ctype!r}."}
        seen.append(ctype)
        if ctype == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif ctype == b"IDAT":
            idat_bytes += length
        elif ctype == b"IEND":
            break
        offset += 12 + length
    if not seen or seen[0] != b"IHDR":
        return {"valid": False, "path": str(p), "error": "Chunk IHDR manquant en tête."}
    if b"IEND" not in seen:
        return {"valid": False, "path": str(p), "error": "Chunk IEND manquant (fichier incomplet)."}
    if idat_bytes == 0:
        return {"valid": False, "path": str(p), "error": "Aucune donnée image (IDAT)."}
    if width <= 0 or height <= 0:
        return {"valid": False, "path": str(p), "error": "Dimensions nulles."}
    return {
        "valid": True,
        "path": str(p),
        "width": width,
        "height": height,
        "size_bytes": len(raw),
    }


_warm_lock = threading.Lock()
_warm_started = False


def warm_matplotlib_cache_async() -> None:
    """Indexe une fois les polices Matplotlib en arrière-plan (évite le coût au 1er graphique)."""
    global _warm_started
    with _warm_lock:
        if _warm_started:
            return
        _warm_started = True

    def _run() -> None:
        env = safe_subprocess_environment()
        env["MPLBACKEND"] = "Agg"
        env["MPLCONFIGDIR"] = str(mpl_config_dir())
        try:
            subprocess.run(
                [sys.executable, "-B", "-c", "import matplotlib.pyplot as plt; plt.figure(); plt.close('all')"],
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=180,
                check=False,
            )
        except Exception:
            pass

    threading.Thread(target=_run, name="neoharness-mpl-warmup", daemon=True).start()

