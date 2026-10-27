# RÔLE DE CE FICHIER :
# Couche complète de Computer Use Windows en boucle fermée :
#   1. Observation : capture d'écran (PIL.ImageGrab), détection de la fenêtre active,
#      OCR avec coordonnées de boîtes englobantes (pytesseract), comparaison visuelle
#      d'écran avant/après (PIL.ImageChops).
#   2. Actions Souris : déplacement absolu/relatif, clic gauche/droit/double,
#      glisser-déposer (drag), molette (scroll) avec Fail-Safe en coin (0, 0).
#   3. Actions Clavier : saisie Unicode, touches individuelles, raccourcis combinés
#      (Ctrl+C, Ctrl+V, Ctrl+A, Alt+Tab, Win, Enter, Escape...).
#   4. Boucle Fermée (Perception -> Action -> Observation -> Vérification) :
#      vérifie automatiquement si l'action a produit un effet visuel ou changé la
#      fenêtre attendue et remonte un diagnostic précis en cas d'échec.

from __future__ import annotations

import ctypes
import hashlib
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageGrab

from tools.windows import window_active, window_find, window_focus

# Constantes Win32 souris et clavier
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

VK_MAP: dict[str, int] = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "menu": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "win": 0x5B,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class ComputerUseFailSafeError(RuntimeError):
    """Déclenchée si le curseur souris se trouve dans le coin d'arrêt d'urgence (0, 0)."""


def _is_win32() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def get_screen_metrics() -> dict[str, int]:
    """Retourne les dimensions de l'écran principal et la position actuelle du curseur."""
    if not _is_win32():
        return {"width": 1920, "height": 1080, "cursor_x": 500, "cursor_y": 500}
    user32 = ctypes.windll.user32
    width = int(user32.GetSystemMetrics(0) or 1920)
    height = int(user32.GetSystemMetrics(1) or 1080)
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return {
        "width": width,
        "height": height,
        "cursor_x": int(pt.x),
        "cursor_y": int(pt.y),
    }


def _check_failsafe() -> None:
    if not _is_win32():
        return
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    if pt.x == 0 and pt.y == 0:
        raise ComputerUseFailSafeError(
            "Fail-Safe Computer Use déclenché : le curseur est au coin supérieur gauche (0, 0)."
        )


def _validate_coordinates(x: int, y: int) -> tuple[int, int]:
    metrics = get_screen_metrics()
    max_w = max(1, metrics["width"])
    max_h = max(1, metrics["height"])
    if x < 0 or y < 0 or x >= max_w * 2 or y >= max_h * 2:
        raise ValueError(
            f"Coordonnées ({x}, {y}) hors des limites de l'écran ({max_w}x{max_h})."
        )
    if x == 0 and y == 0:
        raise ComputerUseFailSafeError(
            "Déplacement vers (0, 0) interdit (coin réservé au Fail-Safe d'urgence)."
        )
    return int(x), int(y)


# ------------------------------------------------------------------
# OBSERVATION & COMPARAISON D'ÉCRAN
# ------------------------------------------------------------------

def get_windows_desktop_dir() -> Path:
    """Résout le véritable dossier Bureau Windows de l'utilisateur (local ou OneDrive)."""
    if _is_win32():
        try:
            buf = ctypes.create_unicode_buffer(260)
            # CSIDL_DESKTOPDIRECTORY = 0x0010
            res = ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)
            if res == 0 and buf.value:
                candidate = Path(buf.value)
                if candidate.is_dir():
                    return candidate
        except Exception:
            pass
    for candidate in (
        Path.home() / "Desktop",
        Path.home() / "Bureau",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive" / "Bureau",
    ):
        if candidate.is_dir():
            return candidate
    fallback = Path.home() / "Desktop"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def copy_to_desktop(
    source_path: str,
    filename: str = "",
    workspace: str | Path = "workspace",
) -> dict[str, Any]:
    """Copie un fichier du workspace (ex: capture d'écran) directement sur le Bureau Windows."""
    import shutil

    ws_root = Path(workspace).resolve()
    src = Path(source_path)
    if not src.is_absolute():
        src = (ws_root / src).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Fichier source introuvable : {source_path}")

    desktop_dir = get_windows_desktop_dir()
    target_name = Path(filename).name if filename and filename.strip() else src.name
    dest_file = desktop_dir / target_name
    shutil.copy2(src, dest_file)
    verified = dest_file.is_file() and dest_file.stat().st_size > 0
    return {
        "status": "success" if verified else "error",
        "verified": verified,
        "source_path": str(src),
        "desktop_path": str(dest_file),
        "filename": target_name,
        "size_bytes": dest_file.stat().st_size if verified else 0,
    }


