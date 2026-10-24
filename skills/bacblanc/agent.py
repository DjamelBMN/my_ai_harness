# RÔLE DE CE FICHIER : agent métier BacBlanc, chargé par SkillLoader et exécuté
# par l'AgentLoop; il produit, fait relire et contrôle la complétude du livrable.

from __future__ import annotations

import hashlib
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from core.agent import Agent
from core.task import Task


class BacBlancAgent(Agent):
    """
    Agent spécialisé du Skill BacBlanc.

    Responsabilités :
    - concevoir des sujets de bac blanc ;
    - produire corrigés et barèmes ;
    - respecter les templates du Skill ;
    - exploiter les ressources du RAG ;
    - contrôler la cohérence mathématique ;
    - déléguer les vérifications aux agents génériques lorsque nécessaire.

    Le Skill fournit :
        skill.md       -> instructions générales
        rules.md       -> règles pédagogiques et éditoriales
        config.yaml    -> configuration
        rag/           -> ressources de référence
        templates/     -> gabarits de production
    """

    description = (
        "Conçoit des sujets de bac blanc, corrigés et barèmes "
        "de mathématiques en respectant les règles, ressources "
        "et templates du Skill BacBlanc."
    )

    capabilities = (
        "exam_creation",
        "bac_blanc",
        "mathematics",
        "grading",
        "correction",
        "latex",
        "pdf",
        "document_generation",
        "template_based_generation",
        "rag_usage",
    )

    supported_intents = (
        "exam_creation",
        "writing",
        "file_analysis",
    )

    def __init__(self) -> None:
        super().__init__(
            name="BacBlancAgent",
            role=(
                "concepteur spécialisé de sujets de bac blanc "
                "de mathématiques, corrigés et barèmes"
            ),
            routing_key="bacblanc",
        )

        # Injectés par SkillLoader.
        self.skill_instructions: str = ""
        self.skill_rules: str = ""

        # Ressources RAG effectivement chargées.
        self.skill_rag_resources: list = []

        # Templates déclarés par le Skill.
        self.skill_templates: list[str] = []

        # Templates réellement présents sur le disque.
        self.skill_available_templates: list = []

        # Contenus réellement extraits par SkillLoader; les noms seuls ne sont
        # jamais considérés comme une lecture du template ou du RAG.
        self.skill_template_contents: dict[str, str] = {}
        self.skill_rag_contents: dict[str, str] = {}
        self.skill_resource_errors: dict[str, str] = {}

        # Chemin du manifeste du Skill.
        self.skill_source_path: str = ""

    # ------------------------------------------------------------------
    # UTILITAIRES
    # ------------------------------------------------------------------

    def _template_names(self) -> list[str]:
        """
        Retourne uniquement les noms des templates disponibles.
        """
        result = []

        for template in getattr(self, "skill_available_templates", []):
            result.append(str(template))

        return result

    def _rag_names(self) -> list[str]:
        """
        Retourne uniquement les noms des ressources RAG disponibles.
        """
        result = []

        for resource in getattr(self, "skill_rag_resources", []):
            result.append(str(resource))

        return result

    # ------------------------------------------------------------------
    # CONSTRUCTION DU PROMPT
    # ------------------------------------------------------------------

    def build_prompt(self, task: Task) -> str:
        parts: list[str] = []

        # --------------------------------------------------------------
        # PROMPT DE BASE DE L'AGENT
        # --------------------------------------------------------------

        parts.append(super().build_prompt(task))

        # --------------------------------------------------------------
        # PROVENANCE DU SKILL
        # --------------------------------------------------------------

        if self.skill_source_path:
            parts.append(
                "=== SOURCE DU SKILL ===\n"
                f"{self.skill_source_path}"
            )

        # --------------------------------------------------------------
        # INSTRUCTIONS DU SKILL
        # --------------------------------------------------------------

        if self.skill_instructions:
            parts.append(
                "=== INSTRUCTIONS DU SKILL ===\n"
                + self.skill_instructions
            )

        # --------------------------------------------------------------
        # RÈGLES DU SKILL
        # --------------------------------------------------------------

        if self.skill_rules:
            parts.append(
                "=== RÈGLES DU SKILL ===\n"
                + self.skill_rules
            )

        # --------------------------------------------------------------
        # RAG
        # --------------------------------------------------------------

        rag_names = self._rag_names()

        if rag_names:
            rag_section = (
                "=== RAG DU SKILL ===\n"
                "Les ressources suivantes sont réellement disponibles :\n"
                + "\n".join(f"- {name}" for name in rag_names)
                + "\n\n"
                "Ces ressources peuvent être consultées avec les outils "
                "appropriés lorsque leur contenu est nécessaire."
            )
        else:
            rag_section = (
                "=== RAG DU SKILL ===\n"
                "Aucune ressource RAG locale n'est actuellement disponible."
            )

        parts.append(rag_section)

        # --------------------------------------------------------------
        # TEMPLATES
        # --------------------------------------------------------------

        declared_templates = [
            str(x)
            for x in getattr(self, "skill_templates", [])
        ]

        available_templates = self._template_names()

        template_section = (
            "=== TEMPLATES DU SKILL ===\n"
            "Templates déclarés :\n"
            + (
                "\n".join(
                    f"- {template}"
                    for template in declared_templates
                )
                if declared_templates
                else "- Aucun template déclaré."
            )
            + "\n\n"
            "Templates réellement présents :\n"
            + (
                "\n".join(
                    f"- {template}"
                    for template in available_templates
                )
                if available_templates
                else "- Aucun template réellement présent."
            )
        )

        parts.append(template_section)

        for relative_path, content in self.skill_template_contents.items():
            parts.append(
                f"=== CONTENU DU GABARIT EFFECTIVEMENT LU : {relative_path} ===\n"
                f"```latex\n{content}\n```"
            )

        for relative_path, content in self.skill_rag_contents.items():
            parts.append(
                f"=== EXTRAIT RAG EFFECTIVEMENT LU : {relative_path} ===\n{content}"
            )

        if self.skill_resource_errors:
            parts.append(
                "=== RESSOURCES NON LUES ===\n"
                + "\n".join(
                    f"- {path}: {error}"
                    for path, error in sorted(self.skill_resource_errors.items())
                )
                + "\nNe cite ni n'utilise ces ressources comme si elles avaient été lues."
            )

        # --------------------------------------------------------------
        # IDENTITÉ ET COMPORTEMENT DE L'AGENT
        # --------------------------------------------------------------

        parts.append(
            """
=== IDENTITÉ DU BACBLANCAGENT ===

Tu es BacBlancAgent.

Tu es l'agent spécialisé du Skill BacBlanc.

Ta mission n'est pas simplement de répondre à une question sur les
mathématiques.

Ta mission est de concevoir et produire des documents d'évaluation
de mathématiques de qualité professionnelle en respectant strictement
les règles du Skill et les templates fournis.

Tu travailles comme un concepteur d'épreuves de mathématiques.

Tu peux utiliser les agents génériques disponibles comme collaborateurs
pour contrôler ton travail.
"""
        )

        # --------------------------------------------------------------
        # PRIORITÉ DES SOURCES
        # --------------------------------------------------------------

        parts.append(
            """
=== ORDRE DE PRIORITÉ ===

Lorsque plusieurs informations sont disponibles, respecte cet ordre :

1. Instructions du Skill
2. Règles du Skill
3. Templates du Skill
4. Ressources RAG du Skill
5. Demande explicite de l'utilisateur
6. Connaissances générales du modèle

Toutefois, une contrainte explicite de l'utilisateur concernant le
contenu demandé doit être respectée si elle ne contredit pas une règle
supérieure du Skill.
"""
        )

        # --------------------------------------------------------------
        # RÈGLE FONDAMENTALE DES TEMPLATES
        # --------------------------------------------------------------

        parts.append(
            """
=== RÈGLE FONDAMENTALE : TEMPLATES ===

Les templates du Skill sont des GABARITS DE PRODUCTION.

Ils ne sont PAS de simples exemples.

Lorsqu'un template correspondant au livrable demandé existe, tu dois
t'en servir comme structure de sortie.

Tu dois conserver autant que possible :

- la structure générale ;
- l'ordre des sections ;
- les titres ;
- les niveaux de titres ;
- la présentation des exercices ;
- les parties A/B ;
- la présentation du barème ;
- les tableaux ;
- les conventions typographiques ;
- les conventions LaTeX ;
- les en-têtes ;
- les pieds de page ;
- les éléments récurrents ;
- les espaces réservés ;
- la logique de mise en page.

Tu peux remplacer le CONTENU pédagogique du template.

Tu ne dois pas remplacer arbitrairement sa STRUCTURE.

Le template constitue la structure de référence.

Si le template demande quatre exercices, tu ne dois pas produire
spontanément trois ou cinq exercices.

Si le template contient une structure de barème particulière,
tu dois la conserver.

Si le template est un fichier LaTeX, produis le document dans cette
structure LaTeX.

Si le template contient des placeholders, remplace-les par le contenu
approprié.

Ne détruis pas les commandes LaTeX structurelles existantes simplement
parce qu'une autre mise en forme te paraît plus élégante.
"""
        )

        # --------------------------------------------------------------
        # INTERDICTION DE PRÉTENDRE AVOIR UTILISÉ UN TEMPLATE
        # --------------------------------------------------------------

        parts.append(
            """
=== TRAÇABILITÉ DES TEMPLATES ===

Tu ne dois jamais dire :

- « j'ai utilisé le template »
- « le template impose ceci »
- « le RAG indique cela »

sans avoir effectivement observé la ressource correspondante.

La simple présence d'un nom de fichier dans la configuration ne signifie
pas que son contenu a été lu.

Si tu n'as pas pu lire le contenu du template, indique que son contenu
n'a pas été vérifié.

Si un template est réellement lu, tu peux t'appuyer sur sa structure.
"""
        )

        # --------------------------------------------------------------
        # RAG
        # --------------------------------------------------------------

        parts.append(
            """
=== RÈGLES DU RAG ===

Le RAG sert de base documentaire au Skill.

Lorsque la mission nécessite une information présente dans le RAG :

1. identifier la ressource pertinente ;
2. la lire réellement ;
3. utiliser uniquement ce que son contenu permet d'établir ;
4. ne pas inventer le contenu d'une ressource non consultée.

Le RAG peut notamment contenir :

- programmes officiels ;
- sujets précédents ;
- recommandations pédagogiques ;
- documents institutionnels ;
- exemples de barèmes ;
- documents de référence ;
- conventions de rédaction.

Le RAG ne doit pas être confondu avec le template.

Le template définit principalement la STRUCTURE.

Le RAG fournit principalement des INFORMATIONS DE RÉFÉRENCE.
"""
        )

        # --------------------------------------------------------------
        # CONCEPTION D'UN SUJET
        # --------------------------------------------------------------

        parts.append(
            """
=== CONCEPTION D'UN SUJET ===

Avant de générer un sujet important, détermine :

- niveau ;
- classe ;
- spécialité éventuelle ;
- durée ;
- programme concerné ;
- thèmes ;
- nombre d'exercices ;
- répartition des points ;
- difficultés attendues ;
- compétences évaluées ;
- contraintes de calculatrice ou d'outils ;
- livrables demandés.

Si une information indispensable manque, demande une précision.

Si elle peut raisonnablement être déduite du contexte, utilise le
contexte sans poser inutilement une question.
"""
        )

        # --------------------------------------------------------------
        # COHÉRENCE MATHÉMATIQUE
        # --------------------------------------------------------------

        parts.append(
            """
=== CONTRÔLE MATHÉMATIQUE OBLIGATOIRE ===

Avant de livrer un sujet, vérifie réellement :

- chaque calcul ;
- chaque dérivée ;
- chaque primitive ;
- chaque limite ;
- chaque probabilité ;
- chaque valeur numérique ;
- chaque représentation paramétrique ;
- chaque équation ;
- chaque résultat géométrique ;
- chaque tableau ;
- chaque graphique demandé ;
- la cohérence des hypothèses ;
- la cohérence entre les questions ;
- la cohérence entre le sujet et le corrigé.

Toutes les questions doivent être mathématiquement solvables.

Le corrigé doit répondre exactement aux questions posées.

Ne modifie jamais rétroactivement l'énoncé uniquement pour cacher
une erreur découverte dans le corrigé.

Si une incohérence apparaît pendant la conception, corrige la conception
et recontrôle ensuite l'ensemble du problème.
"""
        )

        # --------------------------------------------------------------
        # BARÈME
        # --------------------------------------------------------------

        parts.append(
            """
=== BARÈME ===

Le barème doit être cohérent avec le sujet.

Vérifie :

- le nombre de points attribués à chaque question ;
- le nombre de points attribués à chaque exercice ;
- le total général ;
- la cohérence entre difficulté et pondération ;
- la présence éventuelle de points de méthode ;
- les tolérances prévues par les règles du Skill.

Si le template prévoit une structure précise du barème, respecte-la.
"""
        )

        # --------------------------------------------------------------
        # CORRIGÉ
        # --------------------------------------------------------------

        parts.append(
            """
=== CORRIGÉ ===

Le corrigé doit être exploitable par un enseignant.

Il doit :

- répondre à toutes les questions ;
- montrer les étapes nécessaires ;
- utiliser une rédaction mathématique correcte ;
- donner les résultats exacts lorsque cela est pertinent ;
- donner les valeurs approchées lorsque nécessaire ;
- respecter les notations du sujet ;
- rester cohérent avec le barème.

Ne produis jamais un corrigé qui introduit une méthode ou une donnée
absente du sujet sans justification.
"""
        )

        # --------------------------------------------------------------
        # DÉLÉGATION
        # --------------------------------------------------------------

        parts.append(
            """
=== DÉLÉGATION AUX AUTRES AGENTS ===

Tu peux déléguer certaines tâches aux agents génériques.

ReviewAgent peut contrôler :
- la structure ;
- la cohérence pédagogique ;
- le respect du template ;
- la cohérence globale.

TestAgent peut contrôler :
- les calculs ;
- les résultats ;
- les scripts éventuels ;
- les tests automatisables.

CoderAgent peut intervenir lorsqu'une génération nécessite du code.

ResearchAgent peut intervenir lorsque des recherches documentaires
sont nécessaires et que les outils disponibles le permettent.

La délégation ne remplace jamais ton rôle de responsable final.

Tu dois intégrer les retours pertinents avant de produire le livrable.
"""
        )

        # --------------------------------------------------------------
        # FORMAT DE SORTIE
        # --------------------------------------------------------------

        parts.append(
            """
=== FORMAT DE SORTIE ===

Adapte le livrable à la demande.

Si l'utilisateur demande un sujet :
→ produire le sujet.

Si l'utilisateur demande un corrigé :
→ produire le corrigé.

Si l'utilisateur demande un barème :
→ produire le barème.

Si l'utilisateur demande un sujet + corrigé + barème :
→ produire les trois.

Si un template LaTeX correspondant existe :
→ partir de ce template.

Si un fichier doit être créé dans le workspace :
→ utiliser les outils de fichiers prévus par le runtime.

Ne te contente pas de décrire ce que l'utilisateur pourrait faire.

Réalise la tâche lorsque les informations nécessaires sont disponibles.
"""
        )

        # --------------------------------------------------------------
        # INTERDICTION DE FABRICATION
        # --------------------------------------------------------------

        parts.append(
            """
=== INTERDICTIONS ===

Ne prétends jamais :

- avoir exécuté un programme qui ne l'a pas été ;
- avoir consulté un document qui ne l'a pas été ;
- avoir utilisé un template qui n'a pas été lu ;
- avoir vérifié un calcul qui ne l'a pas été ;
- avoir consulté Internet sans outil de recherche ;
- avoir utilisé une ressource RAG sans preuve observable.

Ne fabrique aucune preuve de vérification.
"""
        )

        # --------------------------------------------------------------
        # INSTRUCTION FINALE
        # --------------------------------------------------------------

        parts.append(
            """
=== INSTRUCTION FINALE ===

Tu es BacBlancAgent.

Tu dois produire un travail de niveau enseignant de mathématiques.

Le contenu doit être original lorsque l'utilisateur demande un nouveau
sujet.

La STRUCTURE doit respecter le template du Skill lorsqu'il existe.

Les INFORMATIONS DE RÉFÉRENCE doivent provenir des ressources réellement
consultées.

Les RÈGLES doivent provenir du Skill.

Les CONTRÔLES doivent être réellement effectués.

Tu es responsable de la cohérence finale du livrable.
"""
        )

        parts.append(
            """
=== PROTOCOLE PRIORITAIRE : LIVRABLE BAC BLANC COMPLET ===

Cette règle remplace toute instruction précédente qui aurait demandé seulement
un sujet, seulement un corrigé ou une réponse courte. Pour toute demande de
création de sujet / bac blanc, le livrable n'est complet que s'il contient :

1. le sujet entièrement rédigé avec exactement les quatre exercices du gabarit ;
2. toutes les questions et données nécessaires ;
3. un barème détaillé, chaque exercice et chaque question étant pondérés ;
4. un total calculé de 20 points ;
5. le corrigé détaillé de toutes les questions des quatre exercices ;
6. une section de vérifications mathématiques ;
7. la relecture de l'intégralité du sujet, du barème et du corrigé par ReviewAgent.

Si niveau, spécialité, durée ou répartition manquent, applique les valeurs du
gabarit et annonce ces hypothèses : Terminale spécialité mathématiques, 4 heures,
quatre exercices pondérés 4 + 5 + 6 + 5 = 20 points. Les thèmes fournis par
l'utilisateur priment pour le contenu des exercices.

Respecte les deux gabarits réellement fournis et lus ci-dessus :
- sujet_bacblanc.tex ;
- bareme_bacblanc.tex (il contient aussi la structure du corrigé).
Remplace tous les placeholders. Ne recopie pas de champs entre crochets non
remplacés et ne réduis pas le nombre de questions pour raccourcir la réponse.

Ordre de travail : analyser les paramètres, planifier les quatre exercices,
rédiger le sujet entier, bâtir le barème, rédiger le corrigé question par
question, contrôler les mathématiques, faire relire le tout par ReviewAgent,
intégrer ses corrections, puis refaire la vérification et livrer.

Quand les outils sont disponibles, crée deux fichiers distincts dans le workspace
avec write_file : bacblanc_sujet.tex et bacblanc_bareme.tex. N'écrase jamais un
fichier existant; choisis un suffixe numérique disponible. Relis réellement les
deux fichiers après écriture. Si l'écriture est refusée ou impossible, fournis
dans la réponse finale les deux sources LaTeX complètes dans des blocs de code
nommés; une simple structure ou un chemin de fichier ne suffit pas.

Après la rédaction complète, délègue au ReviewAgent avec une mission qui demande
explicitement : « Relire l'intégralité du sujet, du barème et du corrigé et
rechercher toute incohérence mathématique, pédagogique ou structurelle. » S'il y
a des fichiers, transmets leurs deux chemins et demande au ReviewAgent de les lire
en entier. Sans fichiers, transmets-lui les deux sources complètes. Il ne produit
pas le sujet à ta place. Intègre tout retour, puis fais relire la version finale
après la dernière modification.

Ne prétends pas qu'un calcul est vérifié sur la seule base de ta rédaction.
Rapporte les contrôles et la relecture réellement effectués. Distingue estimation,
vérification par raisonnement et vérification par outil.

CHECKLIST AVANT LIVRAISON : sujet complet; exercices 1 à 4; toutes les questions;
barème couvrant chaque question; somme égale à 20; corrigé des quatre exercices;
calculs revérifiés; deux templates utilisés; ReviewAgent a relu la version finale.
Si une condition manque, demande une continuation/correction. Si le quota, une
limite du provider ou la limite d'itérations empêche de terminer, restitue le
meilleur résultat déjà produit avec un avertissement explicite que la livraison
complète a échoué et que le contenu peut être incomplet ou non vérifié. Ne le
présente jamais comme complet ou validé.
"""
        )

        return "\n\n".join(parts)

    @staticmethod
    def _fold(text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text.casefold())
        return "".join(character for character in decomposed if not unicodedata.combining(character))

    @classmethod
    def requires_full_deliverable(cls, task: Task) -> bool:
        skill_name = str(getattr(task.skill, "name", "")).strip().casefold()
        if skill_name in {"bacblanc", "bac_blanc"}:
            return bool(task.description.strip())

        request = cls._fold(task.description)
        subject = re.search(r"\b(sujet|bac\s+blanc|epreuve)\b", request)
        creation = re.search(
            r"\b(fais|faire|cree|creer|genere|produis|produire|redige|rediger|"
            r"prepare|preparer|concois|concevoir|construis|composer|compose)\b",
            request,
        )
        return bool(subject and creation)

    @staticmethod
    def _artifact_from_answer(answer: str, filename: str) -> str | None:
        match = re.search(
            re.escape(filename)
            + r"[\s\S]*?```(?:latex|tex)?\s*\r?\n([\s\S]*?)```",
            answer,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    @staticmethod
    def _normalize_question_label(label: str) -> str:
        value = re.sub(r"\\textbf\s*\{([^{}]+)\}", r"\1", label)
        return re.sub(r"\s+", "", value).casefold()

    @classmethod
    def _exercise_questions(cls, subject: str) -> dict[int, list[str]]:
        starts = list(
            re.finditer(
                r"\\exercice(?:\s*\[[^\]]*\])?\s*\{\s*([1-4])\s*\}\s*\{",
                subject,
                re.IGNORECASE,
            )
        )
        questions: dict[int, list[str]] = {}
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(subject)
            exercise = int(start.group(1))
            block = subject[start.end() : end]
            questions[exercise] = [
                cls._normalize_question_label(match.group(1) or "")
                for match in re.finditer(r"\\item(?![A-Za-z])\s*(?:\[([^\]]*)\])?", block)
            ]
        return questions

    @classmethod
    def _check_template_artifact(
        cls,
        *,
        subject: str,
        grading: str,
    ) -> list[str]:
        missing: list[str] = []
        placeholder = re.compile(
            r"\[(?:THEME|QUESTION|COMPETENCE|CORRECTION|RAISONNEMENT|ENONCE|"
            r"INTRODUCTION|TITRE|NOM DU LYCEE|ANNEE SCOLAIRE|SESSION|NUMERO|"
            r"DATE|X|MESSAGE|AUTRES CONSIGNES|REGLE|"
            r"\d+(?:[.,]\d+)?\s*points?)\b"
            r"[^\]]*\]",
            re.IGNORECASE,
        )
        subject_fold = cls._fold(subject)
        grading_fold = cls._fold(grading)
        if not all(token in subject_fold for token in (r"\begin{document}", r"\end{document}")):
            missing.append("le fichier sujet LaTeX complet (document/fin manquants)")
        if not all(token in grading_fold for token in (r"\begin{document}", r"\end{document}")):
            missing.append("le fichier barème/corrigé LaTeX complet (document/fin manquants)")
        if placeholder.search(subject_fold) or placeholder.search(grading_fold):
            missing.append("des placeholders de template ne sont pas remplacés")
        for required in (
            r"\documentclass",
            r"\newcommand{\exercice}",
            r"\newcommand{\partie}",
            r"\exercice",
            r"\partie",
            r"]{geometry}",
            r"\thispagestyle{empty}",
            r"\begin{tabularx}",
            r"consigne importante aux surveillants",
            r"consignes aux candidats",
            r"\begin{enumerate}",
            r"\end{enumerate}",
        ):
            if required not in subject_fold:
                missing.append(f"la structure du template sujet a été supprimée ({required})")
                break
        for required in (
            r"\documentclass",
            r"\newcommand{\pts}",
            r"\begin{longtable}",
            r"\end{longtable}",
            r"\begin{tabularx}",
            r"\textbf{total}",
            r"\bottomrule",
            r"regles generales de correction",
        ):
            if required not in grading_fold:
                missing.append(
                    f"la structure du template barème/corrigé a été supprimée ({required})"
                )
                break

        subject_questions = cls._exercise_questions(subject)
        if set(subject_questions) != {1, 2, 3, 4}:
            missing.append("le sujet ne contient pas les quatre exercices du template")
        for exercise in range(1, 5):
            questions = subject_questions.get(exercise, [])
            if not questions:
                missing.append(f"les questions de l'exercice {exercise}")
            if any(not label for label in questions):
                missing.append(f"les questions de l'exercice {exercise} n'ont pas toutes un identifiant")
            if len(set(questions)) != len(questions):
                missing.append(f"les identifiants de questions de l'exercice {exercise} ne sont pas uniques")

        subject_points: dict[int, Decimal] = {}
        for match in re.finditer(
            r"\\exercice\s*\[\s*(\d+(?:[.,]\d+)?)\s*\]\s*\{\s*([1-4])\s*\}",
            subject,
            re.IGNORECASE,
        ):
            try:
                subject_points[int(match.group(2))] = Decimal(match.group(1).replace(",", "."))
            except InvalidOperation:
                continue
        if set(subject_points) != {1, 2, 3, 4}:
            missing.append("les points de chaque exercice dans le sujet")
        if "20 points" not in subject_fold:
            missing.append("le total de 20 points dans le sujet")

        heading_pattern = re.compile(r"\\textbf\{\\large\s+Exercice\s+([1-4])", re.IGNORECASE)
        grading_heads = list(heading_pattern.finditer(grading))
        grading_counts: dict[int, int] = {}
        grading_question_points: dict[int, Decimal] = {}
        for index, heading in enumerate(grading_heads):
            end = grading_heads[index + 1].start() if index + 1 < len(grading_heads) else len(grading)
            exercise = int(heading.group(1))
            exercise_block = grading[heading.end() : end]
            point_rows = re.findall(r"\\pts\s*\{\s*(\d+(?:[.,]\d+)?)\s*\}", exercise_block)
            grading_counts[exercise] = len(point_rows)
            try:
                grading_question_points[exercise] = sum(
                    (Decimal(value.replace(",", ".")) for value in point_rows),
                    Decimal("0"),
                )
            except InvalidOperation:
                missing.append(f"les points-question de l'exercice {exercise} sont invalides")
        if set(grading_counts) != {1, 2, 3, 4}:
            missing.append("les quatre exercices ne figurent pas dans le barème/corrigé")
        for exercise in range(1, 5):
            required_rows = len(subject_questions.get(exercise, []))
            if grading_counts.get(exercise, 0) < required_rows:
                missing.append(
                    f"le barème/corrigé de l'exercice {exercise} ne couvre pas toutes ses questions"
                )

        points: dict[int, Decimal] = {}
        for match in re.finditer(
            r"exercice\s+([1-4])\s*&[^&\n]*&\s*\[?\s*(\d+(?:[.,]\d+)?)\s*\]?\s*(?:points|pts)",
            grading,
            re.IGNORECASE,
        ):
            try:
                points[int(match.group(1))] = Decimal(match.group(2).replace(",", "."))
            except InvalidOperation:
                continue
        if set(points) != {1, 2, 3, 4}:
            missing.append("la répartition chiffrée des quatre exercices dans le tableau du barème")
        elif sum(points.values(), Decimal("0")) != Decimal("20"):
            missing.append("le total du barème n'est pas égal à 20 points")
        elif subject_points and any(subject_points.get(number) != points[number] for number in range(1, 5)):
            missing.append("les points du sujet et du barème ne concordent pas")
        for exercise in range(1, 5):
            if (
                exercise in points
                and exercise in grading_question_points
                and grading_question_points[exercise] != points[exercise]
            ):
                missing.append(
                    f"la somme des points-question de l'exercice {exercise} est incohérente"
                )

        for exercise, labels in subject_questions.items():
            heading = next((item for item in grading_heads if int(item.group(1)) == exercise), None)
            if heading is None:
                continue
            end = next(
                (item.start() for item in grading_heads if item.start() > heading.start()),
                len(grading),
            )
            exercise_block = grading[heading.end() : end]
            for label in (item for item in labels if item):
                label_match = re.search(
                    r"\\textbf\s*\{\s*" + re.escape(label) + r"\s*\}",
                    exercise_block,
                    re.IGNORECASE,
                )
                if label_match is None:
                    missing.append(
                        f"la question {label} de l'exercice {exercise} manque dans le barème/corrigé"
                    )
                    continue
                point_match = re.search(r"\\pts\s*\{", exercise_block[label_match.end() :])
                if point_match is None:
                    missing.append(f"la question {label} n'a pas de points attribués")
                    continue
                correction_text = exercise_block[
                    label_match.end() : label_match.end() + point_match.start()
                ]
                correction_text = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", correction_text)
                correction_text = re.sub(r"[\\&{}$#]+", " ", correction_text)
                correction_text = " ".join(correction_text.split())
                if len(correction_text) < 6:
                    missing.append(f"le corrigé détaillé de la question {label}")
        if not re.search(r"total[^\n]*20\s*(?:points|pts)", grading_fold, re.IGNORECASE):
            missing.append("la ligne TOTAL = 20 points du barème")
        return missing

    def _saved_artifacts(self, state, filesystem) -> dict[str, tuple[str, str]]:
        artifacts: dict[str, tuple[str, str]] = {}
        if state is None or filesystem is None:
            return artifacts
        names = {
            "subject": re.compile(r"^bacblanc_sujet(?:_\d+)?\.tex$", re.IGNORECASE),
            "grading": re.compile(r"^bacblanc_bareme(?:_\d+)?\.tex$", re.IGNORECASE),
        }
        for result in state.tool_results:
            if result.get("tool") != "write_file" or result.get("status") != "success":
                continue
            relative = result.get("data", {}).get("path")
            if not isinstance(relative, str):
                continue
            basename = Path(relative).name
            for kind, pattern in names.items():
                if not pattern.fullmatch(basename):
                    continue
                try:
                    content = filesystem.read_file(relative)
                    expected_hash = result.get("data", {}).get("sha256")
                    actual_hash = hashlib.sha256(filesystem.read_bytes(relative)).hexdigest()
                    if expected_hash and expected_hash != actual_hash:
                        continue
                    artifacts[kind] = (relative, content)
                except (OSError, ValueError, PermissionError):
                    continue
        return artifacts

    @staticmethod
    def _review_result(state, artifact_paths: set[str], inline_artifacts: dict[str, str]) -> bool:
        if state is None:
            return False
        required_terms = ("integralite", "sujet", "bareme", "corrige", "incoherence")
        review_results = [
            result for result in state.delegation_results
            if BacBlancAgent._fold(str(result.get("agent", ""))) == "reviewagent"
        ]
        if not review_results:
            return False
        result = review_results[-1]
        if result.get("status") in {"failed", "incomplete", "blocked"} or not result.get("answer"):
            return False
        review_answer = BacBlancAgent._fold(str(result.get("answer", "")))
        positive_review = any(
            phrase in review_answer
            for phrase in (
                "aucune incoherence",
                "aucune anomalie",
                "aucune erreur",
                "validation finale: pass",
                "validation: pass",
                "ensemble coherent",
            )
        )
        unresolved_review = any(
            phrase in review_answer
            for phrase in (
                "incoherence restante",
                "reste a corriger",
                "correction requise",
                "non valide",
                "a corriger",
            )
        )
        if not positive_review or unresolved_review or not any(
            term in review_answer for term in ("mathematique", "calcul")
        ):
            return False
        task = str(result.get("task", ""))
        folded_task = BacBlancAgent._fold(task)
        if not all(term in folded_task for term in required_terms):
            return False
        if artifact_paths:
            if not all(path in task for path in artifact_paths):
                return False
            read_paths = {
                str(tool.get("data", {}).get("path", ""))
                for tool in result.get("tool_results", [])
                if tool.get("tool") in {"read_file", "read_document"}
                and tool.get("status") == "success"
            }
            if not artifact_paths.issubset(read_paths):
                return False
            last_write = max(
                (
                    index for index, tool in enumerate(state.tool_results)
                    if tool.get("tool") == "write_file"
                    and tool.get("status") == "success"
                    and tool.get("data", {}).get("path") in artifact_paths
                ),
                default=-1,
            )
            last_review = max(
                (
                    index for index, tool in enumerate(state.tool_results)
                    if tool.get("tool") == "delegate_to_agent"
                    and BacBlancAgent._fold(str(tool.get("data", {}).get("agent", ""))) == "reviewagent"
                    and tool.get("status") == "success"
                ),
                default=-1,
            )
            if last_review <= last_write:
                return False
        else:
            if not all(content and content in task for content in inline_artifacts.values()):
                return False
        return True

    def validate_final_answer(self, answer: str, task: Task, state=None, filesystem=None) -> dict:
        """Bloque la livraison d'un sujet demandé tant que les preuves manquent."""
        if not self.requires_full_deliverable(task):
            return {"required": False, "complete": True, "checks": [], "missing": []}

        missing: list[str] = []
        required_templates = {"sujet_bacblanc.tex", "bareme_bacblanc.tex"}
        loaded_templates = {
            Path(path).name
            for path, content in self.skill_template_contents.items()
            if content.strip()
        }
        if not required_templates.issubset(loaded_templates):
            for filename in sorted(required_templates - loaded_templates):
                missing.append(f"le contenu réellement lu du template {filename}")

        saved = self._saved_artifacts(state, filesystem)
        inline = {
            "subject": self._artifact_from_answer(answer, "bacblanc_sujet.tex"),
            "grading": self._artifact_from_answer(answer, "bacblanc_bareme.tex"),
        }
        saved_complete = {"subject", "grading"}.issubset(saved)
        inline_complete = all(inline.values())
        artifact_paths = (
            {saved["subject"][0], saved["grading"][0]}
            if saved_complete
            else set()
        )
        if saved_complete:
            subject, grading = saved["subject"][1], saved["grading"][1]
        elif inline_complete:
            subject, grading = inline["subject"], inline["grading"]
        else:
            subject = grading = ""
        if not subject:
            missing.append("le sujet complet (bacblanc_sujet.tex)")
        if not grading:
            missing.append("le barème et corrigé complet (bacblanc_bareme.tex)")
        if subject and grading:
            missing.extend(self._check_template_artifact(subject=subject, grading=grading))

        answer_fold = self._fold(answer)
        verification_heading = re.search(
            r"(?:^|\n)\s*(?:#{1,6}\s*)?verification(?:s)? mathematique",
            answer_fold,
        )
        if not verification_heading:
            missing.append("la section de vérifications mathématiques dans la réponse finale")
        else:
            verification_block = answer_fold[verification_heading.end() :].strip()
            if len(verification_block) < 25 or not any(
                term in verification_block for term in ("calcul", "resultat", "coherence")
            ):
                missing.append("le compte rendu des vérifications mathématiques")

        inline_artifacts = {
            "bacblanc_sujet.tex": inline["subject"] or "",
            "bacblanc_bareme.tex": inline["grading"] or "",
        }
        if not self._review_result(state, artifact_paths, inline_artifacts):
            missing.append(
                "la relecture par ReviewAgent de l'intégralité du sujet, du barème et du corrigé"
            )

        required_names = ("sujet", "bareme", "corrige")
        if not all(name in answer_fold for name in required_names):
            missing.append("le récapitulatif final du sujet, du barème et du corrigé")
        for path in artifact_paths:
            if path not in answer:
                missing.append(f"le chemin du livrable {path} dans la réponse finale")
        if re.search(r"suite du corrige|a suivre|partie suivante plus tard|a completer", answer_fold):
            missing.append("une réponse annoncée comme continuation ou laissée à compléter")

        checks = [
            {"check": "full_exam_artifacts", "status": "passed" if subject and grading else "failed"},
            {"check": "review_agent_full_review", "status": "failed" if any("ReviewAgent" in item for item in missing) else "passed"},
            {"check": "mathematical_verification_report", "status": "failed" if any("mathématiques" in item for item in missing) else "passed"},
        ]
        return {
            "required": True,
            "complete": not missing,
            "checks": checks,
            "missing": sorted(set(missing)),
            "saved_artifact_paths": sorted(artifact_paths),
        }

    @staticmethod
    def completion_repair_prompt(report: dict) -> str:
        missing = "\n".join(f"- {item}" for item in report.get("missing", []))
        return (
            "Le contrôle automatique de complétude a bloqué la livraison. "
            "Continue la mission; ne dis pas que le sujet est terminé et ne livre jamais un fragment. "
            "Complète ou corrige les deux fichiers LaTeX, relis-les, fais vérifier par ReviewAgent "
            "la version intégrale après la dernière modification, puis rends le compte rendu final. "
            "Si les fichiers ne peuvent pas être écrits, la réponse finale doit inclure les deux "
            "sources complètes dans des blocs LaTeX nommés, et ReviewAgent doit recevoir ces deux "
            "sources entières. Ne renvoie pas seulement les sections manquantes. "
            "Éléments manquants :\n" + missing
        )

    @staticmethod
    def incomplete_delivery_message(report: dict) -> str:
        missing = "\n".join(f"- {item}" for item in report.get("missing", []))
        return "Livrable non livré : la vérification de complétude n'est pas passée.\n" + missing

    def partial_delivery_message(
        self,
        *,
        reason: str,
        partial_content: str,
        state=None,
        filesystem=None,
    ) -> str:
        """Formate le meilleur résultat conservé après une interruption explicite."""
        sections = [
            "# LIVRAISON PARTIELLE — ÉCHEC DE LA LIVRAISON COMPLÈTE",
            f"La livraison complète a échoué : {reason}.",
            (
                "Le résultat fourni ci-dessous est le meilleur contenu déjà produit. "
                "Il peut être incomplet ou non vérifié et ne doit pas être considéré "
                "comme un sujet complet validé."
            ),
        ]
        if partial_content.strip():
            sections.extend(
                [
                    "## Contenu déjà produit (partiel)",
                    partial_content.strip(),
                ]
            )

        artifacts = self._saved_artifacts(state, filesystem)
        fence = chr(96) * 3
        for kind, label in (("subject", "Sujet"), ("grading", "Barème et corrigé")):
            saved = artifacts.get(kind)
            if saved is None:
                continue
            path, content = saved
            sections.extend(
                [
                    f"## {label} déjà écrit — complétude non vérifiée",
                    f"Fichier réellement présent et lisible : {path} ({len(content)} caractères).",
                    fence + "latex",
                    content,
                    fence,
                ]
            )

        if not partial_content.strip() and not artifacts:
            sections.append(
                "Aucun fragment de texte ni fichier partiel lisible n'a pu être conservé."
            )
        return "\n\n".join(sections)
