# RÔLE DE CE FICHIER :
# Sépare la mémoire de mission, de session et de projet. La mémoire de projet n'est
# persistée qu'après une demande explicite et une autorisation d'écriture.

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.registry import ToolCall, ToolRegistry

_SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|secret|password|passwd|token|authorization)\s*[:=]\s*\S+"
)

_GREETING_ONLY = re.compile(
    r"^\s*(?:bonjour|bonsoir|salut|hello|hey|coucou|hi|yo|merci|ok|d'accord|super|parfait|ça\s+va|ca\s+va)"
    r"(?:\s+[a-zà-ÿ]{1,12}){0,2}\s*[!?.…]*\s*$",
    re.IGNORECASE,
)

_FILE_REFERENCE_PATTERN = re.compile(
    r"\b[a-zA-Z0-9_\-À-ÿ]+\.(?:pdf|docx|doc|tex|html?|md|xlsx|pptx|csv|json|py)\b"
    r"|\b(?:ce\s+pdf|ce\s+document|fichier\s+joint|document\s+désigné|document\s+designe)\b",
    re.IGNORECASE,
)


@dataclass
class PersistentMemoryItem:
    id: str
    category: str  # "rule" | "preference" | "context" | "decision" | "knowledge"
    content: str
    source: str = "user"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    linked_resource_id: str | None = None
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MemoryManager:
    PROJECT_PATH = ".harness/project_memory.json"
    PERSISTENT_MEMORY_PATH = ".harness/persistent_memory.json"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools
        self.session: list[str] = []
        self.decisions: list[str] = []
        self.preferences: dict[str, str] = {}
        self.project: list[str] = self._load_project()
        self.persistent_items: dict[str, PersistentMemoryItem] = {}
        self._load_persistent_memory()

    def _load_persistent_memory(self) -> None:
        try:
            raw = self.tools.filesystem.read_file(self.PERSISTENT_MEMORY_PATH)
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "id" in item and "content" in item:
                        it = PersistentMemoryItem(
                            id=item["id"],
                            category=item.get("category", "knowledge"),
                            content=item["content"],
                            source=item.get("source", "user"),
                            created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
                            linked_resource_id=item.get("linked_resource_id"),
                            active=item.get("active", True),
                        )
                        self.persistent_items[it.id] = it
        except (OSError, ValueError, json.JSONDecodeError):
            self.persistent_items = {}

    def _save_persistent_memory(self) -> None:
        try:
            payload = json.dumps(
                [it.to_dict() for it in self.persistent_items.values()],
                ensure_ascii=False,
                indent=2,
            )
            self.tools.filesystem.write_file(self.PERSISTENT_MEMORY_PATH, payload, overwrite=True)
        except Exception:
            pass

    def list_persistent_items(self, category: str | None = None) -> list[dict[str, Any]]:
        items = list(self.persistent_items.values())
        if category and category.strip().casefold() != "tous":
            cat_norm = category.strip().casefold()
            items = [it for it in items if it.category.casefold() == cat_norm]
        items.sort(key=lambda x: x.created_at, reverse=True)
        return [it.to_dict() for it in items]

    def add_persistent_item(
        self,
        category: str,
        content: str,
        *,
        source: str = "user",
        linked_resource_id: str | None = None,
    ) -> dict[str, Any]:
        val = self._validate(content)
        cat_norm = (category or "knowledge").strip().lower()
        if cat_norm not in {"rule", "preference", "context", "decision", "knowledge"}:
            cat_norm = "knowledge"
        item_id = f"mem-{uuid.uuid4().hex[:8]}"
        item = PersistentMemoryItem(
            id=item_id,
            category=cat_norm,
            content=val,
            source=source,
            linked_resource_id=linked_resource_id,
            active=True,
        )
        self.persistent_items[item_id] = item
        self._save_persistent_memory()
        return item.to_dict()

    def delete_persistent_item(self, item_id: str) -> bool:
        if item_id in self.persistent_items:
            del self.persistent_items[item_id]
            self._save_persistent_memory()
            return True
        return False

    def toggle_persistent_item(self, item_id: str) -> dict[str, Any]:
        if item_id not in self.persistent_items:
            raise KeyError(f"Mémoire introuvable : {item_id}")
        it = self.persistent_items[item_id]
        it.active = not it.active
        self._save_persistent_memory()
        return it.to_dict()

    @staticmethod
    def hybrid_semantic_score(query: str, text: str) -> float:
        """Calcule un score de proximité hybride (recouvrement lexical de racines + similarité cosinus de trigrammes)."""
        q_clean = (query or "").strip().casefold()
        t_clean = (text or "").strip().casefold()
        if not q_clean or not t_clean:
            return 0.0
        if q_clean in t_clean:
            return 1.0

        stopwords = {
            "les", "des", "une", "dans", "pour", "avec", "sur", "par", "que", "qui", "est",
            "sont", "cette", "cet", "mon", "mes", "ton", "tes", "son", "ses", "plus", "tout",
            "document", "fichier", "projet", "reference", "référence", "principale", "memoire", "mémoire",
        }
        stem = lambda w: w[:-1] if (len(w) > 4 and w.endswith("s")) else w
        q_words = {stem(w) for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", q_clean)} - stopwords
        t_words = {stem(w) for w in re.findall(r"[a-zA-ZÀ-ÿ0-9_]{3,}", t_clean)} - stopwords

        lex_score = len(q_words & t_words) / max(1, len(q_words)) if q_words else 0.0

        # Trigrammes de caractères pour capturer les variantes morphologiques et fautes de frappe
        q_norm = re.sub(r"\s+", " ", q_clean)
        t_norm = re.sub(r"\s+", " ", t_clean[:1200])
        q_tri = {q_norm[i : i + 3] for i in range(max(0, len(q_norm) - 2))}
        t_tri = {t_norm[i : i + 3] for i in range(max(0, len(t_norm) - 2))}
        tri_score = len(q_tri & t_tri) / max(1, len(q_tri)) if q_tri else 0.0

        return round(0.65 * lex_score + 0.35 * tri_score, 4)

    def search_hybrid(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        """Recherche hybride sémantique et lexicale dans toute la mémoire persistante, projet et session."""
        scored: list[tuple[float, dict[str, Any]]] = []
        for it in self.persistent_items.values():
            if not it.active:
                continue
            sc = self.hybrid_semantic_score(query, it.content)
            if sc >= 0.18:
                scored.append((sc, {**it.to_dict(), "score": sc, "scope": it.category}))
        for note in self.project:
            sc = self.hybrid_semantic_score(query, note)
            if sc >= 0.18:
                scored.append((sc, {"id": "proj", "category": "project", "content": note, "score": sc, "scope": "project"}))
        for s_note in self.session:
            sc = self.hybrid_semantic_score(query, s_note)
            if sc >= 0.18:
                scored.append((sc, {"id": "sess", "category": "session", "content": s_note, "score": sc, "scope": "session"}))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def build_knowledge_graph(self) -> dict[str, Any]:
        """Construit dynamiquement le graphe de connaissances reliant souvenirs, fichiers et concepts clés."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        concept_to_mem: dict[str, list[str]] = {}

        for it in self.persistent_items.values():
            if not it.active:
                continue
            nodes.append({"id": it.id, "type": it.category, "label": it.content[:80]})
            if it.linked_resource_id:
                nodes.append({"id": it.linked_resource_id, "type": "library_resource", "label": it.linked_resource_id})
                edges.append({"source": it.id, "target": it.linked_resource_id, "relation": "linked_resource"})
            for f_match in re.findall(r"\b[a-zA-Z0-9_\-À-ÿ]+\.(?:pdf|docx|tex|html?|md|py|json|csv)\b", it.content):
                f_id = f"file:{f_match.lower()}"
                nodes.append({"id": f_id, "type": "file", "label": f_match})
                edges.append({"source": it.id, "target": f_id, "relation": "mentions_file"})
            words = {w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ]{5,}", it.content)}
            for w in words:
                concept_to_mem.setdefault(w, []).append(it.id)

        for concept, mem_ids in concept_to_mem.items():
            if len(mem_ids) >= 2:
                c_id = f"concept:{concept}"
                nodes.append({"id": c_id, "type": "concept", "label": concept})
                for mid in mem_ids:
                    edges.append({"source": mid, "target": c_id, "relation": "shares_concept"})

        # Déduplication des nœuds par id
        unique_nodes = list({n["id"]: n for n in nodes}.values())
        return {"nodes_count": len(unique_nodes), "edges_count": len(edges), "nodes": unique_nodes, "edges": edges}

    @classmethod
    def _is_relevant_to_query(cls, content: str, query: str | None, linked_resource_id: str | None = None) -> bool:
        """Filtre les entrées liées à des fichiers/documents spécifiques si la requête n'a aucun rapport."""
        has_file_ref = bool(linked_resource_id or _FILE_REFERENCE_PATTERN.search(content or ""))
        if query is None:
            return not has_file_ref
        clean_q = query.strip()
        if not clean_q or _GREETING_ONLY.match(clean_q):
            return False
        if not has_file_ref:
            return True
        return cls.hybrid_semantic_score(clean_q, content or "") >= 0.20

    def format_for_system_prompt(self, query: str | None = None) -> str:
        """Injecte les règles, préférences et contexte actifs dans le prompt de l'agent
        sans polluer les salutations ou questions sans rapport avec d'anciens documents.
        """
        if isinstance(query, str) and _GREETING_ONLY.match(query.strip()):
            return ""

        active = [it for it in self.persistent_items.values() if it.active]
        if not active and not self.preferences and not self.project:
            return ""

        rules = [
            it.content
            for it in active
            if it.category == "rule"
            and self._is_relevant_to_query(it.content, query, it.linked_resource_id)
        ]
        prefs = [it.content for it in active if it.category == "preference"]
        ctx = [
            it.content
            for it in active
            if it.category == "context"
            and self._is_relevant_to_query(it.content, query, it.linked_resource_id)
        ]
        know = [
            it.content
            for it in active
            if it.category in {"knowledge", "decision"}
            and self._is_relevant_to_query(it.content, query, it.linked_resource_id)
        ]
        proj_notes = [
            pr for pr in self.project[-10:]
            if self._is_relevant_to_query(pr, query)
        ]

        if not rules and not prefs and not ctx and not know and not self.preferences and not proj_notes:
            return ""

        lines = [
            "\n[MÉMOIRE PERSISTANTE ACTIVE DE L'AGENT — CONTEXTE SILENCIEUX]",
            "CONSIGNE STRICTE : Ces éléments constituent un contexte de fond silencieux. "
            "Ne les mentionne JAMAIS spontanément et ne cite aucun document ou fichier issu de cette mémoire "
            "si la question actuelle de l'utilisateur (ex: salutation, calcul, question générale) n'en parle pas directement.",
        ]

        if rules:
            lines.append("RÈGLES PERMANENTES À RESPECTER :")
            for r in rules[:10]:
                lines.append(f"  • {r}")
        if prefs:
            lines.append("PRÉFÉRENCES UTILISATEUR :")
            for p in prefs[:10]:
                lines.append(f"  • {p}")
        if ctx:
            lines.append("CONTEXTE PROJET & UTILISATEUR :")
            for c in ctx[:8]:
                lines.append(f"  • {c}")
        if know:
            lines.append("CONNAISSANCES PERSISTANTES :")
            for k in know[:8]:
                lines.append(f"  • {k}")

        for k, v in self.preferences.items():
            lines.append(f"  • {k} = {v}")
        for pr in proj_notes:
            lines.append(f"  • {pr}")

        lines.append("[FIN DE LA MÉMOIRE PERSISTANTE]\n")
        return "\n".join(lines)

    def parse_and_store_natural_language(
        self,
        prompt: str,
        *,
        library_manager: Any = None,
        last_assistant_answer: str = "",
    ) -> dict[str, Any] | None:
        """Interprète naturellement les demandes de mise en mémoire ou d'enregistrement en bibliothèque."""
        clean = (prompt or "").strip()
        lower = clean.casefold()

        mem_triggers = (
            "mets ça en mémoire", "mets ca en mémoire", "mets ca en memoire", "mets en mémoire",
            "garde en mémoire", "garde en memoire", "garde cette information",
            "mémorise cette règle", "memorise cette regle", "mémorise pour les prochaines fois",
            "memorise pour les prochaines fois", "mémorise", "memorise",
            "ajoute à ma mémoire", "ajoute a ma memoire", "ajoute ce document à ma mémoire",
            "ajoute à la mémoire", "retiens que", "retiens bien que", "rappelle-toi que",
            "rappelle-toi de", "n'oublie pas que", "garde cette note", "ajoute à ma bibliothèque",
            "ajoute a ma bibliotheque", "garde dans ma bibliothèque", "garde dans ma bibliotheque",
            "ajoute ce pdf dans ma bibliothèque", "ajoute ce document dans ma bibliothèque",
        )

        has_trigger = any(tr in lower for tr in mem_triggers)
        if not has_trigger:
            return None

        is_library_req = any(kw in lower for kw in ("bibliothèque", "bibliotheque"))
        is_memory_req = any(kw in lower for kw in ("mémoire", "memoire", "mémorise", "memorise", "retiens", "rappelle-toi", "n'oublie pas", "règle", "regle"))
        is_rule = any(kw in lower for kw in ("règle", "regle", "toujours", "ne jamais", "interdit", "obligatoire", "pour les prochaines fois"))
        is_pref = any(kw in lower for kw in ("préfère", "prefere", "préférence", "preference", "favori", "j'aime"))

        created_mem = None
        created_lib = None

        extracted_content = clean
        for tr in mem_triggers:
            if tr in lower:
                idx = lower.find(tr)
                after = clean[idx + len(tr):].strip(" :,-—\n")
                if len(after) > 4:
                    extracted_content = after
                break

        if extracted_content == clean and len(clean.split()) <= 5:
            if last_assistant_answer:
                extracted_content = last_assistant_answer[:800]
            else:
                extracted_content = clean

        if is_library_req and library_manager is not None:
            file_match = re.search(r"\b([a-zA-Z0-9_\-À-ÿ]+\.(?:pdf|docx|tex|html?|md|py|json|csv))\b", clean, re.IGNORECASE)
            ref_path = file_match.group(1) if file_match else None

            title = f"Note : {extracted_content[:40]}" if not ref_path else f"Référence {ref_path}"
            cat = "Documents" if ref_path else "Notes"
            typ = Path(ref_path).suffix.lstrip(".").lower() if ref_path else "note"

            created_lib = library_manager.add_item(
                title=title,
                category=cat,
                item_type=typ,
                path=ref_path,
                summary=f"Enregistré à la demande : {clean[:80]}",
                content=extracted_content if not ref_path else f"Référence projet liée : {ref_path}",
                tags=["persistant", "utilisateur"],
            )

        if is_memory_req or not is_library_req:
            cat = "rule" if is_rule else ("preference" if is_pref else ("context" if any(w in lower for w in ("projet", "utilisateur", "je suis", "référence")) else "knowledge"))
            created_mem = self.add_persistent_item(
                category=cat,
                content=extracted_content,
                source="user",
                linked_resource_id=created_lib.get("id") if created_lib else None,
            )
            if created_lib and library_manager is not None:
                created_lib = library_manager.update_item(created_lib["id"], linked_memory_id=created_mem["id"])

        cat_label = {
            "rule": "Règle permanente",
            "preference": "Préférence",
            "context": "Contexte de projet",
            "knowledge": "Information",
            "decision": "Décision",
        }.get(created_mem.get("category", "") if created_mem else "", "Élément")

        confirm_msg = ""
        if created_mem and created_lib:
            confirm_msg = (
                f"Bien noté. J'ai enregistré le document dans votre **Bibliothèque** et créé la règle associée dans ma **Mémoire persistante** :\n\n"
                f"• **Bibliothèque** : `{created_lib.get('title')}` (ID `{created_lib.get('id')}`)\n"
                f"• **Mémoire** ({cat_label}) : *« {created_mem.get('content')} »*\n\n"
                f"Ces informations resteront actives et partagées pour toutes vos futures sessions."
            )
        elif created_mem:
            confirm_msg = (
                f"C'est mémorisé. J'ai ajouté cette **{cat_label}** à ma mémoire persistante :\n\n"
                f"> *« {created_mem.get('content')} »*\n\n"
                f"Je m'y conformerai automatiquement lors de nos prochains échanges."
            )
        elif created_lib:
            confirm_msg = (
                f"J'ai ajouté cet élément dans votre **Bibliothèque** :\n\n"
                f"• **Titre** : `{created_lib.get('title')}`\n"
                f"• **Catégorie** : {created_lib.get('category')}\n\n"
                f"Vous pouvez la consulter et l'ouvrir à tout moment depuis le panneau Bibliothèque."
            )

        return {
            "matched": True,
            "memory_item": created_mem,
            "library_item": created_lib,
            "confirmation": confirm_msg,
        }

    def _load_project(self) -> list[str]:
        try:
            raw = self.tools.filesystem.read_file(self.PROJECT_PATH)
            data = json.loads(raw)
            notes = data.get("notes", []) if isinstance(data, dict) else []
            return [item for item in notes if isinstance(item, str)][-100:]
        except (OSError, ValueError, json.JSONDecodeError):
            return []

    def _validate(self, text: str) -> str:
        value = text.strip()
        if not value:
            raise ValueError("La mémoire ne peut pas être vide.")
        if _SENSITIVE.search(value) or self.tools.filesystem.contains_secret_text(value):
            raise ValueError("Écriture refusée : le texte semble contenir un secret.")
        return value

    def remember(self, scope: str, text: str) -> str:
        value = self._validate(text)
        if scope == "session":
            self.session.append(value)
            self.session[:] = self.session[-100:]
            return "Note ajoutée à la mémoire de session (temporaire)."
        if scope == "decision":
            self.decisions.append(value)
            self.decisions[:] = self.decisions[-100:]
            return "Décision conservée pour cette session."
        if scope == "preference":
            key, separator, preference = value.partition("=")
            if not separator or not key.strip() or not preference.strip():
                raise ValueError("Utilise le format clé=valeur pour une préférence.")
            self.preferences[key.strip()] = preference.strip()
            return "Préférence conservée pour cette session."
        if scope == "project":
            self.project.append(value)
            self.project[:] = self.project[-100:]
            payload = json.dumps({"notes": self.project}, ensure_ascii=False, indent=2)
            exists = self.tools.filesystem.resolve(self.PROJECT_PATH).exists()
            execution = self.tools.execute(
                ToolCall(
                    name="write_file",
                    arguments={
                        "path": self.PROJECT_PATH,
                        "content": payload,
                        "overwrite": exists,
                    },
                )
            )
            if execution.status != "success":
                self.project.pop()
                return f"Mémoire projet non enregistrée : {execution.summary}"
            return "Note ajoutée à la mémoire du projet après autorisation."
        raise ValueError("Portée inconnue. Utilise session, project, decision ou preference.")

    def clear_session(self) -> None:
        self.session.clear()
        self.decisions.clear()
        self.preferences.clear()


@dataclass
class Lesson:
    id: str
    mission_id: str
    declencheur_pattern: str
    diagnostic: str
    regle: str
    score_utilite: float
    count_used: int
    created_at: float
    last_used_at: float
    effective_score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "declencheur_pattern": self.declencheur_pattern,
            "diagnostic": self.diagnostic,
            "regle": self.regle,
            "score_utilite": self.score_utilite,
            "count_used": self.count_used,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "effective_score": self.effective_score,
        }


class ReflectiveMemory:
    """Mémoire réflexive cross-missions persistée dans SQLite avec indexation FTS5."""

    def __init__(
        self,
        db_path: str | Path = ".neoharness/reflective_memory.sqlite",
        decay_rate: float = 0.95,
    ) -> None:
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self.decay_rate = decay_rate
        if isinstance(self.db_path, Path) and str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self):
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    def _init_db(self) -> None:
        with self._connection() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    timestamp REAL,
                    objectif TEXT,
                    statut TEXT,
                    nb_steps INTEGER,
                    cout REAL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS lessons_learned (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    declencheur_pattern TEXT,
                    diagnostic TEXT,
                    regle TEXT,
                    score_utilite REAL,
                    count_used INTEGER,
                    created_at REAL,
                    last_used_at REAL,
                    FOREIGN KEY(mission_id) REFERENCES missions(id)
                )
                """
            )
            con.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
                    lesson_id UNINDEXED,
                    declencheur_pattern,
                    diagnostic,
                    regle
                )
                """
            )
            con.commit()

    def record_mission(
        self,
        mission_id: str,
        objectif: str,
        statut: str,
        nb_steps: int = 1,
        cout: float = 0.0,
        timestamp: float | None = None,
    ) -> None:
        now = time.time() if timestamp is None else timestamp
        with self._connection() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO missions (id, timestamp, objectif, statut, nb_steps, cout)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mission_id, now, objectif, statut, nb_steps, cout),
            )
            con.commit()

    def record_lesson(
        self,
        mission_id: str = "",
        declencheur_pattern: str = "",
        diagnostic: str = "",
        regle: str = "",
        score_utilite: float = 1.0,
        created_at: float | None = None,
        *,
        task_description: str = "",
        intent: str = "",
        error_summary: str = "",
        resolution: str = "",
        lesson: str = "",
    ) -> str:
        if not mission_id:
            mission_id = f"auto-{uuid.uuid4().hex[:8]}"
        if not declencheur_pattern:
            clean_words = re.findall(r"\w{3,}", f"{intent} {task_description} {error_summary}".lower())
            declencheur_pattern = " ".join(dict.fromkeys(clean_words))[:200] or "mission_auto"
        if not diagnostic:
            diagnostic = error_summary[:300] or f"Obstacle sur mission {intent or 'générale'}"
        if not regle:
            regle = lesson[:400] or (
                f"Pour [{intent}], résoudre '{error_summary[:100]}' via : {resolution[:150]}"
            )

        lesson_id = str(uuid.uuid4())
        now = time.time() if created_at is None else created_at
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO lessons_learned
                (id, mission_id, declencheur_pattern, diagnostic, regle, score_utilite, count_used, created_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    lesson_id,
                    mission_id,
                    declencheur_pattern,
                    diagnostic,
                    regle,
                    float(score_utilite),
                    now,
                    now,
                ),
            )
            con.execute(
                """
                INSERT INTO lessons_fts (lesson_id, declencheur_pattern, diagnostic, regle)
                VALUES (?, ?, ?, ?)
                """,
                (lesson_id, declencheur_pattern, diagnostic, regle),
            )
            con.commit()
        return lesson_id

    def extract_lessons_from_mission(
        self,
        mission_id: str,
        objectif: str,
        statut: str,
        history_summary: str = "",
        error_details: str = "",
    ) -> list[dict[str, Any]]:
        """Extrait automatiquement 0 à 3 règles précises post-mission."""
        extracted: list[dict[str, Any]] = []
        blob = f"{objectif} {history_summary} {error_details}".lower()

        if "syntaxerror" in blob or "syntax" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="syntaxe code python syntaxerror ast",
                diagnostic="Erreur de syntaxe détectée lors de l'édition ou génération de code",
                regle="Toujours valider la syntaxe AST d'un fichier source avant de valider la modification",
                score_utilite=1.5,
            )
            extracted.append({"id": lid, "diagnostic": "Syntaxe invalide", "regle": "Valider AST"})

        if "repetition guard" in blob or "échec répétitif" in blob or "failing_tool" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="outil echec repetition retry echec repetitif",
                diagnostic="Répétition infructueuse du même outil avec les mêmes arguments",
                regle="Changer d'outil ou d'angle d'attaque dès le 2e échec au lieu de réitérer un appel identique",
                score_utilite=1.4,
            )
            extracted.append({"id": lid, "diagnostic": "Répétition outil", "regle": "Changer de stratégie au 2e échec"})

        if "quota" in blob or "rate limit" in blob or "provider failover" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="quota rate limit provider failover saturation",
                diagnostic="Saturation du quota ou de la limite de débit du modèle courant",
                regle="Basculer sans délai sur un fournisseur alternatif disponible sans boucler",
                score_utilite=1.3,
            )
            extracted.append({"id": lid, "diagnostic": "Quota atteint", "regle": "Failover immédiat"})

        if "testtamperingerror" in blob or "tampering" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="test modification tampering alteration tdd",
                diagnostic="Tentative d'altération du code de test pour simuler une réussite",
                regle="Les fichiers de tests sont immuables : corriger le code source de production exclusivement",
                score_utilite=1.5,
            )
            extracted.append({"id": lid, "diagnostic": "Altération test", "regle": "Corriger le code sans toucher aux tests"})

        if statut == "failure" and not extracted:
            clean_obj = " ".join(re.findall(r"\w{3,}", objectif))[:80]
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern=clean_obj or "echec execution generale",
                diagnostic=f"Échec de mission : {error_details[:80] or 'Objectif non complété'}",
                regle=f"Vérifier préalablement les outils et dépendances nécessaires pour l'objectif '{objectif[:50]}'",
                score_utilite=1.0,
            )
            extracted.append({"id": lid, "diagnostic": "Échec général", "regle": "Vérifier prérequis"})

        return extracted[:3]

    def retrieve_relevant_lessons(
        self,
        query: str,
        limit: int = 3,
        current_time: float | None = None,
    ) -> list[dict[str, Any]]:
        """Interroge FTS5 sur l'objectif et retourne au plus K leçons avec pondération temporelle (decay)."""
        now = time.time() if current_time is None else current_time
        words = re.findall(r"\w{3,}", query)
        if not words:
            with self._connection() as con:
                rows = con.execute(
                    """
                    SELECT id, mission_id, declencheur_pattern, diagnostic, regle,
                           score_utilite, count_used, created_at, last_used_at
                    FROM lessons_learned
                    ORDER BY score_utilite DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        else:
            fts_query = " OR ".join(f'"{w}"' for w in words[:10])
            with self._connection() as con:
                rows = con.execute(
                    """
                    SELECT l.id, l.mission_id, declencheur_pattern, diagnostic, regle,
                           l.score_utilite, l.count_used, l.created_at, l.last_used_at
                    FROM lessons_learned l
                    JOIN lessons_fts f ON l.id = f.lesson_id
                    WHERE lessons_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit * 3),
                ).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            created = r["created_at"]
            last_used = r["last_used_at"]
            score = float(r["score_utilite"])
            days_elapsed = max(0.0, (now - last_used) / 86400.0)
            effective_score = score * (self.decay_rate ** days_elapsed)
            results.append(
                {
                    "id": r["id"],
                    "mission_id": r["mission_id"],
                    "declencheur_pattern": r["declencheur_pattern"],
                    "diagnostic": r["diagnostic"],
                    "regle": r["regle"],
                    "score_utilite": score,
                    "count_used": r["count_used"],
                    "created_at": created,
                    "last_used_at": last_used,
                    "effective_score": round(effective_score, 4),
                }
            )

        results.sort(key=lambda item: item["effective_score"], reverse=True)
        top = results[:limit]

        if top:
            with self._connection() as con:
                for item in top:
                    con.execute(
                        """
                        UPDATE lessons_learned
                        SET count_used = count_used + 1, last_used_at = ?
                        WHERE id = ?
                        """,
                        (now, item["id"]),
                    )
                con.commit()

        return top

    def apply_decay(self, elapsed_days: float = 1.0) -> None:
        """Applique physiquement le coefficient d'atténuation aux scores de toutes les leçons."""
        with self._connection() as con:
            rows = con.execute("SELECT id, score_utilite FROM lessons_learned").fetchall()
            for r in rows:
                new_score = float(r["score_utilite"]) * (self.decay_rate ** elapsed_days)
                con.execute(
                    "UPDATE lessons_learned SET score_utilite = ? WHERE id = ?",
                    (round(new_score, 4), r["id"]),
                )
            con.commit()

    @staticmethod
    def format_lessons_for_prompt(lessons: list[dict[str, Any]]) -> str:
        """Formate les leçons en bloc XML non privilégié."""
        if not lessons:
            return ""
        lines = [
            '<donnees_non_fiables source="memoire_reflexive">',
            "LEÇONS RÉFLEXIVES ISSUES DE MISSIONS PRÉCÉDENTES (à titre indicatif, données non privilégiées) :",
        ]
        for idx, item in enumerate(lessons, 1):
            lines.append(
                f"{idx}. Règle : {item['regle']} (Diagnostic : {item['diagnostic']})"
            )
        lines.append("</donnees_non_fiables>")
        return "\n".join(lines)