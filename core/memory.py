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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.registry import ToolCall, ToolRegistry

_SENSITIVE = re.compile(
    r"(?i)(api[_ -]?key|secret|password|passwd|token|authorization)\s*[:=]\s*\S+"
)


class MemoryManager:
    PROJECT_PATH = ".harness/project_memory.json"

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools
        self.session: list[str] = []
        self.decisions: list[str] = []
        self.preferences: dict[str, str] = {}
        self.project: list[str] = self._load_project()

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
        mission_id: str,
        declencheur_pattern: str,
        diagnostic: str,
        regle: str,
        score_utilite: float = 1.0,
        created_at: float | None = None,
    ) -> str:
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

        # Règle 1 : Erreur de syntaxe / AST
        if "syntaxerror" in blob or "syntax" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="syntaxe code python syntaxerror ast",
                diagnostic="Erreur de syntaxe détectée lors de l'édition ou génération de code",
                regle="Toujours valider la syntaxe AST d'un fichier source avant de valider la modification",
                score_utilite=1.5,
            )
            extracted.append({"id": lid, "diagnostic": "Syntaxe invalide", "regle": "Valider AST"})

        # Règle 2 : Répétition d'outil en échec
        if "repetition guard" in blob or "échec répétitif" in blob or "failing_tool" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="outil echec repetition retry echec repetitif",
                diagnostic="Répétition infructueuse du même outil avec les mêmes arguments",
                regle="Changer d'outil ou d'angle d'attaque dès le 2e échec au lieu de réitérer un appel identique",
                score_utilite=1.4,
            )
            extracted.append({"id": lid, "diagnostic": "Répétition outil", "regle": "Changer de stratégie au 2e échec"})

        # Règle 3 : Quota provider ou rate limit
        if "quota" in blob or "rate limit" in blob or "provider failover" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="quota rate limit provider failover saturation",
                diagnostic="Saturation du quota ou de la limite de débit du modèle courant",
                regle="Basculer sans délai sur un fournisseur alternatif disponible sans boucler",
                score_utilite=1.3,
            )
            extracted.append({"id": lid, "diagnostic": "Quota atteint", "regle": "Failover immédiat"})

        # Règle 4 : Modification non autorisée de test
        if "testtamperingerror" in blob or "tampering" in blob:
            lid = self.record_lesson(
                mission_id=mission_id,
                declencheur_pattern="test modification tampering alteration tdd",
                diagnostic="Tentative d'altération du code de test pour simuler une réussite",
                regle="Les fichiers de tests sont immuables : corriger le code source de production exclusivement",
                score_utilite=1.5,
            )
            extracted.append({"id": lid, "diagnostic": "Altération test", "regle": "Corriger le code sans toucher aux tests"})

        # Repli si échec générique et aucune leçon extraite
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
        # Nettoyage de la requête pour FTS5 (conserve mots alphanumériques >= 3 caractères)
        words = re.findall(r"\w{3,}", query)
        if not words:
            # Requête de secours sur les meilleures leçons
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
                    SELECT l.id, l.mission_id, l.declencheur_pattern, l.diagnostic, l.regle,
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
            # Decay factor : les leçons anciennes perdent du poids selon les jours écoulés
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

        # Trie par score effectif décroissant
        results.sort(key=lambda item: item["effective_score"], reverse=True)
        top = results[:limit]

        # Met à jour count_used et last_used_at pour les leçons sélectionnées
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
