# RÔLE DE CE FICHIER :
# Limite le contexte de session envoyé à l'Agent. La mémoire de tâche reste dans
# TaskState; la mémoire longue durée est désactivée et n'est jamais écrite ici.

from __future__ import annotations

from core.context import Context


class ContextManager:
    def __init__(self, max_items: int = 5, max_characters: int = 6000) -> None:
        self.max_items = max(1, max_items)
        self.max_characters = max(500, max_characters)

    def compact(self, context: Context) -> Context:
        selected = context.history[-self.max_items :]
        total = 0
        compacted = []
        for entry in reversed(selected):
            remaining = self.max_characters - total
            if remaining <= 0:
                break
            value = entry[-remaining:]
            compacted.append(value)
            total += len(value)
        context.history = list(reversed(compacted))
        return context

