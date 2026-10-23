# RÔLE DE CE FICHIER :
# Fournit un accès aux fichiers limité à un workspace explicite. Les wrappers
# historiques gardent leur API; ToolRegistry applique les confirmations d'écriture.

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1] / "workspace"
DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024
_SENSITIVE_COMPONENTS = {
    ".aws", ".ssh", ".gnupg", ".git", ".netrc", ".npmrc", ".pypirc",
    "id_rsa", "id_ed25519", "credentials",
    "secrets", "secrets.json", "credentials.json", "__pycache__", ".venv",
    "venv", ".pytest_cache",
}
_SECRET_PATTERNS = [
    re.compile(
        r"(?im)(\b(?:OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY|API_KEY|"
        r"CLIENT_SECRET|ACCESS_TOKEN|AUTH_TOKEN|PASSWORD|PRIVATE_KEY)\b\s*[:=]\s*)"
        r"['\"]?[^\s'\",}]+"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?im)(Authorization\s*:\s*Bearer\s+)[A-Za-z0-9._~+/-]+=*"),
    re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"
    ),
]


class WorkspaceFilesystem:
    """Opérations de fichier confinées au workspace, y compris via symlinks."""

    def __init__(
        self,
        root: str | Path = WORKSPACE_ROOT,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = max_file_bytes

    def resolve(self, relative_path: str, *, allow_root: bool = False) -> Path:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("Un chemin relatif au workspace est requis.")
        provided = Path(relative_path)
        if ".." in provided.parts:
            raise ValueError("Les segments '..' sont interdits dans les chemins du workspace.")
        lexical = provided if provided.is_absolute() else self.root / provided
        try:
            lexical_relative = lexical.relative_to(self.root)
        except ValueError:
            raise ValueError("Le chemin demandé est hors du workspace autorisé.") from None

        for component in lexical_relative.parts:
            normalized = component.casefold()
            if normalized.startswith(".env") or normalized in _SENSITIVE_COMPONENTS:
                raise PermissionError("L'accès aux fichiers d'identifiants est interdit.")

        current = self.root
        for part in lexical_relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError("Les chemins contenant un lien symbolique sont refusés.")

        resolved = lexical.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise ValueError("Le chemin demandé est hors du workspace autorisé.") from None
        if resolved == self.root and not allow_root:
            raise ValueError("Cette opération nécessite un fichier dans le workspace.")
        return resolved

    def _read_bytes(self, path: Path) -> bytes:
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {path.relative_to(self.root)}")
        size = path.stat().st_size
        if size > self.max_file_bytes:
            raise ValueError(
                f"Fichier trop volumineux ({size} octets; limite {self.max_file_bytes})."
            )
        return path.read_bytes()

    @staticmethod
    def _decode(data: bytes) -> str:
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return data.decode("cp1252")

    def read_file(self, relative_path: str) -> str:
        path = self.resolve(relative_path)
        if path.suffix.lower() in {".pdf", ".docx", ".xlsx", ".pptx"}:
            raise ValueError(
                f"{path.suffix} est un format binaire; utilise read_document pour l'extraire."
            )
        data = self._read_bytes(path)
        if b"\x00" in data[:8192]:
            raise ValueError("Le fichier semble binaire; aucune lecture texte n'a été déclarée.")
        return self.redact_secrets(self._decode(data))

    @staticmethod
    def redact_secrets(text: str) -> str:
        redacted = text
        for pattern in _SECRET_PATTERNS:
            if pattern.groups:
                redacted = pattern.sub(r"\1[REDACTED]", redacted)
            else:
                redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def read_bytes(self, relative_path: str) -> bytes:
        path = self.resolve(relative_path)
        return self._read_bytes(path)

    def list_files(self, relative_path: str = ".", recursive: bool = False) -> list[str]:
        path = self.resolve(relative_path, allow_root=True)
        if not path.is_dir():
            raise NotADirectoryError(f"Dossier introuvable : {relative_path}")
        files = []
        if recursive:
            iterator = os.walk(path, topdown=True, followlinks=False)
            for current, directories, filenames in iterator:
                directories[:] = [
                    name for name in directories
                    if name.casefold() not in _SENSITIVE_COMPONENTS
                    and not name.casefold().startswith(".env")
                    and not (Path(current) / name).is_symlink()
                ]
                candidates = [Path(current) / name for name in filenames]
                files.extend(self._visible_file_paths(candidates))
        else:
            files.extend(self._visible_file_paths(list(path.iterdir())))
        return sorted(files)

    def _visible_file_paths(self, candidates: list[Path]) -> list[str]:
        visible = []
        for item in candidates:
            if item.is_symlink() or not item.is_file():
                continue
            if item.name.casefold().startswith(".env") or item.name.casefold() in _SENSITIVE_COMPONENTS:
                continue
            try:
                self.resolve(str(item.relative_to(self.root)))
            except (ValueError, PermissionError):
                continue
            visible.append(item.relative_to(self.root).as_posix())
        return visible

    def find_file(self, name: str, limit: int = 50) -> list[str]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Un nom de fichier est requis.")
        needle = name.casefold()
        matches = [
            relative for relative in self.list_files(".", recursive=True)
            if needle in Path(relative).name.casefold()
        ]
        return matches[:limit]

    def search_files(
        self,
        query: str,
        extensions: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Un texte de recherche est requis.")
        extension_set = {
            value.lower() if value.startswith(".") else f".{value.lower()}"
            for value in (extensions or [])
        }
        needle = query.casefold()
        hits: list[dict[str, object]] = []
        for relative in self.list_files(".", recursive=True):
            if extension_set and Path(relative).suffix.lower() not in extension_set:
                continue
            try:
                contents = self.read_file(relative)
            except (UnicodeDecodeError, ValueError, OSError):
                continue
            for line_number, line in enumerate(contents.splitlines(), start=1):
                if needle in line.casefold():
                    hits.append(
                        {"path": relative, "line": line_number, "text": line[:500]}
                    )
                    if len(hits) >= limit:
                        return hits
        return hits

    def write_file(
        self,
        relative_path: str,
        content: str,
        *,
        overwrite: bool = False,
    ) -> dict[str, object]:
        if not isinstance(content, str):
            raise TypeError("Le contenu à écrire doit être du texte.")
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
            raise PermissionError("Écriture refusée : le contenu ressemble à un secret ou une clé API.")
        if len(content.encode("utf-8")) > self.max_file_bytes:
            raise ValueError("Le contenu dépasse la limite autorisée pour un fichier.")
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.resolve(relative_path)
        if path.exists() and not overwrite:
            raise FileExistsError(f"Le fichier existe déjà : {relative_path}")
        if path.exists() and not path.is_file():
            raise IsADirectoryError(f"Ce chemin n'est pas un fichier : {relative_path}")

        data = content.encode("utf-8")
        if overwrite:
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=path.parent, prefix=".harness-", delete=False
                ) as temp_file:
                    temp_name = temp_file.name
                    temp_file.write(data)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                self.resolve(relative_path)
                os.replace(temp_name, path)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)
        else:
            with path.open("xb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        digest = hashlib.sha256(data).hexdigest()
        return {
            "path": path.relative_to(self.root).as_posix(),
            "bytes": len(data),
            "sha256": digest,
        }

    def patch_file(
        self,
        relative_path: str,
        old_text: str,
        new_text: str,
        *,
        replace_all: bool = False,
    ) -> dict[str, object]:
        if not old_text:
            raise ValueError("Le texte à remplacer ne peut pas être vide.")
        path = self.resolve(relative_path)
        original = self._decode(self._read_bytes(path))
        count = original.count(old_text)
        if count == 0:
            raise ValueError("Le texte à remplacer n'a pas été trouvé; aucun changement.")
        if count > 1 and not replace_all:
            raise ValueError(
                f"Le texte correspond à {count} emplacements; précise replace_all."
            )
        updated = original.replace(old_text, new_text, -1 if replace_all else 1)
        result = self.write_file(relative_path, updated, overwrite=True)
        result["replacements"] = count if replace_all else 1
        return result

    def delete_file(self, relative_path: str) -> dict[str, str]:
        path = self.resolve(relative_path)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {relative_path}")
        path.unlink()
        return {"path": path.relative_to(self.root).as_posix(), "deleted": "true"}

    def move_file(self, source: str, destination: str) -> dict[str, str]:
        source_path = self.resolve(source)
        destination_path = self.resolve(destination)
        if not source_path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {source}")
        if destination_path.exists():
            raise FileExistsError(f"La destination existe déjà : {destination}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path = self.resolve(destination)
        source_path.rename(destination_path)
        return {
            "source": source_path.relative_to(self.root).as_posix(),
            "destination": destination_path.relative_to(self.root).as_posix(),
            "moved": "true",
        }


def _default_filesystem() -> WorkspaceFilesystem:
    return WorkspaceFilesystem(WORKSPACE_ROOT)


def _workspace_path(relative_path: str) -> Path:
    """Wrapper historique utilisé par les anciennes fonctions publiques."""
    return _default_filesystem().resolve(relative_path, allow_root=True)


def read_file(relative_path: str) -> str:
    return _default_filesystem().read_file(relative_path)


def write_file(relative_path: str, content: str) -> Path:
    """Crée un fichier neuf dans workspace/ sans remplacement implicite."""
    result = _default_filesystem().write_file(relative_path, content, overwrite=False)
    return WORKSPACE_ROOT / result["path"]


def list_directory(relative_path: str = ".") -> list[str]:
    path = _default_filesystem().resolve(relative_path, allow_root=True)
    if not path.is_dir():
        raise NotADirectoryError(f"Ce dossier n'existe pas : {relative_path}")
    return sorted(item.name for item in path.iterdir())
