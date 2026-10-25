# RÔLE DE CE FICHIER :
# Définit les événements techniques du runtime et leur traduction concise en français.
# AgentLoop les émet; les interfaces terminal ou visuelles peuvent s'y abonner.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class HarnessEvent:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class EventTranslator:
    """Traduit les noms d'événements sans exposer les détails internes du provider."""

    TOOL_MESSAGES = {
        "read_file": "Lecture du fichier…",
        "read_document": "Lecture du document…",
        "list_files": "Inventaire des fichiers…",
        "find_file": "Recherche du fichier…",
        "search_files": "Recherche dans les fichiers…",
        "write_file": "Écriture du fichier (soumise aux permissions)…",
        "patch_file": "Modification du fichier (soumise aux permissions)…",
        "run_tests": "Exécution des tests…",
        "run_python": "Exécution du script (soumise aux permissions)…",
        "git_status": "Lecture de l’état Git…",
        "delegate_to_agent": "Délégation à un autre agent…",
    }

    @classmethod
    def translate(cls, event: HarnessEvent) -> str:
        data = event.data
        name = event.name
        if name == "mode.changed":
            return (
                f"Mode du Harness changé : {data.get('previous', '?')} "
                f"→ {data.get('current', '?')}."
            )
        if name == "agent.started":
            return f"L’agent {data.get('agent', 'actif')} commence la mission."
        if name == "agent.thinking":
            return f"L’agent {data.get('agent', 'actif')} analyse l’étape suivante."
        if name == "provider.started":
            return f"Appel du modèle {data.get('model', 'sélectionné')}…"
        if name == "provider.error":
            cause = data.get("category")
            if cause == "quota":
                return "Le quota ou la limite de débit du fournisseur a été atteint."
            if cause == "network":
                return "Le fournisseur n’est pas joignable pour le moment."
            return "Le modèle n’a pas pu répondre."
        if name == "tool.started":
            return cls.TOOL_MESSAGES.get(str(data.get("tool", "")), "Exécution d’un outil…")
        if name == "tool.completed":
            return "L’outil a terminé : " + str(data.get("status", "résultat reçu")) + "."
        if name == "delegation.started":
            return f"Délégation à {data.get('agent', 'un agent spécialisé')}…"
        if name == "delegation.completed":
            return f"Résultat reçu de {data.get('agent', 'l’agent délégué')}."
        if name == "verification.started":
            return "Vérification des éléments observables…"
        if name == "verification.completed":
            return "Vérification : " + str(data.get("status", "résultat reçu")) + "."
        if name == "delivery.started":
            return "Préparation de la réponse…"
        if name == "delivery.completed":
            return "La réponse a été remise."
        if name == "delivery.failed":
            return "La livraison complète n’a pas pu être vérifiée."
        if name == "skill.loaded":
            return f"Skill {data.get('skill', 'chargé')} chargé."
        if name == "plan.created":
            steps = data.get("plan_steps") or data.get("steps") or []
            return f"Plan d'action créé ({len(steps)} étapes)."
        if name == "plan.step_started":
            return f"Étape {data.get('step_index', '')} en cours : {data.get('description', '')}"
        if name == "plan.step_completed":
            return f"Étape {data.get('step_index', '')} terminée ({data.get('status', 'validée')})."
        if name == "compile.attempt":
            return f"Compilation {data.get('attempt', 1)}/{data.get('max_attempts', 25)}…"
        if name == "compile.error":
            return f"Erreur de compilation ligne {data.get('line', '?')} : {data.get('message', '')}."
        if name == "compile.fixed":
            return f"Correction appliquée : {data.get('note', data.get('action', 'modifié'))}."
        if name == "compile.completed":
            return "Compilation réussie sans aucune erreur."
        if name in {"compile.rollback", "rollback"}:
            return f"Rollback vers checkpoint : {data.get('reason', 'reprise')}"
        if name == "search.query":
            return f"Recherche web : {data.get('query', '')}"
        if name == "search.candidate_rejected":
            return f"Candidat rejeté : {data.get('reason', '')}"
        if name == "download.verified":
            return f"Téléchargement vérifié sur disque : {data.get('destination', '')}"
        if name == "budget.update":
            return f"Budget actualisé : {data.get('tokens_used', 0)} tokens utilisés."
        if name == "provider.failover":
            return f"Repli fournisseur vers {data.get('to_provider', 'modèle alternatif')}."
        if name == "checkpoint.created":
            return f"Point de reprise shadow git créé."
        if name == "critic.started":
            return "Revue critique TDD en cours…"
        if name == "critic.verdict":
            return f"Verdict critique : {'Approuvé' if data.get('approved') else 'Refusé'}."
        if name == "task.stopped":
            return "Mission arrêtée à la demande de l'utilisateur."
        if name == "dag.started":
            return f"Graphe multi-agents (DAG) démarré ({data.get('total_nodes', '?')} étapes)."
        if name == "dag.node_started":
            return f"Sous-tâche DAG lancée : [{data.get('agent', '')}] {data.get('title', '')}"
        if name == "dag.node_completed":
            return f"Sous-tâche DAG terminée : [{data.get('agent', '')}] {data.get('status', '')}"
        if name == "dag.completed":
            return f"Graphe multi-agents (DAG) achevé ({data.get('status', 'terminé')})."
        return name
