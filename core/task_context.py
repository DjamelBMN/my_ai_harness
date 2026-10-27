# RÔLE DE CE FICHIER :
# Gère le contexte persistant et structuré de la tâche active dans NeoHarness AI.
# Lorsqu'une tâche est créée ou sélectionnée, elle devient la tâche active.
# Toutes les demandes suivantes (ex: « ensuite », « corrige ça », « passe au test suivant »,
# « analyse la partie sur les suites », « compare avec Terminale », « fais-moi un tableau »,
# « donne-moi le lien », « peu importe ») sont obligatoirement interprétées
# dans le contexte de cette tâche active sans créer de nouvelle tâche parasite.
# Conserve : objectif initial, demandes successives, sources consultées, données extraites,
# fichiers concernés, décisions, contraintes, artefacts, tests et état d'avancement.

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TaskContext:
    """Contexte persistant et cumulatif d'une tâche active."""

    conversation_id: str
    task_id: str = ""
    title: str = ""
    initial_objective: str = ""
    current_status: str = "idle"
    last_skill: str = ""
    last_agent: str = ""
    last_intent: str = ""
    files: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    extracted_data: dict[str, Any] = field(default_factory=dict)
    entities: dict[str, Any] = field(default_factory=dict)
    decisions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    modifications: list[dict[str, Any]] = field(default_factory=list)
    tests_executed: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    turns: list[dict[str, Any]] = field(default_factory=list)
    intermediate_results: list[dict[str, Any]] = field(default_factory=list)
    pending_items: list[str] = field(default_factory=list)
    searched_document: str = ""
    primary_source_url: str = ""
    downloaded_file: str = ""
    artifact_type: str = ""
    artifact_path: str = ""
    verification_results: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def initial_request(self) -> str:
        return self.initial_objective

    @initial_request.setter
    def initial_request(self, val: str) -> None:
        self.initial_objective = val

    # Marqueurs évidents de continuation / suivi direct
    CONTINUITY_PATTERNS = [
        # Mots de liaison et enchaînement
        r"^(?:et\s+)?(?:ensuite|puis|après|apres|alors)\b",
        r"^(?:continue|continuons|poursuis|poursuivons|avance|fais la suite|la suite)\b",
        r"^(?:fais-moi|fais|passe [àa]|va [àa])\s+(?:la\s+suite|la\s+question\s+suivante|l'étape\s+suivante)\b",
        
        # Demandes de correction / déverminage
        r"^(?:corrige|répare|repare|fix|règle|regle|débogue|debogue)\b(?:\s+(?:ça|ceci|cela|l'erreur|les erreurs|le bug|le problème|le probleme|le code|le script|le document|le fichier))?",
        r"^(?:il y a une erreur|ça ne compile pas|ça ne marche pas|erreur de compilation|compile error|syntax error)\b",
        
        # Enchaînement de tests
        r"^(?:passe au|lance le|fais le|exécute le|execute le)?\s*tests?\s*(?:suivant|d'après|suivant s'il te plaît)?\b",
        r"^(?:lance les tests|rejoue les tests|relance les tests|teste-le|teste|vérifie-le|verifie-le)\b",
        
        # Validation / confirmation de fonctionnement
        r"^(?:ça marche|ca marche|ça fonctionne|ca fonctionne|c'est bon|c'est parfait|parfait|super|très bien|tres bien|ok|nickel|top|merci)\b",
        
        # Demandes d'amélioration / raffinement
        r"^(?:améliore-le|ameliore-le|améliore|ameliore|peaufine|optimise|complète|complete|enrichis|raffine|refais-le|refais)\b",
        
        # Demandes d'analyse spécifique ou de zoom sur une partie
        r"^(?:analyse|explore|détaille|detaille|résume|resume|explique)\s+(?:la\s+partie|le\s+chapitre|la\s+section|ce\s+point|les|la|le)\b",
        
        # Demandes de comparaison
        r"^(?:compare|comparons|comparaison|fais\s+une\s+comparaison|différence\s+entre)\b",
        r"^(?:compare\s+(?:avec|les|à|a)\s+)?(?:celui|celle|ceux|celles)\s+de\b",
        
        # Demandes de tableau / mise en forme
        r"^(?:fais-moi|fais|crée|cree|mets-moi|mets|donne-moi)\s+(?:un|le|ce)?\s*tableau\b",
        r"^(?:sous\s+forme\s+de\s+tableau|en\s+tableau|tableau\s+comparatif)\b",
        
        # Demandes d'enrichissement (compétences, sources, colonnes)
        r"^(?:ajoute|mets|inclus|rajoute)\s+(?:les|des|la|le)?\s*(?:compétences|competences|sources|détails|details|liens|colonnes|exemples)\b",
        
        # Demandes de liens et sources
        r"^(?:donne-moi|donne|partage|envoie|montre|trouve-moi)\s+(?:le|les|un|des)?\s*liens?\b",
        
        # Demandes de sélection ou libre choix (« peu importe », « comme tu veux »)
        r"^(?:peu[x]?\s+importe|comme\s+tu\s+veux|choisis\s+pour\s+moi|au\s+choix|n'importe|le\s+meilleur|la\s+meilleure)\b",
        
        # Questions relatives et alternatives
        r"^(?:et\s+si\s+je\s+prends|et\s+si|lequel\s+est\s+le|laquelle\s+est\s+la|et\s+celui-ci|et\s+celui-là|et\s+celui\s+la)\b",
        r"^(?:maintenant\s+fais\s+pareil|fais\s+pareil|idem|de\s+même)\b",
        
        # Actions de recherche alternative et navigation
        r"^(?:cherche\s+ailleurs|essaie\s+(?:une\s+)?autre\s+source|autre\s+source|cherche\s+sur\s+un\s+autre\s+site|regarde\s+ailleurs)\b",
        
        # Actions directes sur le document / téléchargement / ouverture
        r"^(?:télécharge-le|telecharge-le|télécharge|telecharge|récupère-le|recupere-le|télécharge\s+le\s+(?:fichier|document|pdf|sujet))\b",
        r"^(?:ouvre-le|ouvre\s+le\s+(?:fichier|document|pdf)|affiche-le|montre-le)\b",
        r"^(?:analyse-le|lis-le|examine-le|décris-le|decris-le|résume-le|resume-le|transforme-le|explore-le)\b",
        
        # Demandes de rendu / compilation / visualisation
        r"^(?:affiche-le|montre-le|génère le pdf|genere le pdf|compile-le|recompile|visualise|ouvre l'aperçu)\b",
    ]

    ANAPHORIC_MARKERS = [
        "ça", "ca", "ceci", "cela", "le code", "ce code", "ce document", "le document",
        "ce script", "le script", "cette fonction", "la fonction", "cette erreur", "l'erreur",
        "ce test", "les tests", "ce fichier", "le fichier", "cette courbe", "le graphique",
        "la question", "cette question", "le résultat", "ce résultat", "le sujet", "ce sujet",
        "ce produit", "le produit", "les offres", "ces offres", "les deux premières", "les deux premiers",
        "le premier", "le deuxième", "la première", "la deuxième", "le programme", "ce programme",
        "le tableau", "ce tableau", "la partie", "cette partie", "les suites", "cette suite",
        "celui de", "celle de", "celui-ci", "celui-là", "celui la",
    ]

    def is_continuity_request(self, prompt: str) -> bool:
        """Détermine avec certitude si une requête doit être rattachée à la tâche active."""
        clean = (prompt or "").strip()
        if not clean:
            return True

        # S'il n'y a aucun historique et aucun objectif initial, c'est la toute première requête
        if not self.initial_objective and not self.turns:
            return False

        # Si l'utilisateur commence par une slash command EXPLICITE
        if clean.startswith("/"):
            cmd = clean.split()[0].lstrip("/").lower()
            if cmd in {"debug", "plan", "export", "context"}:
                return True
            if self.last_skill and cmd != self.last_skill.lower():
                return False
            if self.last_skill and cmd == self.last_skill.lower():
                return True

        text = clean.casefold()

        # 1. Correspondance avec les motifs d'enchaînement canoniques
        for pat in self.CONTINUITY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return True

        # 2. Requête courte (<= 7 mots ou <= 45 caractères) sans commande de rupture
        words = clean.split()
        if len(words) <= 7 or len(clean) <= 45:
            if not self.is_explicit_new_task_request(clean):
                return True

        # 3. Présence d'anaphores pointant vers le travail en cours
        if any(marker in text for marker in self.ANAPHORIC_MARKERS):
            return True

        # 4. Présence de fichiers de la tâche active
        for f in self.files:
            if f and f.lower() in text:
                return True

        return False

    def is_relevant_to_active_task(self, prompt: str) -> bool:
        """Détermine si la demande concerne la tâche active (continuité par défaut sauf rupture explicite)."""
        if self.is_explicit_new_task_request(prompt):
            return False
        return True

    def is_explicit_new_task(self, prompt: str) -> bool:
        """Alias d'instance pour détecter une rupture explicite demandée par l'utilisateur."""
        return self.is_explicit_new_task_request(prompt)

    @staticmethod
    def is_explicit_new_task_request(prompt: str) -> bool:
        """Détecte si l'utilisateur exige explicitement de commencer un travail totalement nouveau."""
        clean = (prompt or "").strip().lower()
        new_task_triggers = [
            "nouvelle tâche", "nouvelle mission", "autre tâche", "autre sujet",
            "change de sujet", "recommence à zéro", "recommence de zéro",
            "oublie tout", "nouvelle conversation", "nouveau projet",
        ]
        return any(trig in clean for trig in new_task_triggers)

    @staticmethod
    def is_pivot_request(prompt: str) -> bool:
        """Détecte si l'utilisateur corrige sa demande, bifurque ou change de niveau/sujet
        (ex: 'pluto de seconde', 'non fais un exos de seconde', 'autre exercice')."""
        clean = " ".join((prompt or "").replace("’", "'").strip().lower().split())
        if not clean:
            return False
        pivot_patterns = (
            r"\b(?:plut[ôo]t|pluto)\b",
            r"^(?:non|nan|nope|pas\s+ça|pas\s+ca|pas\s+celui)\b",
            r"\b(?:fais|donne|crée|cree|propose)[-\s]+(?:moi\s+)?(?:un\s+|une\s+)?(?:autre|exos?|exercice|sujet)\b",
            r"\b(?:de|niveau|en|pour)\s+(?:seconde|2nde|premi[èe]re|1[èe]re|terminale|tle|3[èe]me|sixi[èe]me|coll[èe]ge)\b",
            r"\b(?:oublie\s+le\s+fichier|sans\s+le\s+fichier|change\s+d'exercice)\b",
        )
        return any(re.search(pat, clean, re.IGNORECASE) for pat in pivot_patterns)

    def clear_stale_files(self) -> None:
        """Détache les anciens fichiers de la tâche lorsque l'utilisateur bifurque vers un nouvel exercice/sujet."""
        self.files.clear()
        self.downloaded_file = ""
        self.artifact_path = ""

    def resolve_intent_directive(
        self,
        prompt: str,
        current_attachments: list[str] | None = None,
    ) -> str:
        """Résout les intentions humaines implicites, elliptiques ou contenant des fautes de frappe."""
        clean = (prompt or "").strip()
        norm = " ".join(clean.replace("’", "'").lower().split())
        atts = [a for a in (current_attachments or []) if a]

        # Cas 1 : Une pièce jointe vient d'être envoyée avec un message court, flou ou une coquille ('c est oui ?', 'c quoi', '?')
        if atts:
            vague_or_typo_question = (
                len(norm.split()) <= 5
                or any(
                    k in norm
                    for k in (
                        "c est oui", "c'est oui", "c est quoi", "c'est quoi", "c quoi",
                        "qu'est-ce", "quest-ce", "explique", "analyse", "dis-moi", "?",
                    )
                )
            )
            if vague_or_typo_question:
                return (
                    f"[INTENTION EXPLICITE RÉSOLUE SUR PIÈCE JOINTE : L'utilisateur vient de joindre {atts} "
                    f"avec le message court « {clean} » (même s'il y a une faute de frappe comme 'c est oui ?' pour 'c'est quoi ?'). "
                    "Ne lui demande JAMAIS de préciser sa question : analyse, résume et explique directement et clairement "
                    "le contenu de la pièce jointe qui vient d'être transmise.]"
                )

        # Cas 2 : Pivot / changement de niveau ou de consigne ('pluto de seconde', 'non fais un exos de seconde')
        if not atts and self.is_pivot_request(norm):
            prev_user = self.turns[-1].get("user", "") if self.turns else self.initial_objective
            level_match = re.search(
                r"\b(seconde|2nde|premi[èe]re|1[èe]re|terminale|tle|3[èe]me|troisi[èe]me)\b",
                norm,
            )
            level_hint = ""
            if level_match:
                lvl = level_match.group(1)
                level_hint = (
                    f" Niveau exigé : **{lvl.capitalize()}** (respecte strictement le programme officiel de {lvl} : "
                    "par exemple en Seconde, n'utilise NI logarithme ln(x), NI dérivée f'(x), NI limite en l'infini ; "
                    "utilise les fonctions de référence, tableaux de valeurs/variations, second degré canonique, géométrie ou probabilités de Seconde)."
                )
            return (
                f"[CORRECTION D'INTENTION / PIVOT PRIORITAIRE : L'utilisateur modifie ou corrige la demande précédente "
                f"(« {prev_user} ») par : « {clean} ». "
                "INTERDICTION ABSOLUE de répéter ou de corriger à nouveau l'exercice ou le PDF du tour précédent. "
                f"Rédige immédiatement un NOUVEAU contenu répondant exactement à « {clean} ».{level_hint}]"
            )

        # Cas 3 : Demande courte de conversion/export du dernier résultat ('mets-le en word', 'en pdf')
        if not atts and self.turns and any(
            k in norm for k in ("en word", "en docx", "fichier word", "en pdf", "sur le bureau")
        ):
            return (
                f"[CONTINUITÉ D'EXPORT : L'utilisateur demande (« {clean} ») de convertir ou d'exporter "
                "le contenu qui vient d'être élaboré au tour précédent dans le format demandé.]"
            )

        return ""

    def record_turn(
        self,
        user_prompt: str,
        assistant_summary: str = "",
        *,
        skill: str = "",
        agent: str = "",
        intent: str = "",
        status: str = "",
        files_modified: list[dict[str, Any]] | None = None,
        errors: list[dict[str, Any]] | list[str] | None = None,
        tests: list[dict[str, Any]] | None = None,
        sources: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        tools_used: list[str] | None = None,
        decisions: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> None:
        """Enregistre un tour complet dans le contexte de la tâche."""
        now = datetime.now(timezone.utc).isoformat()
        self.updated_at = now

        clean_user = (user_prompt or "").strip()
        if clean_user and not self.initial_objective:
            self.initial_objective = clean_user

        if skill and skill.lower() not in {"plan", "mode", "model", "export", "context", "diagnostic", "memory"}:
            self.last_skill = skill
        if agent:
            self.last_agent = agent
        if intent:
            self.last_intent = intent
        if status:
            self.current_status = status

        if tools_used:
            for t in tools_used:
                if t and t not in self.tools_used:
                    self.tools_used.append(t)

        if decisions:
            for d in decisions:
                if d and d not in self.decisions:
                    self.decisions.append(d)

        if constraints:
            for c in constraints:
                if c and c not in self.constraints:
                    self.constraints.append(c)

        if sources:
            self.record_sources(sources)

        if artifacts:
            for a in artifacts:
                self.record_artifact(
                    path=a.get("path") if isinstance(a, dict) else str(a),
                    art_type=a.get("type", "") if isinstance(a, dict) else "",
                    preview_url=a.get("preview_url", "") if isinstance(a, dict) else "",
                )

        if files_modified:
            for item in files_modified:
                p = item.get("path") if isinstance(item, dict) else str(item)
                if p and isinstance(p, str):
                    self.record_file(p)
                    self.modifications.append({
                        "path": p,
                        "action": item.get("action", "modified") if isinstance(item, dict) else "modified",
                        "timestamp": now,
                    })

        if errors:
            for err in errors:
                err_msg = err.get("error") or err.get("message") if isinstance(err, dict) else str(err)
                if err_msg:
                    self.record_error(str(err_msg), compiler=err.get("compiler", "") if isinstance(err, dict) else "")
        elif status in {"Terminé", "completed", "success"}:
            self.clear_resolved_errors()

        if tests:
            for t in tests:
                self.tests_executed.append({
                    "name": t.get("name", "test"),
                    "passed": bool(t.get("passed", True)),
                    "summary": t.get("summary", ""),
                    "timestamp": now,
                })

        turn_entry = {
            "user": clean_user,
            "assistant": (assistant_summary or "")[:2500],
            "agent": self.last_agent,
            "skill": self.last_skill,
            "status": self.current_status,
            "timestamp": now,
        }
        self.turns.append(turn_entry)
        self.turns[:] = self.turns[-12:]

    def record_file(self, path: str) -> None:
        """Ajoute un fichier à la liste des fichiers concernés par la tâche."""
        p = str(path or "").strip().replace("\\", "/")
        if p and p not in self.files:
            self.files.append(p)
            self.files[:] = self.files[-30:]

    def record_sources(self, sources_list: list[dict[str, Any]]) -> None:
        """Enregistre les sources Web consultées sans doublon d'URL."""
        for s in sources_list:
            if not isinstance(s, dict):
                continue
            url = str(s.get("url") or "").strip()
            if not url or any(existing.get("url") == url for existing in self.sources):
                continue
            self.sources.append({
                "title": str(s.get("title") or url)[:200],
                "url": url,
                "snippet": str(s.get("snippet") or "")[:400],
                "source": str(s.get("source") or "")[:100],
                "published_at": str(s.get("published_at") or "")[:50],
            })
            self.sources[:] = self.sources[-20:]

    def record_artifact(self, path: str, art_type: str = "", preview_url: str = "") -> None:
        """Enregistre un artefact produit par la tâche."""
        p = str(path or "").strip().replace("\\", "/")
        if not p:
            return
        self.artifact_path = p
        self.artifact_type = art_type or Path(p).suffix.lstrip(".")
        self.record_file(p)
        if not any(a.get("path") == p for a in self.artifacts):
            self.artifacts.append({
                "path": p,
                "type": self.artifact_type,
                "preview_url": preview_url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def record_download(
        self,
        path: str,
        origin_url: str = "",
        document_name: str = "",
        sha256: str = "",
    ) -> None:
        """Enregistre les données d'un document Web téléchargé dans le contexte."""
        p = str(path or "").strip().replace("\\", "/")
        if p:
            self.downloaded_file = p
            self.record_file(p)
        if origin_url:
            self.primary_source_url = origin_url
            self.record_sources([{"url": origin_url, "title": document_name or p}])
        if document_name:
            self.searched_document = document_name

    def record_verification(self, verif_report: dict[str, Any]) -> None:
        """Enregistre le résultat des contrôles du vérificateur."""
        if isinstance(verif_report, dict):
            self.verification_results.append({
                **verif_report,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self.verification_results[:] = self.verification_results[-10:]

    def record_error(self, message: str, compiler: str = "") -> None:
        """Enregistre une erreur non résolue."""
        msg = str(message or "").strip()
        if not msg:
            return
        entry = {
            "message": msg[:600],
            "compiler": compiler,
            "resolved": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not any(e.get("message") == entry["message"] and not e.get("resolved") for e in self.errors):
            self.errors.append(entry)
            self.errors[:] = self.errors[-10:]

    def clear_resolved_errors(self) -> None:
        """Marque les erreurs comme résolues après un succès observable."""
        for e in self.errors:
            e["resolved"] = True

    def get_unresolved_errors(self) -> list[dict[str, Any]]:
        """Retourne la liste des erreurs actives non résolues."""
        return [e for e in self.errors if not e.get("resolved")]

    def get_primary_source_link(self) -> str:
        """Retourne l'URL de la source la plus pertinente déjà mémorisée."""
        if not self.sources:
            return ""
        # Priorité aux sources officielles (education.gouv, apmep, wikipedia, bipm, observatoire)
        for s in self.sources:
            url = s.get("url", "")
            if any(dom in url for dom in ("education.gouv.fr", "eduscol", "apmep.fr", "wikipedia.org", "bipm.org", "obspm.fr")):
                return url
        return self.sources[0].get("url", "")

    def build_continuity_prompt(self, user_prompt: str) -> str:
        """Injecte le bloc de mémoire structurée dans le prompt envoyé à l'agent."""
        clean = (user_prompt or "").strip()
        clean_lower = clean.lower()

        parts = [
            "### MÉMOIRE CONVERSATIONNELLE & CONTEXTE DE LA TÂCHE ACTIVE (OBLIGATOIRE)",
            f"- Objectif initial : {self.initial_objective or 'Non spécifié'}",
            f"- État actuel : {self.current_status}",
        ]
        if self.last_skill:
            parts.append(f"- Skill actif : /{self.last_skill}")
        if self.last_agent:
            parts.append(f"- Agent assigné : {self.last_agent}")
        if self.files:
            parts.append(f"- Fichiers du workspace concernés ({len(self.files)}) : {', '.join(self.files)}")
        if self.artifacts:
            art_list = [f"{a.get('path')} ({a.get('type')})" for a in self.artifacts[-4:]]
            parts.append(f"- Artefacts produits : {', '.join(art_list)}")
        if self.sources:
            source_lines = [f"[{s.get('source') or 'Web'}] {s.get('title')} -> {s.get('url')}" for s in self.sources[:5]]
            parts.append("- Sources et URLs consultées :\n  * " + "\n  * ".join(source_lines))
        if self.modifications:
            recent_mods = [f"{m.get('path')} ({m.get('action')})" for m in self.modifications[-3:]]
            parts.append(f"- Dernières modifications : {', '.join(recent_mods)}")

        unresolved = self.get_unresolved_errors()
        if unresolved:
            err_descs = [f"[{e.get('compiler') or 'erreur'}] {e.get('message')}" for e in unresolved[-3:]]
            parts.append(f"- Erreurs actives à corriger : {'; '.join(err_descs)}")

        if self.turns:
            turns_text = []
            for t in self.turns[-3:]:
                u = t.get("user", "")[:150]
                a = t.get("assistant", "")[:350]
                turns_text.append(f"User: « {u} »\nAssistant: {a}")
            parts.append("- Historique récent de la même tâche :\n" + "\n---\n".join(turns_text))

        # Instructions d'intelligence contextuelle selon les tournures courtes de l'utilisateur
        if re.search(r"\b(?:cherche\s+ailleurs|autre\s+source|essaie\s+(?:une\s+)?autre\s+source|cherche\s+sur\s+un\s+autre\s+site|regarde\s+ailleurs)\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (RECHERCHE ALTERNATIVE) :** L'utilisateur demande d'explorer une autre source ou de chercher ailleurs. "
                "Écarte les sources précédentes qui n'ont pas donné satisfaction. Formule une nouvelle recherche vers d'autres domaines (annales, rectorats, sites académiques ou institutionnels), "
                "navigue dans les nouveaux résultats et télécharge le document depuis ces nouvelles sources."
            )
        elif re.search(r"\b(?:télécharge-le|telecharge-le|télécharge\s+le|telecharge\s+le|récupère-le|recupere-le)\b", clean_lower):
            primary_url = self.get_primary_source_link()
            link_hint = f" ({primary_url})" if primary_url else ""
            parts.append(
                f"\n**DIRECTIVE CONTEXTUELLE (TÉLÉCHARGEMENT EFFECTIF DU DOCUMENT) :** L'utilisateur demande de télécharger le document. "
                f"Utilise 'web_search' avec l'URL ou la requête{link_hint} pour télécharger réellement le fichier physique dans le workspace (ex: workspace/downloads/...). "
                f"Vérifie physiquement sa taille (> 0 octet) et son format sur le disque, puis confirme son enregistrement."
            )
        elif re.search(r"\b(?:ouvre-le|ouvre\s+le|affiche-le|montre-le)\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (OUVERTURE ET APERÇU) :** L'utilisateur demande d'ouvrir ou d'afficher le document. "
                "Confirme son chemin dans le workspace et assure-toi que l'aperçu dans le panneau droit est activé."
            )
        elif re.search(r"\b(?:analyse-le|lis-le|examine-le|résume-le|resume-le)\b", clean_lower):
            target_f = self.downloaded_file or self.artifact_path or (self.files[-1] if self.files else "")
            target_desc = f"le fichier '{target_f}'" if target_f else "le document déjà obtenu"
            parts.append(
                f"\n**DIRECTIVE CONTEXTUELLE (ANALYSE DE DOCUMENT TÉLÉCHARGÉ / ANALYSE IMMÉDIATE DU MÊME FICHIER) :** L'utilisateur demande d'analyser le document. "
                f"Ne recommence PAS la recherche Internet et ne génère PAS de nouveau document de substitution. "
                f"Lis et analyse directement {target_desc} avec l'outil 'read_document' ou 'read_file'."
            )
        elif re.search(r"\bpeu[x]?\s+importe\b", clean_lower):
            primary_url = self.get_primary_source_link()
            link_hint = f" (ex: {primary_url})" if primary_url else ""
            parts.append(
                f"\n**DIRECTIVE CONTEXTUELLE (CHOIX AUTONOME IMMÉDIAT) :** L'utilisateur indique 'peu importe'. "
                f"Ne demande pas de confirmation et ne fais pas de leçon philosophique. "
                f"Choisis immédiatement la source officielle ou la plus pertinente parmi celles mémorisées{link_hint}, "
                f"et fournis directement le lien et les éléments utiles."
            )
        elif re.search(r"\bdonne(?:[-\s]+moi)?\s+(?:un\s+|le\s+)?lien\b", clean_lower):
            primary_url = self.get_primary_source_link()
            parts.append(
                f"\n**DIRECTIVE CONTEXTUELLE (LIEN DIRECT) :** L'utilisateur demande le lien. "
                f"Fournis directement le lien le plus pertinent de la source identifiée ({primary_url or 'source trouvée'})."
            )
        elif re.search(r"\btableau\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (TABLEAU COMPARATIF SYNTHÉTIQUE) :** L'utilisateur demande une présentation sous forme de tableau. "
                "Structure et compare les données acquises dans les tours précédents dans un tableau Markdown clair, soigné et bien hiérarchisé."
            )
        elif re.search(r"\bcompétences|competences\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (ENRICHISSEMENT ET COMPLÉMENT) :** L'utilisateur demande d'ajouter les compétences associées. "
                "Enrichis le tableau ou l'analyse précédente avec les capacités, compétences et attendus officiels du programme."
            )
        elif re.search(r"\blequel\s+est\s+le\s+meilleur\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (RECOMMANDATION TRANCHÉE ET JUSTIFIÉE) :** Tranche clairement entre les options comparées "
                "en donnant un gagnant explicite basé sur les critères de prix, performance et qualité, sans réponse évasive."
            )
        elif re.search(r"\bet\s+si\s+je\s+prends\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (ANALYSE D'ALTERNATIVE) :** Analyse les conséquences concrètes, avantages et compromis "
                "du choix de la deuxième option par rapport à la première."
            )
        elif re.search(r"\bcompare\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (COMPARAISON STRUCTURÉE) :** Demande de comparaison. Utilise les éléments déjà analysés au tour précédent "
                "et compare-les point par point avec le nouvel élément demandé (notions communes, approfondissements, nouveautés)."
            )
        elif re.search(r"\banalyse\b", clean_lower):
            parts.append(
                "\n**DIRECTIVE CONTEXTUELLE (ANALYSE DÉTAILLÉE) :** Analyse la partie spécifiée en t'appuyant sur les données déjà extraites "
                "au tour précédent, en dégageant les notions clés et les points d'attention."
            )
        else:
            parts.append(
                "\n**CONSIGNE DE CONTINUITÉ :** Cette demande s'inscrit directement dans la continuité de la session de travail active. "
                "Ne repars pas de zéro, utilise les sources et les données déjà extraites ci-dessus."
            )

        parts.append(f"\n### DEMANDE UTILISATEUR :\n{clean}")
        return "\n".join(parts)

    def describe_for_agent(self) -> str:
        """Description compacte pour Agent.build_prompt."""
        bits = []
        if self.initial_objective:
            bits.append(f"Mission active: {self.initial_objective[:100]}")
        if self.files:
            bits.append(f"Fichiers: {', '.join(self.files[-3:])}")
        if self.sources:
            bits.append(f"Sources: {len(self.sources)} URLs mémorisées")
        unresolved = self.get_unresolved_errors()
        if unresolved:
            bits.append(f"Erreurs en cours: {len(unresolved)}")
        return " | ".join(bits)

    def to_dict(self) -> dict[str, Any]:
        """Sérialisation sûre pour stockage dans conversations.json."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, conversation_id: str = "") -> TaskContext:
        """Désérialisation sûre depuis un dictionnaire."""
        if not data or not isinstance(data, dict):
            return cls(conversation_id=conversation_id)
        return cls(
            conversation_id=data.get("conversation_id") or conversation_id,
            initial_objective=str(data.get("initial_objective") or ""),
            current_status=str(data.get("current_status") or "idle"),
            last_skill=str(data.get("last_skill") or ""),
            last_agent=str(data.get("last_agent") or ""),
            last_intent=str(data.get("last_intent") or ""),
            files=list(data.get("files") or []),
            sources=list(data.get("sources") or []),
            extracted_data=dict(data.get("extracted_data") or {}),
            entities=dict(data.get("entities") or {}),
            decisions=list(data.get("decisions") or []),
            constraints=list(data.get("constraints") or []),
            artifacts=list(data.get("artifacts") or []),
            tools_used=list(data.get("tools_used") or []),
            modifications=list(data.get("modifications") or []),
            tests_executed=list(data.get("tests_executed") or []),
            errors=list(data.get("errors") or []),
            turns=list(data.get("turns") or []),
            intermediate_results=list(data.get("intermediate_results") or []),
            pending_items=list(data.get("pending_items") or []),
            searched_document=str(data.get("searched_document") or ""),
            primary_source_url=str(data.get("primary_source_url") or ""),
            downloaded_file=str(data.get("downloaded_file") or ""),
            artifact_type=str(data.get("artifact_type") or ""),
            artifact_path=str(data.get("artifact_path") or ""),
            verification_results=list(data.get("verification_results") or []),
            created_at=str(data.get("created_at") or datetime.now(timezone.utc).isoformat()),
            updated_at=str(data.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        )

    @classmethod
    def from_conversation(cls, conv: dict[str, Any]) -> TaskContext:
        """Construit ou restaure le TaskContext à partir d'une conversation."""
        cid = str(conv.get("id") or "")
        existing = conv.get("task_context")
        if isinstance(existing, dict):
            tc = cls.from_dict(existing, conversation_id=cid)
            if not tc.initial_objective:
                msgs = conv.get("messages") or []
                for m in msgs:
                    if m.get("role") == "user" and m.get("content"):
                        tc.initial_objective = m["content"].strip()
                        break
            return tc

        tc = cls(conversation_id=cid)
        msgs = conv.get("messages") or []
        for m in msgs:
            role = m.get("role")
            if role == "user" and not tc.initial_objective:
                tc.initial_objective = str(m.get("content") or "").strip()
            elif role == "assistant":
                if m.get("skill"):
                    tc.last_skill = str(m["skill"])
                if m.get("agent"):
                    tc.last_agent = str(m["agent"])
                if m.get("intent"):
                    tc.last_intent = str(m["intent"])
                if m.get("status"):
                    tc.current_status = str(m["status"])
                for s in (m.get("sources") or []):
                    if isinstance(s, dict) and s.get("url"):
                        tc.record_sources([s])
                for fmod in (m.get("files_modified") or []):
                    p = fmod.get("path") if isinstance(fmod, dict) else str(fmod)
                    if p:
                        tc.record_file(p)
                for part in (m.get("preview_artifacts") or []):
                    p = part.get("path") if isinstance(part, dict) else str(part)
                    if p:
                        tc.record_artifact(p, part.get("type", "") if isinstance(part, dict) else "")
                for err in (m.get("compilation_errors") or []):
                    tc.record_error(err.get("error", "") if isinstance(err, dict) else str(err))

        conv["task_context"] = tc.to_dict()
        return tc


class TaskContinuityManager:
    """Gestionnaire centralisé pour la continuité et l'isolation des tâches entre conversations."""

    def __init__(self) -> None:
        self._contexts: dict[str, TaskContext] = {}

    def get_or_create_context(
        self,
        conversation_id: str,
        task_id: str = "",
        user_prompt: str = "",
        title: str = "",
    ) -> TaskContext:
        if conversation_id not in self._contexts:
            ctx = TaskContext(
                conversation_id=conversation_id,
                task_id=task_id,
                title=title,
                initial_objective=user_prompt.strip() if user_prompt else "",
            )
            self._contexts[conversation_id] = ctx
        return self._contexts[conversation_id]

    def resolve_active_task(self, conversation_id: str, new_prompt: str = "") -> TaskContext:
        return self.get_or_create_context(conversation_id)

    def clear(self, conversation_id: str | None = None) -> None:
        if conversation_id:
            self._contexts.pop(conversation_id, None)
        else:
            self._contexts.clear()