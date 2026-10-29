# RÔLE DE CE FICHIER :
# Compaction sémantique du contexte de session envoyé à l'Agent.
# Préserve immuablement les faits établis, décisions et contraintes.
# Remplace la troncature aveugle par une synthèse structurée des tours anciens.

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.context import Context


class ContextManager:
    """Gestionnaire de contexte avec compaction sémantique et préservation des invariants."""

    def __init__(self, max_items: int = 5, max_characters: int = 6000) -> None:
        self.max_items = max(1, max_items)
        self.max_characters = max(500, max_characters)

    def compact(self, context: Context) -> Context:
        if not context.history:
            return context

        # 1. Préservation immuable des faits, contraintes et décisions
        immutable_facts: list[str] = []
        tc = getattr(context, "task_context", None)
        if tc is not None:
            decisions = getattr(tc, "decisions", [])
            constraints = getattr(tc, "constraints", [])
            if decisions:
                immutable_facts.append(f"[DÉCISIONS VALIDÉES] : {', '.join(str(d) for d in decisions[-5:])}")
            if constraints:
                immutable_facts.append(f"[CONTRAINTES IMMUABLES] : {', '.join(str(c) for c in constraints[-5:])}")

        # 2. Si l'historique dépasse la capacité, synthétiser les tours anciens
        if tc is not None and len(context.history) > self.max_items:
            older_items = context.history[:-self.max_items]
            recent_items = context.history[-self.max_items:]

            # Synthèse extractive des tours anciens (extraction des actions clés et résultats)
            condensed_summary = self._summarize_older_turns(older_items)
            new_history = [condensed_summary, *recent_items]
        else:
            new_history = list(context.history[-self.max_items:])

        # 3. Contrôle du budget de caractères sans découpage sauvage de mots
        total_len = sum(len(x) for x in new_history)
        if total_len > self.max_characters:
            budget = self.max_characters
            pruned: list[str] = []
            for item in reversed(new_history):
                if len(item) <= budget:
                    pruned.append(item)
                    budget -= len(item)
                else:
                    # Tronquer au niveau de la phrase la plus proche
                    cutoff = budget
                    last_period = item[:cutoff].rfind(". ")
                    if last_period > cutoff // 2:
                        pruned.append(item[:last_period + 1] + " [suite condensée]")
                    else:
                        pruned.append(item[:cutoff] + "...")
                    break
            new_history = list(reversed(pruned))

        if immutable_facts and not any("[DÉCISIONS VALIDÉES]" in h for h in new_history):
            new_history.insert(0, " | ".join(immutable_facts))

        context.history = new_history
        return context

    @staticmethod
    def _summarize_older_turns(turns: list[str]) -> str:
        extracted: list[str] = []
        preserved_files: list[str] = []
        preserved_symbols: list[str] = []

        for t in turns:
            lines = t.strip().splitlines()
            first_line = lines[0] if lines else ""
            clean_first = re.sub(r"\s+", " ", first_line).strip()[:150]
            if clean_first:
                extracted.append(clean_first)
            for fm in re.findall(r"\b[a-zA-Z0-9_\-/]+\.(?:py|tex|pdf|docx|html|md|json|csv)\b", t):
                if fm not in preserved_files:
                    preserved_files.append(fm)
            for sym in re.findall(r"\b(?:class|def)\s+([a-zA-Z_][a-zA-Z0-9_]*)", t):
                if sym not in preserved_symbols:
                    preserved_symbols.append(sym)

        summary_body = " -> ".join(extracted[-6:]) if extracted else "Historique antérieur archivé"
        invariants = []
        if preserved_files:
            invariants.append(f"Fichiers cités: {', '.join(preserved_files[:10])}")
        if preserved_symbols:
            invariants.append(f"Symboles: {', '.join(preserved_symbols[:10])}")
        inv_str = f" ({' | '.join(invariants)})" if invariants else ""
        return f"[SYNTHÈSE TOURS ANCIENS ({len(turns)} archivés){inv_str}] : {summary_body}"