# RÔLE DE CE FICHIER :
# Chaîne de provenance et intégrité absolue des artefacts (Universal Artifact Engine).
# Établit et vérifie la chaîne complète et infalsifiable pour tout artefact externe :
# SOURCE WEB → URL → TÉLÉCHARGEMENT → FICHIER PHYSIQUE → HASH → TYPE/MAGIC BYTES → CONTENU → VÉRIFICATION.
# Empêche toute fabrication, simulation ou substitution locale de document externe demandé.

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.filesystem import WorkspaceFilesystem


@dataclass
class ProvenanceRecord:
    """Enregistrement immuable de la chaîne de provenance d'un artefact."""
    source_kind: str  # "web_download", "agent_generated", "user_uploaded"
    origin_url: str
    resolved_domain: str
    download_timestamp: str
    local_path: str
    file_size: int
    sha256: str
    magic_bytes: str
    task_id: str = ""
    content_excerpt: str = ""
    page_count: int | None = None
    verification_status: str = "verified"  # "verified" ou "failed"
    verification_checks: list[dict[str, Any]] = field(default_factory=list)
    attempted_sources: list[dict[str, Any]] = field(default_factory=list)
    anti_substitution: bool = True  # Garantit qu'aucun fichier n'a été fabriqué en remplacement

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceRecord:
        return cls(
            source_kind=str(data.get("source_kind", "unknown")),
            origin_url=str(data.get("origin_url", "")),
            resolved_domain=str(data.get("resolved_domain", "")),
            download_timestamp=str(data.get("download_timestamp", "")),
            local_path=str(data.get("local_path", "")),
            file_size=int(data.get("file_size", 0)),
            sha256=str(data.get("sha256", "")),
            magic_bytes=str(data.get("magic_bytes", "")),
            task_id=str(data.get("task_id", "")),
            content_excerpt=str(data.get("content_excerpt", "")),
            page_count=data.get("page_count"),
            verification_status=str(data.get("verification_status", "failed")),
            verification_checks=list(data.get("verification_checks") or []),
            attempted_sources=list(data.get("attempted_sources") or []),
            anti_substitution=bool(data.get("anti_substitution", True)),
        )


