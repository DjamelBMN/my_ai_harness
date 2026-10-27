# RÔLE DE CE FICHIER :
# Gestion et inspection des fenêtres graphiques Windows via l'API Win32 native
# (ctypes.windll.user32) : lister les fenêtres, identifier la fenêtre active,
# chercher par titre, activer/focus, minimiser, maximiser, restaurer, fermer
# et récupérer la position/taille.

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import time
from typing import Any

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
SW_SHOW = 5
WM_CLOSE = 0x0010


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _is_win32_available() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def _get_window_info(hwnd: int, active_hwnd: int = 0) -> dict[str, Any] | None:
    if not _is_win32_available() or not hwnd:
        return None
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value.strip()

    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    rect = _RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = max(0, rect.right - rect.left)
    height = max(0, rect.bottom - rect.top)

    is_visible = bool(user32.IsWindowVisible(hwnd))
    is_minimized = bool(user32.IsIconic(hwnd))
    is_maximized = bool(user32.IsZoomed(hwnd))
    fg_hwnd = active_hwnd or user32.GetForegroundWindow()

    return {
        "hwnd": int(hwnd),
        "title": title,
        "pid": int(pid.value),
        "visible": is_visible,
        "is_active": int(hwnd) == int(fg_hwnd),
        "is_minimized": is_minimized,
        "is_maximized": is_maximized,
        "rect": {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
            "width": int(width),
            "height": int(height),
        },
    }


def window_list(visible_only: bool = True, filter_title: str = "") -> dict[str, Any]:
    """Liste toutes les fenêtres Windows ouvertes avec leur titre, HWND, PID et position."""
    if not _is_win32_available():
        return {"status": "success", "count": 0, "windows": [], "backend": "unavailable"}

    user32 = ctypes.windll.user32
    fg_hwnd = int(user32.GetForegroundWindow() or 0)
    needle = (filter_title or "").strip().casefold()
    results: list[dict[str, Any]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd: int, _lparam: int) -> bool:
        if visible_only and not user32.IsWindowVisible(hwnd):
            return True
        info = _get_window_info(hwnd, active_hwnd=fg_hwnd)
        if not info or not info["title"]:
            return True
        if needle and needle not in info["title"].casefold():
            return True
        results.append(info)
        return True

    enum_proc = WNDENUMPROC(_callback)
    user32.EnumWindows(enum_proc, 0)
    return {
        "status": "success",
        "count": len(results),
        "active_hwnd": fg_hwnd,
        "windows": results,
    }


def window_active() -> dict[str, Any]:
    """Identifie et retourne la fenêtre actuellement au premier plan sur Windows."""
    if not _is_win32_available():
        return {"status": "success", "window": None, "backend": "unavailable"}

    user32 = ctypes.windll.user32
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return {"status": "success", "window": None}
    info = _get_window_info(hwnd, active_hwnd=hwnd)
    return {
        "status": "success",
        "window": info,
    }


def window_find(query: str) -> dict[str, Any]:
    """Recherche une ou plusieurs fenêtres par sous-chaîne de titre."""
    clean_q = (query or "").strip()
    if not clean_q:
        raise ValueError("Le paramètre 'query' ne peut pas être vide.")
    listed = window_list(visible_only=True, filter_title=clean_q)
    matches = listed.get("windows", [])
    return {
        "status": "success",
        "found": bool(matches),
        "count": len(matches),
        "query": clean_q,
        "windows": matches,
    }


def _resolve_target_hwnd(title: str = "", hwnd: int = 0) -> dict[str, Any] | None:
    if hwnd and _is_win32_available():
        info = _get_window_info(int(hwnd))
        if info and info["title"]:
            return info
    if title:
        found = window_find(title)
        windows = found.get("windows", [])
        if windows:
            return windows[0]
    return None


def window_focus(title: str = "", hwnd: int = 0) -> dict[str, Any]:
    """Active et amène au premier plan une fenêtre Windows identifiée par son titre ou HWND."""
    target = _resolve_target_hwnd(title=title, hwnd=hwnd)
    if target is None:
        return {
            "status": "error",
            "verified": False,
            "error_code": "window_not_found",
            "error": f"Fenêtre introuvable (title={title!r}, hwnd={hwnd}).",
        }
    target_hwnd = int(target["hwnd"])
    user32 = ctypes.windll.user32
    if user32.IsIconic(target_hwnd):
        user32.ShowWindow(target_hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(target_hwnd, SW_SHOW)
    user32.SetForegroundWindow(target_hwnd)
    time.sleep(0.15)
    after = _get_window_info(target_hwnd)
    is_active = bool(after and after.get("is_active"))
    return {
        "status": "success" if is_active else "warning",
        "verified": is_active,
        "window": after or target,
    }


def _change_window_state(action: str, sw_cmd: int, title: str = "", hwnd: int = 0) -> dict[str, Any]:
    target = _resolve_target_hwnd(title=title, hwnd=hwnd)
    if target is None:
        return {
            "status": "error",
            "verified": False,
            "error_code": "window_not_found",
            "error": f"Fenêtre introuvable pour '{action}' (title={title!r}, hwnd={hwnd}).",
        }
    target_hwnd = int(target["hwnd"])
    user32 = ctypes.windll.user32
    user32.ShowWindow(target_hwnd, sw_cmd)
    time.sleep(0.1)
    after = _get_window_info(target_hwnd)
    return {
        "status": "success",
        "verified": True,
        "action": action,
        "window": after or target,
    }


def window_minimize(title: str = "", hwnd: int = 0) -> dict[str, Any]:
    """Minimise une fenêtre Windows."""
    return _change_window_state("minimize", SW_MINIMIZE, title=title, hwnd=hwnd)


def window_maximize(title: str = "", hwnd: int = 0) -> dict[str, Any]:
    """Maximise une fenêtre Windows."""
    return _change_window_state("maximize", SW_MAXIMIZE, title=title, hwnd=hwnd)


def window_restore(title: str = "", hwnd: int = 0) -> dict[str, Any]:
    """Restaure une fenêtre Windows minimisée ou maximisée."""
    return _change_window_state("restore", SW_RESTORE, title=title, hwnd=hwnd)


def window_close(title: str = "", hwnd: int = 0) -> dict[str, Any]:
    """Demande la fermeture propre (WM_CLOSE) d'une fenêtre Windows."""
    target = _resolve_target_hwnd(title=title, hwnd=hwnd)
    if target is None:
        return {
            "status": "error",
            "verified": False,
            "error_code": "window_not_found",
            "error": f"Fenêtre introuvable pour fermeture (title={title!r}, hwnd={hwnd}).",
        }
    target_hwnd = int(target["hwnd"])
    user32 = ctypes.windll.user32
    user32.PostMessageW(target_hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.2)
    still_exists = bool(user32.IsWindow(target_hwnd))
    return {
        "status": "success",
        "verified": not still_exists,
        "hwnd": target_hwnd,
        "title": target["title"],
        "closed": not still_exists,
    }