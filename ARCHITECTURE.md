# ARCHITECTURE INDUSTRIELLE DE NEOHARNESS AI

## 1. Vue d'Ensemble des Composants

```
+-------------------------------------------------------------------------------+
|                                 CORE RUNTIME                                  |
|                                                                               |
|  [main.py] ---> [Orchestrator] ---> [Planner] <--- [ReflectiveMemory (FTS5)]  |
|                         |                                                     |
|                         v                                                     |
|                  [AgentLoop] <--------+                                       |
|                    |     |            |                                       |
|      +-------------+     +------+     | (Re-plan / Remédiation)               |
|      v                          v     |                                       |
|  [ToolRegistry]          [TDDEngine]--+                                       |
|      |                          |                                             |
|      +-> edit_file (AST)        +-> [CheckpointManager]                       |
|      +-> view_file (paginé)            (Shadow Git)                           |
|      +-> search_code                   Rollback physique                      |
|      +-> DynamicBrowser (Playwright)                                          |
|      +-> delegate_to_agent                                                    |
|                                                                               |
|  [IndependentCritic] (Contexte vierge, Veto motivé)                          |
+-------------------------------------------------------------------------------+
```

---

## 2. Modules Clés et Responsabilités

### `core/checkpoint.py` (Brique 1 : Backtracking)
- **Rôle :** Snapshot automatique et retour en arrière physique en cas d'impasse.
- **Mécanisme :** Dépôt fantôme `--git-dir=.neoharness/shadow.git --work-tree=<workspace>`. N'impacte JAMAIS le dépôt utilisateur.
- **Rollback :** Restauration stricte par `git reset --hard` et `git clean -fd` combinée à la réinitialisation de `TaskState`.

### `tools/browser.py` (Brique 2 : Navigation Dynamique)
- **Rôle :** Interaction avec le Web moderne et téléchargement certifié.
- **Moteur :** Chromium headless via Playwright avec repli statique transparent (`mode statique dégradé : Playwright indisponible`).
- **Garanties :** Extraction structurée du DOM (IDs stables `e_1`, `e_2`), vérification obligatoire de `robots.txt` et contrôle physique des artefacts (magic bytes).

### `core/memory.py` (Brique 3 : Mémoire Réflexive Cross-Missions)
- **Rôle :** Capitalisation d'expériences sans grossissement incontrôlé.
- **Stockage :** SQLite avec table virtuelle FTS5 (`.neoharness/reflective_memory.sqlite`).
- **Algorithme temporel :** Décroissance exponentielle (`effective_score = score * (decay_rate ** days)`).

### `core/tdd_engine.py` (Brique 4 : TDD Fermé)
- **Rôle :** Boucle contractuelle stricte : Red -> Green -> Refactor.
- **Intégrité :** Calcul et vérification du hash SHA-256 des fichiers de tests. Déclenche `TestTamperingError` à la moindre tentative de modification non autorisée.

### `core/multi_agent_coordinator.py` (Brique 5 : Hiérarchie Multi-Agents)
- **Rôle :** Orchestration Manager / Workers / Critic.
- **Protocole :** Messages typés (`TaskAssignment`, `TaskCompletion`, `CritiqueVerdict`).
- **Sécurité de boucle :** Détection formelle de cycles (`CyclicDelegationError`) et plafond de profondeur (`max_depth = 3`).

---

## 3. Observabilité et Replay

Chaque cycle émet des événements `HarnessEvent` consommés par [`JSONLMissionMetricsSink`](file:///c:/Users/nanod/Desktop/my_ai_harness/core/metrics_sink.py).
La commande de relecture :
```bash
python -m core.replay <run_id>
# ou
python main.py --replay <run_id>
```
permet de reconstituer à la milliseconde près chaque étape, appel d'outil et décision d'une mission.
