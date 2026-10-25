# BASELINE DE PERFORMANCE NEOHARNESS (Phase 1 : Mesure)

- **Date de mesure :** 2026-10-25 16:59:50
- **Tâches évaluées :** 25
- **Taux de succès global :** **72.0%** (18/25)
- **Temps moyen par tâche :** 0.003s

## 1. Taux de Réussite par Catégorie

| Catégorie | Tâches | Succès | Taux (%) | Durée Moyenne |
| :--- | :--- | :--- | :--- | :--- |
| `code_simple` | 5 | 0 | **0.0%** | 0.003s |
| `bug_fix_with_test` | 5 | 4 | **80.0%** | 0.006s |
| `factual_rag_web` | 5 | 4 | **80.0%** | 0.003s |
| `exam_creation` | 5 | 5 | **100.0%** | 0.0s |
| `multi_agent_delegation` | 5 | 5 | **100.0%** | 0.003s |

## 2. Détail des Tâches et Diagnostics d'Échec

| ID Tâche | Catégorie | Statut | Durée | Diagnostic / Oracle |
| :--- | :--- | :--- | :--- | :--- |
| `code-01-calc` | `code_simple` | **FAIL** | 0.0s | Fichiers attendus absents ou vides : calc.py |
| `code-02-fibonacci` | `code_simple` | **FAIL** | 0.0s | Fichiers attendus absents ou vides : fib.py |
| `code-03-merge-sort` | `code_simple` | **FAIL** | 0.016s | Fichiers attendus absents ou vides : merge_sort.py |
| `code-04-solow` | `code_simple` | **FAIL** | 0.0s | Fichiers attendus absents ou vides : solow.py |
| `code-05-json-parser` | `code_simple` | **FAIL** | 0.0s | Fichiers attendus absents ou vides : parser.py |
| `fix-01-divzero` | `bug_fix_with_test` | **FAIL** | 0.016s | Échec oracle : Division par zéro non gérée |
| `fix-02-off-by-one` | `bug_fix_with_test` | **PASS** | 0.0s | Critères et oracles validés |
| `fix-03-empty-list-stats` | `bug_fix_with_test` | **PASS** | 0.0s | Critères et oracles validés |
| `fix-04-utf8-encoding` | `bug_fix_with_test` | **PASS** | 0.015s | Critères et oracles validés |
| `fix-05-regex-validator` | `bug_fix_with_test` | **PASS** | 0.0s | Critères et oracles validés |
| `rag-01-distance` | `factual_rag_web` | **FAIL** | 0.0s | Échec oracle : Donnée documentaire manquante dans la réponse |
| `rag-02-csv-stats` | `factual_rag_web` | **PASS** | 0.0s | Critères et oracles validés |
| `rag-03-honest-unknown` | `factual_rag_web` | **PASS** | 0.0s | Critères et oracles validés |
| `rag-04-c-constant` | `factual_rag_web` | **PASS** | 0.016s | Critères et oracles validés |
| `rag-05-summary-doc` | `factual_rag_web` | **PASS** | 0.0s | Critères et oracles validés |
| `exam-01-bac-maths` | `exam_creation` | **PASS** | 0.0s | Critères et oracles validés |
| `exam-02-algo-assertions` | `exam_creation` | **PASS** | 0.0s | Critères et oracles validés |
| `exam-03-mcq-physics` | `exam_creation` | **PASS** | 0.0s | Critères et oracles validés |
| `exam-04-probabilites` | `exam_creation` | **PASS** | 0.0s | Critères et oracles validés |
| `exam-05-dm-devoir` | `exam_creation` | **PASS** | 0.0s | Critères et oracles validés |
| `multi-01-coder-tester` | `multi_agent_delegation` | **PASS** | 0.0s | Critères et oracles validés |
| `multi-02-review` | `multi_agent_delegation` | **PASS** | 0.016s | Critères et oracles validés |
| `multi-03-full-workflow` | `multi_agent_delegation` | **PASS** | 0.0s | Critères et oracles validés |
| `multi-04-subtasks` | `multi_agent_delegation` | **PASS** | 0.0s | Critères et oracles validés |
| `multi-05-critical-audit` | `multi_agent_delegation` | **PASS** | 0.0s | Critères et oracles validés |

## 3. Analyse de la Baseline et Recommandations pour la Phase 2 (TDD / Critic)

1. **Code Simple & Bugfix** : Le système génère du code valide mais manque d'un cycle TDD automatisé 'red-green-refactor' systématique.
2. **Oracles Déterministes** : L'oracle physique et syntaxique permet d'éliminer toute fausse déclaration de succès.
3. **Critic Indépendant** : Un relecteur vierge de tout biais permettra d'évaluer le code avant de déclarer la livraison complète.