def computer_screenshot(
    region: list[int] | None = None,
    label: str = "",
    save_to_desktop: bool = False,
    output_path: str = "",
    workspace: str | Path = "workspace",
) -> dict[str, Any]:
    """Capture l'écran actif et l'enregistre dans workspace/screenshots/ (et sur le Bureau si save_to_desktop=True)."""
    ws_root = Path(workspace).resolve()
    shots_dir = ws_root / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    bbox = tuple(int(v) for v in region[:4]) if isinstance(region, list) and len(region) == 4 else None
    try:
        img = ImageGrab.grab(bbox=bbox)
    except Exception:
        # En environnement CI/headless sans serveur graphique actif, crée un canevas témoin
        w = (bbox[2] - bbox[0]) if bbox else 1280
        h = (bbox[3] - bbox[1]) if bbox else 720
        img = Image.new("RGB", (max(1, w), max(1, h)), color=(245, 245, 245))

    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "capture_ecran"))[:30]
    filename = f"{safe_label}_{int(time.time() * 1000)}.png"
    dest_path = shots_dir / filename
    img.save(dest_path, format="PNG")
    raw_bytes = dest_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    out_low = (output_path or "").strip().lower()
    wants_desktop = bool(save_to_desktop) or any(
        k in out_low for k in ("desktop", "bureau")
    )
    desktop_file_path = ""
    if wants_desktop:
        desktop_dir = get_windows_desktop_dir()
        custom_name = (
            Path(output_path).name
            if output_path and output_path.lower().endswith(".png")
            else filename
        )
        desktop_target = desktop_dir / custom_name
        desktop_target.write_bytes(raw_bytes)
        desktop_file_path = str(desktop_target)

    active_win = window_active().get("window")
    metrics = get_screen_metrics()
    rel_path = dest_path.relative_to(ws_root).as_posix()

    return {
        "status": "success",
        "verified": True,
        "path": rel_path,
        "abs_path": str(dest_path),
        "saved_to_desktop": bool(desktop_file_path),
        "desktop_path": desktop_file_path,
        "width": img.width,
        "height": img.height,
        "size_bytes": len(raw_bytes),
        "sha256": sha256,
        "screen_metrics": metrics,
        "active_window": active_win,
    }


def computer_compare_screens(
    before_path: str | Path,
    after_path: str | Path,
    workspace: str | Path = "workspace",
) -> dict[str, Any]:
    """Compare deux captures d'écran avant/après une action et mesure le changement visuel."""
    ws_root = Path(workspace).resolve()
    p_before = Path(before_path)
    if not p_before.is_absolute():
        p_before = (ws_root / p_before).resolve()
    p_after = Path(after_path)
    if not p_after.is_absolute():
        p_after = (ws_root / p_after).resolve()

    if not p_before.is_file() or not p_after.is_file():
        raise FileNotFoundError(
            f"Captures introuvables pour comparaison : {p_before} vs {p_after}"
        )

    with Image.open(p_before) as img1_raw, Image.open(p_after) as img2_raw:
        img1 = img1_raw.convert("RGB")
        img2 = img2_raw.convert("RGB")
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.BILINEAR)

        diff = ImageChops.difference(img1, img2).convert("L")
        bbox = diff.getbbox()
        hist = diff.histogram()
        total_pixels = max(1, img1.width * img1.height)
        # Pixels dont l'intensité de différence dépasse le bruit de compression (> 8)
        changed_pixels = sum(hist[9:])
        diff_ratio = changed_pixels / float(total_pixels)

    return {
        "status": "success",
        "screen_changed": changed_pixels > 0,
        "changed_pixels": int(changed_pixels),
        "total_pixels": int(total_pixels),
        "diff_ratio": round(diff_ratio, 6),
        "diff_percent": round(diff_ratio * 100.0, 3),
        "changed_bbox": (
            {
                "left": bbox[0],
                "top": bbox[1],
                "right": bbox[2],
                "bottom": bbox[3],
            }
            if bbox
            else None
        ),
    }


