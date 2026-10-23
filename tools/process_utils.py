# RÔLE DE CE FICHIER :
# Prépare un environnement minimal pour les sous-processus locaux. Les tools de test
# et Git l'utilisent afin de ne pas transmettre les clés API héritées du terminal.

from __future__ import annotations

import os


_SAFE_ENVIRONMENT_NAMES = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
}


def safe_subprocess_environment() -> dict[str, str]:
    """Ne transmet que les variables système nécessaires aux outils locaux."""
    return {
        name: value
        for name, value in os.environ.items()
        if name.upper() in _SAFE_ENVIRONMENT_NAMES
    }
