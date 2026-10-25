# GUIDE D'ÉVALUATION DÉTERMINISTE : NEOHARNESS AI

## 1. Philosophie d'Évaluation

Le système d'évaluation de NeoHarness repose sur des tâches reproductibles et déterministes, garantissant qu'aucune régression fonctionnelle ou sécuritaire ne puisse être introduite sans être détectée par le banc de test.

---

## 2. Lancement Rapide (Moins de 2 minutes)

Pour exécuter l'ensemble des 25 tâches de benchmark avec l'oracle déterministe :

```bash
python -m evals.runner
```

Le script produit deux livrables :
1. `evals/results.json` : Données brutes structurées (statut, durée, nombre d'appels d'outils, tokens).
2. `evals/BASELINE.md` : Rapport lisible avec tableau par catégorie et diagnostic d'oracle.

---

## 3. Structure des 25 Tâches Déterministes

Les tâches sont réparties en 5 catégories distinctes définies dans [`evals/tasks.py`](file:///c:/Users/nanod/Desktop/my_ai_harness/evals/tasks.py) :

1. **`code_simple` (5 tâches) :**
   - Calculatrice modulaire (`code-01-calc`)
   - Algorithme Fibonacci optimisé (`code-02-fibonacci`)
   - Tri fusion déterministe (`code-03-merge-sort`)
   - Modèle économique de Solow (`code-04-solow`)
   - Analyseur JSON sans dépendance (`code-05-json-parser`)

2. **`bug_fix_with_test` (5 tâches) :**
   - Correction division par zéro (`fix-01-divzero`)
   - Résolution KeyError dans dictionnaire (`fix-02-keyerror`)
   - Hors limite d'index dans parsing (`fix-03-indexerror`)
   - Détection de récursion infinie (`fix-04-recursion`)
   - Correction de fuite de mémoire cache (`fix-05-memoryleak`)

3. **`factual_rag_web` (5 tâches) :**
   - Extraction de dates et faits vérifiables avec traçabilité exacte des sources.

4. **`exam_creation` (5 tâches) :**
   - Génération de sujets, corrigés et barèmes conformes aux programmes officiels.

5. **`multi_agent_delegation` (5 tâches) :**
   - Chaîne complète Manager -> Workers spécialisés -> Critic indépendant.

---

## 4. Rejouer une Mission Spécifique

Chaque exécution enregistre son identifiant unique `run_id` :

```bash
python -m core.replay <run_id>
# Exemple : python -m core.replay 4eccf6fb38404cb9bd785bbb410e9d11
```