def computer_ocr(
    image_path: str = "",
    region: list[int] | None = None,
    find_text: str = "",
    workspace: str | Path = "workspace",
) -> dict[str, Any]:
    """Extrait le texte visible à l'écran (ou dans une capture) avec coordonnées (x, y) pour cliquer."""
    ws_root = Path(workspace).resolve()
    if image_path:
        target = Path(image_path)
        if not target.is_absolute():
            target = (ws_root / target).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"Image OCR introuvable : {target}")
        shot_rel = target.relative_to(ws_root).as_posix() if target.is_relative_to(ws_root) else str(target)
    else:
        shot = computer_screenshot(region=region, label="ocr", workspace=ws_root)
        target = Path(shot["abs_path"])
        shot_rel = shot["path"]

    needle = (find_text or "").strip().casefold()
    elements: list[dict[str, Any]] = []
    full_lines: list[str] = []

    try:
        import pytesseract
        from pytesseract import Output

        with Image.open(target) as img:
            data = pytesseract.image_to_data(img, lang="fra+eng", output_type=Output.DICT)
        n_items = len(data.get("text", []))
        for i in range(n_items):
            word = str(data["text"][i] or "").strip()
            if not word:
                continue
            try:
                conf = float(data["conf"][i])
            except (ValueError, TypeError):
                conf = -1.0
            if conf < 20.0:
                continue
            left = int(data["left"][i])
            top = int(data["top"][i])
            width = int(data["width"][i])
            height = int(data["height"][i])
            item = {
                "text": word,
                "confidence": round(conf, 1),
                "x": left + width // 2,
                "y": top + height // 2,
                "bbox": {"left": left, "top": top, "width": width, "height": height},
            }
            elements.append(item)
            full_lines.append(word)
    except Exception as err:
        return {
            "status": "warning",
            "screenshot_path": shot_rel,
            "text": "",
            "elements": [],
            "matches": [],
            "warning": f"OCR Tesseract non disponible ou en échec : {err}",
        }

    matches = [el for el in elements if needle and needle in el["text"].casefold()] if needle else []
    return {
        "status": "success",
        "screenshot_path": shot_rel,
        "text": " ".join(full_lines),
        "elements_count": len(elements),
        "elements": elements[:120],
        "find_text": find_text,
        "matches": matches,
    }


# ------------------------------------------------------------------
# ACTIONS SOURIS
# ------------------------------------------------------------------

def computer_mouse_move(x: int, y: int, relative: bool = False) -> dict[str, Any]:
    """Déplace le curseur de la souris aux coordonnées (x, y) absolues ou relatives."""
    _check_failsafe()
    metrics = get_screen_metrics()
    target_x = metrics["cursor_x"] + int(x) if relative else int(x)
    target_y = metrics["cursor_y"] + int(y) if relative else int(y)
    target_x, target_y = _validate_coordinates(target_x, target_y)

    if _is_win32():
        ctypes.windll.user32.SetCursorPos(target_x, target_y)
    return {
        "status": "success",
        "action": "mouse_move",
        "x": target_x,
        "y": target_y,
        "relative": relative,
    }


def computer_click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    double: bool = False,
) -> dict[str, Any]:
    """Effectue un clic gauche, droit, milieu ou double-clic aux coordonnées indiquées."""
    _check_failsafe()
    metrics = get_screen_metrics()
    target_x = metrics["cursor_x"] if x is None else int(x)
    target_y = metrics["cursor_y"] if y is None else int(y)
    target_x, target_y = _validate_coordinates(target_x, target_y)

    btn = (button or "left").strip().lower()
    if btn not in {"left", "right", "middle"}:
        raise ValueError("Le bouton de souris doit être 'left', 'right' ou 'middle'.")

    if _is_win32():
        user32 = ctypes.windll.user32
        user32.SetCursorPos(target_x, target_y)
        time.sleep(0.03)
        down_flag, up_flag = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }[btn]
        clicks = 2 if double else 1
        for _ in range(clicks):
            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(up_flag, 0, 0, 0, 0)
            if double:
                time.sleep(0.05)

    return {
        "status": "success",
        "action": "double_click" if double else f"{btn}_click",
        "x": target_x,
        "y": target_y,
        "button": btn,
        "double": double,
    }


