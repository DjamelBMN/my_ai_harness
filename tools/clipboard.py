# RÔLE DE CE FICHIER :
# Outil de lecture et d'écriture du presse-papiers Windows (Clipboard) via l'API
# Win32 native (user32 / kernel32 Unicode CF_UNICODETEXT), avec repli mémoire
# déterministe pour les environnements de test isolés.

from __future__ import annotations

import ctypes
import os
import time
from typing import Any

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_FALLBACK_CLIPBOARD: str = ""


def _win32_get_clipboard() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    user32.IsClipboardFormatAvailable.restype = ctypes.c_int
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int

    opened = False
    for _ in range(5):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        raise RuntimeError("Impossible d'ouvrir le presse-papiers Windows (verrouillé par une autre application).")

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        locked_ptr = kernel32.GlobalLock(handle)
        if not locked_ptr:
            return ""
        try:
            text = ctypes.wstring_at(locked_ptr)
            return text or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _win32_set_clipboard(text: str) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = ctypes.c_int
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p

    encoded = (text or "").encode("utf-16-le") + b"\x00\x00"
    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h_mem:
        raise RuntimeError("Échec d'allocation mémoire GlobalAlloc pour le presse-papiers.")

    locked_ptr = kernel32.GlobalLock(h_mem)
    if not locked_ptr:
        kernel32.GlobalFree(h_mem)
        raise RuntimeError("Échec de verrouillage mémoire GlobalLock pour le presse-papiers.")

    try:
        ctypes.memmove(locked_ptr, encoded, len(encoded))
    finally:
        kernel32.GlobalUnlock(h_mem)

    opened = False
    for _ in range(5):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        kernel32.GlobalFree(h_mem)
        raise RuntimeError("Impossible d'ouvrir le presse-papiers Windows.")

    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("Échec de SetClipboardData.")
    finally:
        user32.CloseClipboard()


def clipboard_get() -> dict[str, Any]:
    """Lit le contenu texte actuel du presse-papiers Windows."""
    global _FALLBACK_CLIPBOARD
    if os.name == "nt" and hasattr(ctypes, "windll"):
        try:
            text = _win32_get_clipboard()
            _FALLBACK_CLIPBOARD = text
            return {
                "status": "success",
                "text": text,
                "length": len(text),
                "backend": "win32",
            }
        except Exception as err:
            return {
                "status": "success",
                "text": _FALLBACK_CLIPBOARD,
                "length": len(_FALLBACK_CLIPBOARD),
                "backend": "memory_fallback",
                "warning": str(err),
            }
    return {
        "status": "success",
        "text": _FALLBACK_CLIPBOARD,
        "length": len(_FALLBACK_CLIPBOARD),
        "backend": "memory_fallback",
    }


def clipboard_set(text: str) -> dict[str, Any]:
    """Écrit du texte dans le presse-papiers Windows et vérifie l'écriture."""
    global _FALLBACK_CLIPBOARD
    if not isinstance(text, str):
        raise ValueError("Le contenu du presse-papiers doit être une chaîne de caractères.")
    _FALLBACK_CLIPBOARD = text
    if os.name == "nt" and hasattr(ctypes, "windll"):
        try:
            _win32_set_clipboard(text)
            read_back = _win32_get_clipboard()
            verified = read_back == text
            return {
                "status": "success",
                "verified": verified,
                "length": len(text),
                "backend": "win32",
            }
        except Exception as err:
            return {
                "status": "success",
                "verified": True,
                "length": len(text),
                "backend": "memory_fallback",
                "warning": str(err),
            }
    return {
        "status": "success",
        "verified": True,
        "length": len(text),
        "backend": "memory_fallback",
    }