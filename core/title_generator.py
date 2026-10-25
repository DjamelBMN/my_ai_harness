# RÔLE DE CE FICHIER :
# Génère automatiquement un titre court, naturel et descriptif de 3 à 6 mots
# pour chaque tâche créée dans NeoHarness AI (affiché dans la sidebar).
# Ne montre JAMAIS la requête brute de l'utilisateur ni de slash command.
# Le titre est généré dès la création et reste stable ensuite.

from __future__ import annotations

import re
from typing import Any


def generate_task_title(prompt: str, skill_hint: str = "", llm_provider: Any = None) -> str:
    """Génère un titre court, naturel et descriptif (3 à 6 mots) résumant l'objectif réel de la tâche."""
    raw = (prompt or "").strip()
    if not raw:
        return "Nouvelle tâche"

    # 1. Extraction et suppression de la slash command (/dm, /exercice, /bacblanc, /debug, etc.)
    m_cmd = re.match(r"^/([a-zA-Z0-9_-]+)", raw)
    detected_skill = (m_cmd.group(1).lower() if m_cmd else skill_hint or "").lower()
    text = re.sub(r"^/[a-zA-Z0-9_-]+\s*", "", raw).strip()
    text = text.replace("’", "'")

    # Nettoyage des formules de politesse et verbes introductifs
    fillers = [
        r"^(?:s'il te pla[îi]t|s'il vous pla[îi]t|svp|stp|merci de|veuillez|peux-tu|pouvez-vous)\s+(?:me\s+|m')?",
        r"^(?:j'aimerais que tu|je voudrais que tu|je souhaite que tu|j'aimerais|je voudrais|je veux)\s+(?:me\s+|m')?",
        r"^(?:fais-moi|fais moi|cr[ée]e-moi|cr[ée]e moi|g[ée]n[èe]re-moi|g[ée]n[èe]re moi|g[ée]n[èe]re|donne-moi|donne moi|[ée]cris-moi|[ée]cris moi|[ée]cris|trace-moi|trace moi|trace|dessine-moi|dessine|affiche-moi|affiche)\s+(?:un|une|des|le|la|les|ce|cette)?\s*",
        r"^(?:analyse-moi|analyse moi|analyse|corrige-moi|corrige|v[ée]rifie-moi|v[ée]rifie|r[ée]sous-moi|r[ée]sous|explique-moi|explique|r[ée]dige-moi|r[ée]dige)\s+(?:un|une|des|le|la|les|ce|cette)?\s*",
    ]
    for _ in range(3):
        for f in fillers:
            text = re.sub(f, "", text, flags=re.IGNORECASE).strip()

    # Nettoyage des politesses finales
    text = re.sub(r"\s*(?:s'il te pla[îi]t|s'il vous pla[îi]t|svp|stp|merci)\s*[.?!]*$", "", text, flags=re.IGNORECASE).strip(" .?!;:,")

    # 2. Règles déterministes haute fidélité (instantané 0 ms, aucun appel réseau, stable)
    # A. Bac blanc
    if detected_skill == "bacblanc" or re.search(r"\bbac\s*blanc\b", raw, re.I):
        if re.search(r"physique|chimie", text, re.I):
            return "Bac blanc de physique-chimie"
        elif re.search(r"svt|biologie", text, re.I):
            return "Bac blanc de SVT"
        elif re.search(r"ses|economie|économie", text, re.I):
            return "Bac blanc de SES"
        return "Bac blanc de mathématiques"

    # B. Exercice
    if detected_skill == "exercice" or re.search(r"\bexercice\b", raw, re.I):
        m_topic = re.search(r"(?:sur|de)\s+(?:les\s+|la\s+|le\s+|l'|des\s+)?([a-zA-ZÀ-ÿ0-9_-]+(?:\s+[a-zA-ZÀ-ÿ0-9_-]+){0,2})", text, re.I)
        if m_topic:
            topic = m_topic.group(1).strip().lower()
            topic = re.sub(r"\s+(?:avec|pour|en|terminale|premiere|bac).*$", "", topic)
            if "suite" in topic:
                return "Exercice sur les suites"
            elif "proba" in topic:
                return "Exercice sur les probabilités"
            elif "fonction" in topic:
                return "Exercice sur les fonctions"
            elif "geometrie" in topic or "géométrie" in topic:
                return "Exercice de géométrie"
            elif "integrale" in topic or "intégrale" in topic:
                return "Exercice sur le calcul intégral"
            elif "matrice" in topic:
                return "Exercice sur les matrices"
            words = m_topic.group(1).split()[:2]
            return f"Exercice sur {' '.join(words)}"
        return "Exercice de mathématiques"

    # C. Devoir maison / DM
    if detected_skill == "dm" or re.search(r"\b(?:dm|devoir\s+maison)\b", raw, re.I):
        if re.search(r"optique", text, re.I):
            return "Devoir maison sur l'optique"
        elif re.search(r"mecanique|mécanique", text, re.I):
            return "Devoir maison de mécanique"
        elif re.search(r"physique", text, re.I):
            return "Devoir maison de physique"
        elif re.search(r"chimie", text, re.I):
            return "Devoir maison de chimie"
        m_topic = re.search(r"sur\s+(?:l'|la\s+|le\s+|les\s+)?([a-zA-ZÀ-ÿ0-9_-]+)", text, re.I)
        if m_topic:
            top = m_topic.group(1)
            pref = "l'" if top[0].lower() in "aeiouyéèê" else "les "
            return f"Devoir maison sur {pref}{top}"
        return "Devoir maison de mathématiques"

    # D. Graphique / Tracé Matplotlib / Python
    if re.search(r"\b(?:graphique|courbe|plot|tracer|matplotlib)\b", raw, re.I):
        if re.search(r"fonction\s+carr[ée]e?", raw, re.I) or re.search(r"x\s*\^\s*2|x\s*\*\*\s*2", raw, re.I):
            return "Graphique de la fonction carré"
        elif re.search(r"fonction[s]?\s+de\s+r[ée]f[ée]rence", raw, re.I):
            return "Graphique de fonction de référence"
        elif re.search(r"gauss", raw, re.I):
            return "Graphique de la courbe de Gauss"
        elif re.search(r"sinus|sin\b", raw, re.I):
            return "Graphique de la fonction sinus"
        elif re.search(r"cosinus|cos\b", raw, re.I):
            return "Graphique de la fonction cosinus"
        elif re.search(r"exponentielle|exp\b", raw, re.I):
            return "Graphique de la fonction exponentielle"
        elif re.search(r"logarithme|ln\b", raw, re.I):
            return "Graphique du logarithme népérien"
        elif re.search(r"inverse", raw, re.I):
            return "Graphique de la fonction inverse"
        
        # Nettoyage des compléments d'outil dans l'intitulé
        clean_graph = re.sub(r"\b(?:en\s+python|avec\s+matplotlib|en\s+matplotlib|avec\s+python)\b", "", text, flags=re.I).strip()
        m_fn = re.search(r"(?:de\s+la\s+|du\s+|d'un[e]?\s+)?(fonction\s+(?:de\s+)?[a-zA-ZÀ-ÿ0-9_-]+|courbe\s+(?:de\s+)?[a-zA-ZÀ-ÿ0-9_-]+)", clean_graph, re.I)
        if m_fn:
            fn_title = m_fn.group(1).strip()
            # Éviter les prépositions orphelines en fin
            fn_title = re.sub(r"\s+(?:en|de|du|des|pour|par|avec)$", "", fn_title, flags=re.I)
            return f"Graphique de la {fn_title}"
        return "Graphique de données"

    # E. Correction / Debug
    if detected_skill == "debug" or re.search(r"\b(?:corrige|correction|debug|d[ée]boguer|erreur)\b", raw, re.I):
        m_fn = re.search(r"fonction\s+([a-zA-Z0-9_]+)", text, re.I)
        if m_fn:
            return f"Correction de la fonction {m_fn.group(1)}"
        if re.search(r"latex|tex\b", raw, re.I):
            return "Correction du document LaTeX"
        elif re.search(r"python|script", raw, re.I):
            return "Correction du script Python"
        elif re.search(r"html|css|js\b", raw, re.I):
            return "Correction du code Web"
        return "Correction et débogage"

    # F. Cas spécifiques fréquents
    if re.search(r"seconde\s+guerre\s+mondiale", raw, re.I):
        return "Seconde Guerre mondiale"
    if re.search(r"premi[èe]re\s+guerre\s+mondiale", raw, re.I):
        return "Première Guerre mondiale"
    if re.search(r"calculatrice", raw, re.I):
        return "Calculatrice interactive Web"
    if re.search(r"eleves|donn[ée]es\s+eleves", raw, re.I):
        return "Analyse du fichier élèves"
    if re.search(r"po[èe]me", raw, re.I):
        m_sub = re.search(r"sur\s+(?:l'|la\s+|le\s+|les\s+)?([a-zA-ZÀ-ÿ0-9_-]+)", text, re.I)
        if m_sub:
            sub = m_sub.group(1)
            pref = "l'" if sub[0].lower() in "aeiouyéèê" else "la "
            return f"Poème sur {pref}{sub}"
        return "Poème littéraire"

    # 3. Optionnel : synthèse LLM si demandée pour les cas généraux atypiques
    if llm_provider is not None:
        try:
            p_prompt = (
                "Tu es l'assistant de nommage de tâches de NeoHarness AI.\n"
                "Génère un titre court, naturel et descriptif de 3 à 5 mots en français "
                "résumant l'objectif réel de la demande ci-dessous.\n"
                "Règles strictes :\n"
                "- Pas de slash command (ex: pas de /exercice, /bacblanc, etc.)\n"
                "- Pas de politesse (ex: pas de 'peux-tu', 'fais-moi', 'svp')\n"
                "- Pas de guillemets ni de ponctuation finale\n"
                "- Entre 3 et 5 mots maximum\n\n"
                f"Demande : {text}\n"
                "Titre court :"
            )
            raw_title = str(llm_provider.generate(p_prompt) or "").strip()
            clean_llm = re.sub(r'^["\'«»\s*#]+|["\'«»\s.]+$', "", raw_title).strip()
            clean_llm = re.sub(r"^(?:titre\s*:\s*)", "", clean_llm, flags=re.I).strip()
            words_llm = clean_llm.split()
            if 2 <= len(words_llm) <= 6 and not clean_llm.startswith("/"):
                return clean_llm[0].upper() + clean_llm[1:]
        except Exception:
            pass

    # 4. Règle générale : extraction propre des 3 à 5 mots les plus significatifs
    words = [w for w in text.split() if w]
    stop_ends = {"de", "du", "des", "le", "la", "les", "un", "une", "sur", "et", "ou", "en", "pour", "avec", "dans", "par"}

    if len(words) <= 5:
        selected = words
    else:
        selected = words[:4]

    while selected and selected[-1].lower() in stop_ends:
        selected.pop()

    res = " ".join(selected).strip(" .?!,;:-")
    if res:
        res = res[0].upper() + res[1:]
    return res or "Nouvelle tâche"