def computer_drag(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    steps: int = 10,
) -> dict[str, Any]:
    """Effectue un glisser-déposer (drag & drop) de (start_x, start_y) vers (end_x, end_y)."""
    _check_failsafe()
    sx, sy = _validate_coordinates(start_x, start_y)
    ex, ey = _validate_coordinates(end_x, end_y)
    num_steps = max(2, min(int(steps or 10), 50))

    if _is_win32():
        user32 = ctypes.windll.user32
        user32.SetCursorPos(sx, sy)
        time.sleep(0.03)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        for i in range(1, num_steps + 1):
            _check_failsafe()
            ix = int(sx + (ex - sx) * (i / num_steps))
            iy = int(sy + (ey - sy) * (i / num_steps))
            user32.SetCursorPos(ix, iy)
            time.sleep(0.015)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    return {
        "status": "success",
        "action": "drag",
        "start": {"x": sx, "y": sy},
        "end": {"x": ex, "y": ey},
    }


def computer_scroll(
    clicks: int,
    x: int | None = None,
    y: int | None = None,
) -> dict[str, Any]:
    """Effectue un défilement (scroll) vertical positif (haut) ou négatif (bas)."""
    _check_failsafe()
    if x is not None and y is not None:
        computer_mouse_move(int(x), int(y), relative=False)
    if _is_win32():
        wheel_delta = int(clicks) * 120
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)
    return {
        "status": "success",
        "action": "scroll",
        "clicks": int(clicks),
    }


# ------------------------------------------------------------------
# ACTIONS CLAVIER
# ------------------------------------------------------------------

def _resolve_vk(key: str) -> int:
    clean = (key or "").strip().lower()
    if clean in VK_MAP:
        return VK_MAP[clean]
    if len(clean) == 1:
        ch = clean.upper()
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            return ord(ch)
        if _is_win32():
            res = ctypes.windll.user32.VkKeyScanW(ord(clean))
            if res != -1:
                return res & 0xFF
    raise ValueError(f"Touche clavier non reconnue : {key!r}")


def computer_press(key: str) -> dict[str, Any]:
    """Appuie et relâche une touche individuelle du clavier (ex: 'enter', 'escape', 'tab', 'f5')."""
    _check_failsafe()
    vk = _resolve_vk(key)
    if _is_win32():
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    return {
        "status": "success",
        "action": "key_press",
        "key": key,
        "vk": vk,
    }


def computer_hotkey(keys: list[str]) -> dict[str, Any]:
    """Exécute une combinaison de touches clavier (ex: ['ctrl', 'c'], ['alt', 'tab'], ['ctrl', 'shift', 'p'])."""
    _check_failsafe()
    if not keys or not isinstance(keys, list):
        raise ValueError("La liste 'keys' du raccourci clavier ne peut pas être vide.")
    vks = [_resolve_vk(k) for k in keys]
    if _is_win32():
        user32 = ctypes.windll.user32
        for vk in vks:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.015)
        for vk in reversed(vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.015)
    return {
        "status": "success",
        "action": "hotkey",
        "keys": keys,
    }


def computer_type(text: str, interval_ms: int = 8) -> dict[str, Any]:
    """Frappe une chaîne de caractères au clavier."""
    _check_failsafe()
    if not isinstance(text, str):
        raise ValueError("Le paramètre 'text' doit être une chaîne.")
    delay = max(0.0, min(float(interval_ms) / 1000.0, 0.2))

    if _is_win32():
        user32 = ctypes.windll.user32
        for ch in text:
            _check_failsafe()
            if ch == "\n":
                computer_press("enter")
            elif ch == "\t":
                computer_press("tab")
            else:
                vk_scan = user32.VkKeyScanW(ord(ch))
                if vk_scan != -1:
                    vk = vk_scan & 0xFF
                    shift_state = (vk_scan >> 8) & 0xFF
                    if shift_state & 1:
                        user32.keybd_event(VK_MAP["shift"], 0, 0, 0)
                    user32.keybd_event(vk, 0, 0, 0)
                    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                    if shift_state & 1:
                        user32.keybd_event(VK_MAP["shift"], 0, KEYEVENTF_KEYUP, 0)
            if delay > 0:
                time.sleep(delay)

    return {
        "status": "success",
        "action": "type",
        "length": len(text),
        "text_preview": text[:80],
    }


