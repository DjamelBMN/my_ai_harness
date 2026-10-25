# RÔLE DE CE FICHIER :
# Chargé automatiquement (mécanisme standard `site`) par chaque script Python lancé par
# NeoHarness, grâce au PYTHONPATH préparé dans tools/python_runtime.py.
# Il rend Matplotlib réellement headless et capture les figures produites :
#   - plt.show() ne bloque jamais : il enregistre les figures ouvertes en PNG puis les ferme ;
#   - plt.close() enregistre la figure avant sa fermeture ;
#   - à la fin du script, toute figure encore ouverte est enregistrée ;
#   - les PNG vont dans NEOHARNESS_OUTPUT_DIR et la liste réelle est écrite dans
#     NEOHARNESS_FIGURE_MANIFEST (JSON) pour que l'hôte la vérifie.
# Aucun import de Matplotlib n'est forcé : un script sans graphique ne paie aucun coût.

import atexit
import importlib.abc
import importlib.machinery
import json
import os
import sys

_OUTPUT_DIR = os.environ.get("NEOHARNESS_OUTPUT_DIR", "")
_MANIFEST = os.environ.get("NEOHARNESS_FIGURE_MANIFEST", "")
_STATE = {"counter": 0, "figures": [], "errors": [], "patched": False}


def _capture(fig):
    """Enregistre réellement une figure Matplotlib en PNG dans le dossier output/."""
    if not _OUTPUT_DIR or fig is None:
        return None
    try:
        path = getattr(fig, "_neoharness_png", None)
        if not path:
            _STATE["counter"] += 1
            os.makedirs(_OUTPUT_DIR, exist_ok=True)
            path = os.path.join(_OUTPUT_DIR, "figure_%d.png" % _STATE["counter"])
            fig._neoharness_png = path
        fig.savefig(path, format="png", dpi=110, bbox_inches="tight")
        if path not in _STATE["figures"]:
            _STATE["figures"].append(path)
        return path
    except Exception as exc:  # l'erreur est remontée à l'hôte via le manifeste
        _STATE["errors"].append("%s: %s" % (type(exc).__name__, exc))
        return None


def _capture_all(plt):
    for num in list(plt.get_fignums()):
        _capture(plt.figure(num))


def _patch_pyplot(plt):
    if _STATE["patched"]:
        return
    _STATE["patched"] = True
    original_close = plt.close

    def show(*args, **kwargs):
        _capture_all(plt)
        original_close("all")

    def close(fig=None):
        try:
            if fig is None:
                current = plt.get_fignums()
                if current:
                    _capture(plt.gcf())
            elif isinstance(fig, str) and fig == "all":
                _capture_all(plt)
            elif isinstance(fig, int):
                if fig in plt.get_fignums():
                    _capture(plt.figure(fig))
            elif hasattr(fig, "savefig"):
                _capture(fig)
        except Exception as exc:
            _STATE["errors"].append("%s: %s" % (type(exc).__name__, exc))
        return original_close(fig)

    plt.show = show
    plt.close = close

    # atexit est LIFO : Matplotlib a déjà enregistré Gcf.destroy_all pendant son import.
    # En s'enregistrant maintenant, la capture des figures ouvertes s'exécute AVANT
    # leur destruction.
    def _capture_open_figures():
        try:
            _capture_all(plt)
        except Exception as exc:
            _STATE["errors"].append("%s: %s" % (type(exc).__name__, exc))

    atexit.register(_capture_open_figures)


class _PyplotLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def create_module(self, spec):
        return self._wrapped.create_module(spec)

    def exec_module(self, module):
        self._wrapped.exec_module(module)
        _patch_pyplot(module)


class _PyplotFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != "matplotlib.pyplot":
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is not None and spec.loader is not None:
            spec.loader = _PyplotLoader(spec.loader)
        return spec


def _finalize():
    """Enregistré au démarrage, donc exécuté en dernier : écrit le manifeste réel."""
    plt = sys.modules.get("matplotlib.pyplot")
    if _MANIFEST:
        try:
            with open(_MANIFEST, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "matplotlib_used": plt is not None,
                        "figures": _STATE["figures"],
                        "errors": _STATE["errors"],
                    },
                    handle,
                )
        except Exception:
            pass


if _OUTPUT_DIR:
    sys.meta_path.insert(0, _PyplotFinder())
    atexit.register(_finalize)