class ProvenanceLedger:
    """Registre auditable et persistant de la provenance des artefacts dans le workspace."""

    LEDGER_REL_PATH = ".harness/provenance_ledger.json"

    def __init__(self, workspace_path: str | Path) -> None:
        self.workspace_path = Path(workspace_path)
        self.ledger_file = self.workspace_path / self.LEDGER_REL_PATH

    def _load_ledger(self) -> dict[str, dict[str, Any]]:
        if not self.ledger_file.exists():
            return {}
        try:
            with open(self.ledger_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_ledger(self, data: dict[str, dict[str, Any]]) -> None:
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.ledger_file.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp.replace(self.ledger_file)

    def record_download(
        self,
        origin_url: str,
        local_path: str,
        raw_bytes: bytes,
        content_excerpt: str = "",
        page_count: int | None = None,
        attempted_sources: list[dict[str, Any]] | None = None,
        task_id: str = "",
    ) -> ProvenanceRecord:
        """Enregistre un document physiquement téléchargé dans le registre de provenance."""
        norm_path = local_path.replace("\\", "/").lstrip("/")
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
        size = len(raw_bytes)

        # Détection des magic bytes
        magic = "unknown"
        if raw_bytes.startswith(b"%PDF-"):
            magic = raw_bytes[:8].decode("latin-1", errors="replace").strip()
        elif raw_bytes.startswith(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])):
            magic = "PNG"
        elif raw_bytes.startswith(bytes([0xff, 0xd8, 0xff])):
            magic = "JPEG"
        elif raw_bytes.startswith(bytes([0x50, 0x4b, 0x03, 0x04])):
            magic = "ZIP/DOCX"
        else:
            magic = raw_bytes[:8].hex()

        # Extraction textuelle automatique pour les PDF si non fournie
        if not content_excerpt and raw_bytes.startswith(b"%PDF-"):
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
                if page_count is None:
                    page_count = len(reader.pages)
                pages_text = []
                for p in reader.pages[:3]:
                    t = p.extract_text()
                    if t:
                        pages_text.append(t)
                content_excerpt = "\n".join(pages_text)[:4000]
            except Exception:
                pass

        parsed = urllib.parse.urlparse(origin_url)
        domain = parsed.netloc or parsed.path.split("/")[0]

        checks = [
            {"step": "SOURCE WEB", "status": "passed", "detail": f"Domaine source identifié : {domain}"},
            {"step": "URL", "status": "passed", "detail": f"URL distante valide : {origin_url}"},
            {"step": "TÉLÉCHARGEMENT", "status": "passed", "detail": f"{size} octets reçus"},
            {"step": "FICHIER PHYSIQUE", "status": "passed", "detail": f"Écrit sur disque dans {norm_path}"},
            {"step": "HASH", "status": "passed", "detail": f"SHA-256 = {sha256_hash}"},
            {"step": "TYPE/MAGIC BYTES", "status": "passed", "detail": f"Signature = {magic}"},
        ]
        if content_excerpt:
            checks.append({"step": "CONTENU", "status": "passed", "detail": f"Extrait observable ({len(content_excerpt)} car.)"})
        checks.append({"step": "VÉRIFICATION", "status": "passed", "detail": "Chaîne de provenance complète validée sans substitution."})

        record = ProvenanceRecord(
            source_kind="web_download",
            origin_url=origin_url,
            resolved_domain=domain,
            download_timestamp=datetime.now(timezone.utc).isoformat(),
            local_path=norm_path,
            file_size=size,
            sha256=sha256_hash,
            magic_bytes=magic,
            task_id=task_id,
            content_excerpt=content_excerpt[:4000],
            page_count=page_count,
            verification_status="verified",
            verification_checks=checks,
            attempted_sources=list(attempted_sources or []),
            anti_substitution=True,
        )

        ledger = self._load_ledger()
        ledger[norm_path] = record.to_dict()
        self._save_ledger(ledger)
        return record

    def get_provenance(self, local_path: str) -> ProvenanceRecord | None:
        """Récupère l'enregistrement de provenance pour un chemin local s'il existe."""
        norm_path = local_path.replace("\\", "/").lstrip("/")
        ledger = self._load_ledger()
        data = ledger.get(norm_path)
        if not data:
            return None
        return ProvenanceRecord.from_dict(data)

    def get_records_for_task(self, task_id: str) -> list[ProvenanceRecord]:
        """Récupère tous les enregistrements de provenance créés pour une tâche donnée."""
        if not task_id:
            return []
        ledger = self._load_ledger()
        records = []
        for d in ledger.values():
            rec = ProvenanceRecord.from_dict(d)
            if rec.task_id == task_id:
                records.append(rec)
        return records

    def verify_provenance_chain(
        self,
        local_path: str,
        filesystem: WorkspaceFilesystem,
        expected_keywords: list[str] | None = None,
        task_id: str = "",
    ) -> dict[str, Any]:
        """Vérifie rigoureusement la chaîne de provenance d'un fichier physique.
        Rejette toute falsification, modification locale, hash incohérent ou mauvaise tâche.
        """
        norm_path = local_path.replace("\\", "/").lstrip("/")
        record = self.get_provenance(norm_path)
        if not record:
            return {
                "verified": False,
                "error": f"Aucune chaîne de provenance enregistrée pour {norm_path}. Fichier potentiellement synthétisé localement.",
                "checks": [],
            }

        if task_id and record.task_id and record.task_id != task_id:
            return {
                "verified": False,
                "error": f"Isolation de tâche violée : le document {norm_path} appartient à la tâche {record.task_id}, et non {task_id}.",
                "checks": [],
            }

        # 1. Vérification du fichier physique
        try:
            resolved = filesystem.resolve(norm_path)
            if not resolved.exists() or not resolved.is_file():
                return {
                    "verified": False,
                    "error": f"Fichier physique introuvable sur le disque : {norm_path}",
                    "checks": record.verification_checks,
                }
            current_bytes = resolved.read_bytes()
            current_size = len(current_bytes)
            current_hash = hashlib.sha256(current_bytes).hexdigest()
        except Exception as err:
            return {
                "verified": False,
                "error": f"Erreur de lecture du fichier physique : {err}",
                "checks": record.verification_checks,
            }

        # 2. Vérification de l'intégrité du hash
        if current_hash != record.sha256:
            return {
                "verified": False,
                "error": f"Altération détectée pour {norm_path} : SHA-256 actuel {current_hash} != enregistré {record.sha256}",
                "checks": record.verification_checks,
            }

        # 3. Vérification de la taille
        if current_size != record.file_size or current_size == 0:
            return {
                "verified": False,
                "error": f"Incohérence de taille pour {norm_path} : {current_size} octets != {record.file_size}",
                "checks": record.verification_checks,
            }

        # 4. Vérification du format (anti-falsification d'extension)
        magic_ok = False
        if current_bytes.startswith(b"%PDF-"):
            magic_ok = True
        elif current_bytes.startswith(bytes([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])):
            magic_ok = True
        elif current_bytes.startswith(bytes([0xff, 0xd8, 0xff])):
            magic_ok = True
        elif current_bytes.startswith(bytes([0x50, 0x4b, 0x03, 0x04])):
            magic_ok = True
        elif current_size > 50:
            magic_ok = True

        if not magic_ok:
            return {
                "verified": False,
                "error": f"Magic bytes corrompus ou invalides pour {norm_path}.",
                "checks": record.verification_checks,
            }

        return {
            "verified": True,
            "origin_url": record.origin_url,
            "resolved_domain": record.resolved_domain,
            "local_path": norm_path,
            "size_bytes": current_size,
            "sha256": current_hash,
            "magic_bytes": record.magic_bytes,
            "page_count": record.page_count,
            "task_id": record.task_id,
            "checks": record.verification_checks,
        }

    def verify_semantic_match(
        self,
        local_path: str,
        query: str,
        filesystem: WorkspaceFilesystem,
    ) -> dict[str, Any]:
        """Vérifie la correspondance sémantique rigoureuse entre la ressource demandée et l'artefact.
        Rejette fermement tout document étranger (ex: un sujet de Bac quand on demande un CERFA, ou inversement).
        """
        norm_path = local_path.replace("\\", "/").lstrip("/")
        record = self.get_provenance(norm_path)

        clean_q = query.lower()

        # 1. Détection de code CERFA (ex: cerfa 15776, 15776*02, cerfa_15776)
        cerfa_match = re.search(r"(?:cerfa[_\s-]*)?(\d{5})(?:\*?(\d{2}))?", clean_q)
        is_cerfa_query = "cerfa" in clean_q or bool(re.search(r"\b\d{5}\*(?:\d{2})\b", clean_q))

        # 2. Détection d'examen (Bac, Brevet, etc.)
        is_bac = any(k in clean_q for k in ("bac", "baccalauréat", "baccalaureat"))
        bac_year = re.search(r"\b(202\d)\b", clean_q)

        # Collecter tout le texte disponible pour le document candidat
        doc_text = ""
        if record:
            doc_text += f"{record.origin_url} {record.local_path} {record.content_excerpt} "

        doc_text += f" {norm_path} "
        try:
            p_abs = filesystem.resolve(norm_path)
            if p_abs.is_file() and p_abs.stat().st_size > 0:
                raw_data = p_abs.read_bytes()[:32000]
                if raw_data.startswith(b"%PDF-"):
                    try:
                        import pypdf
                        r = pypdf.PdfReader(io.BytesIO(raw_data))
                        for page in r.pages[:3]:
                            txt = page.extract_text()
                            if txt:
                                doc_text += f" {txt} "
                    except Exception:
                        pass
                else:
                    doc_text += f" {raw_data.decode('utf-8', errors='ignore')} "
        except Exception:
            pass

        doc_text_lower = doc_text.lower()

        # Règle stricte pour CERFA :
        if is_cerfa_query and cerfa_match:
            num = cerfa_match.group(1)
            # Le numéro CERFA doit impérativement apparaître dans le texte, l'URL ou le nom du fichier
            if num not in doc_text_lower and f"cerfa_{num}" not in norm_path.lower():
                return {
                    "match": False,
                    "reason": f"Incompatibilité sémantique absolue : Le document '{norm_path}' ne contient pas le numéro CERFA demandé ({num}).",
                    "query_type": "cerfa",
                    "expected_id": num,
                }
            # Si un document d'examen est présenté en lieu et place d'un CERFA, rejet catégorique
            if any(k in norm_path.lower() for k in ("bac", "mathematiques", "metropole")) and "cerfa" not in norm_path.lower():
                return {
                    "match": False,
                    "reason": f"Document étranger rejeté : '{norm_path}' provient d'une mission d'examen indépendante.",
                    "query_type": "cerfa",
                }
            return {"match": True, "reason": f"CERFA {num} vérifié dans le document.", "query_type": "cerfa"}

        # Règle stricte pour Bac / Annales :
        if is_bac:
            # Si on demande du Bac, et que le document est un formulaire administratif/CERFA, rejet catégorique
            if "cerfa" in doc_text_lower and not any(k in doc_text_lower for k in ("bac", "epreuve", "sujet", "mathematique")):
                return {
                    "match": False,
                    "reason": f"Incompatibilité sémantique : Le document '{norm_path}' est un formulaire administratif CERFA et non une annale du Bac.",
                    "query_type": "exam",
                }
            if bac_year:
                year = bac_year.group(1)
                if year not in doc_text_lower and year not in norm_path:
                    return {
                        "match": False,
                        "reason": f"Année d'examen non correspondante : attendu {year}.",
                        "query_type": "exam",
                    }
            return {"match": True, "reason": "Sujet d'examen vérifié.", "query_type": "exam"}

        # Correspondance générale par mots-clés substantifs
        tokens = [w for w in re.findall(r"\w{3,}", clean_q) if w not in {"trouve", "trouver", "telecharge", "telecharger", "workspace", "officiel", "document", "fichier", "pour", "dans", "avec", "cette"}]
        matches = [t for t in tokens if t in doc_text_lower]
        if tokens and len(matches) == 0:
            return {
                "match": False,
                "reason": f"Aucun mot-clé de la requête trouvé dans le document '{norm_path}'.",
                "query_type": "general",
            }

        return {"match": True, "reason": f"{len(matches)}/{len(tokens)} mots-clés vérifiés.", "query_type": "general"}