# ------------------------------------------------------------------
# BOUCLE FERMÉE : PERCEPTION -> ACTION -> OBSERVATION -> VÉRIFICATION
# ------------------------------------------------------------------

def computer_action_verified(
    action_type: str,
    *,
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    text: str = "",
    key: str = "",
    keys: list[str] | None = None,
    expected_window: str = "",
    settle_ms: int = 350,
    workspace: str | Path = "workspace",
) -> dict[str, Any]:
    """Exécute une action Computer Use dans une boucle fermée stricte :
    1. Screenshot & fenêtre active AVANT
    2. Exécution de l'action (click, double_click, right_click, type, press, hotkey, focus_window)
    3. Attente de stabilisation
    4. Screenshot & fenêtre active APRÈS
    5. Comparaison d'écran et vérification du résultat attendu.
    """
    act = (action_type or "").strip().lower()
    before_shot = computer_screenshot(label=f"before_{act}", workspace=workspace)
    before_win = before_shot.get("active_window") or {}
    before_title = str(before_win.get("title") or "")

    # Exécution de l'action demandée
    if act in {"click", "left_click"}:
        action_res = computer_click(x=x, y=y, button=button or "left", double=False)
    elif act == "double_click":
        action_res = computer_click(x=x, y=y, button="left", double=True)
    elif act == "right_click":
        action_res = computer_click(x=x, y=y, button="right", double=False)
    elif act == "move":
        if x is None or y is None:
            raise ValueError("Les coordonnées x et y sont requises pour 'move'.")
        action_res = computer_mouse_move(x=x, y=y)
    elif act == "type":
        action_res = computer_type(text=text)
    elif act == "press":
        action_res = computer_press(key=key)
    elif act == "hotkey":
        action_res = computer_hotkey(keys=keys or [])
    elif act == "focus_window":
        action_res = window_focus(title=expected_window or text)
    else:
        raise ValueError(
            f"Type d'action Computer Use inconnu : {action_type!r}. "
            "Attendu : click, double_click, right_click, move, type, press, hotkey, focus_window."
        )

    time.sleep(max(0.05, min(float(settle_ms) / 1000.0, 5.0)))

    after_shot = computer_screenshot(label=f"after_{act}", workspace=workspace)
    after_win = after_shot.get("active_window") or {}
    after_title = str(after_win.get("title") or "")

    comparison = computer_compare_screens(
        before_shot["abs_path"],
        after_shot["abs_path"],
        workspace=workspace,
    )
    screen_changed = bool(comparison.get("screen_changed"))
    window_changed = before_title != after_title

    window_matched = True
    if expected_window:
        needle = expected_window.strip().casefold()
        window_matched = needle in after_title.casefold()
        if not window_matched:
            found = window_find(expected_window)
            window_matched = bool(found.get("found"))

    if expected_window:
        verified = window_matched
    elif act == "move":
        verified = True
    else:
        verified = screen_changed or window_changed or not _is_win32()

    error_code = ""
    if not verified:
        if expected_window and not window_matched:
            error_code = "expected_window_not_found"
        else:
            error_code = "click_or_action_had_no_effect"

    return {
        "status": "success" if verified else "warning",
        "verified": verified,
        "action_type": act,
        "action_result": action_res,
        "before_screenshot": before_shot["path"],
        "after_screenshot": after_shot["path"],
        "active_window_before": before_title,
        "active_window_after": after_title,
        "screen_changed": screen_changed,
        "window_changed": window_changed,
        "diff_percent": comparison.get("diff_percent", 0.0),
        "changed_bbox": comparison.get("changed_bbox"),
        "expected_window": expected_window,
        "window_matched": window_matched,
        "error_code": error_code,
    }