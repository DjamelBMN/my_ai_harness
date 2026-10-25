# AUDIT D'ARCHITECTURE & SÉCURITÉ : AgentLoop (Phase 0.A)

**Projet :** NeoHarness AI (`my_ai_harness`)  
**Date :** 25 Octobre 2026  
**Auteur :** Lead Agentic Systems Engineer  
**Statut :** Phase 0.A complétée  

---

## 1. Schéma Mermaid du Flux Actuel (`AgentLoop.run`)

```mermaid
flowchart TD
    Start(["run(agent, task, state)"]) --> ValidateProvider{"agent.provider\ndéfini ?"}
    ValidateProvider -- Non --> ErrProvider["RuntimeError"]
    ValidateProvider -- Oui --> InitState["Init TaskState & TaskMode\n(PLAN/ACCEPT/EDIT/AUTO)"]
    
    InitState --> RunInitialObs["Perception initiale\n(_run_initial_observations)"]
    RunInitialObs --> BuildInitialPrompt["Construire prompt initial\n(_initial_prompt)"]
    
    BuildInitialPrompt --> LoopStart["Boucle Iteration 1..N\n(max_iterations)"]
    
    LoopStart --> CheckStop{"_stop_requested ?"}
    CheckStop -- Oui --> RetCancelled["AgentResult(status='failed',\n'Interrompu par utilisateur')"]
    CheckStop -- Non --> PrepareSchemas["Filtrer schémas d'outils\n(mode PLAN / allowed_tools)"]
    
    PrepareSchemas --> ProviderCall["provider.generate_agent_turn(...)"]
    
    ProviderCall -- Exception --> HandleProvErr{"Quota ou\nRate Limit ?"}
    HandleProvErr -- Quoi/Erreur --> ProvFailover{"Fallback\ndisponible ?"}
    ProvFailover -- Oui --> SwitchProv["Bascule vers fallback\n(provider.failover)"] --> ProviderCall
    ProvFailover -- Non --> MaxRetryCheck{"attempt > max_retries\nou fallback=None ?"}
    
    MaxRetryCheck -- Non --> RetryBackoff["Sleep & Retry provider"] --> ProviderCall
    MaxRetryCheck -- Oui --> BackdoorDirect["[RISQUE] Appel direct hors registre\nautonomous_web_retrieve / doc_reader"]
    BackdoorDirect --> RetProvFail["AgentResult(status='failed'\nou _partial_failure_result)"]
    
    ProviderCall -- Succès Turn --> CheckTurnType{"Turn contient\ndes tool_calls ?"}
    
    CheckTurnType -- Oui --> ExecTools["Exécution des outils\n(ToolRegistry / DelegationEngine)"]
    ExecTools --> RecordObs["Enregistrer observations\net tool_results"]
    RecordObs --> NextIter["Iteration suivante\n(continuation & tool_results)"] --> LoopStart
    
    CheckTurnType -- Non (Réponse texte) --> SpecialValidator{"Validateur spécialisé\n(validate_final_answer) ?"}
    
    SpecialValidator -- Défini --> RunSpecVal["Exécution validateur"]
    RunSpecVal -- Incomplet --> CanRepair{"correction_count <\nmax_retries ?"}
    CanRepair -- Oui --> RepairLoop["prompt = repair_prompt\nIteration suivante"] --> LoopStart
    CanRepair -- Non --> BlockedSpec["AgentResult(status='incomplete')"]
    
    SpecialValidator -- Non/Complet --> RunVerifier["Vérification déterministe\n(Verifier.verify)"]
    RunVerifier --> VerifPassed{"verification['status']\n== 'passed' ?"}
    
    VerifPassed -- Non --> CanCorrect{"correction_count <\nmax_retries ?"}
    CanCorrect -- Oui --> CorrectLoop["prompt = ré-essayer\nIteration suivante"] --> LoopStart
    CanCorrect -- Non --> BlockedVerif["AgentResult(status='incomplete')"]
    
    VerifPassed -- Oui --> DeliverOk["Marquer PlanStep completed\nstatus = success / verified"]
    DeliverOk --> EndResult(["AgentResult Livré"])
```

---

## 2. Points d'Extension Architecturaux

1. **`ToolRegistry` (`tools/registry.py`)** :
   - Unique autorité de validation des schémas d'outils (`_validate_schema`), des niveaux de risque (`RiskLevel`), des timeouts et des politiques de permission (`PermissionPolicy`).
   - Centralisation des exécutions avec isolation synchrone (mutations) vs `ThreadPoolExecutor` (lectures concurrentes).
   - Découverte dynamique via `discover()` et génération de schémas OpenAPI/LLM via `schemas()`.

2. **Hooks Agent Spécialisés (`core/agent.py`)** :
   - `validate_final_answer(final_answer, task, state, filesystem)` : validation déterministe de la complétude du livrable propre au métier de l'agent.
   - `partial_delivery_message(reason, partial_content, state, filesystem)` : formatage contrôlé d'un livrable partiel honnête en cas d'interruption.
   - `completion_repair_prompt(report)` : génération du prompt guidé pour combler les manques identifiés sans hallucination.
   - `incomplete_delivery_message(report)` : notification utilisateur claire lorsque la complétude échoue.

3. **`ModelRouter` & Fournisseurs (`core/router.py`, `providers/base_provider.py`)** :
   - Routage intelligent par intention (`coding`, `research`, `review`, `testing`, `exam_creation`).
   - Bascule automatique sans boucle infinie (`get_fallback_provider`) avec exclusion des familles entières de providers en échec.

4. **`DelegationEngine` & `MultiAgentCoordinator` (`core/delegation.py`, `core/multi_agent_coordinator.py`)** :
   - Délégation hiérarchique bornée (max depth 3, max délégations 8).
   - Détection de cycles sur la signature `(agent, task)`.
   - Handoff contextuel contrôlé entre mission mère et mission fille.

5. **`Verifier` Déterministe (`core/verifier.py`)** :
   - Contrôles déterministes basés exclusivement sur les artefacts physiques (SHA-256 réels, existence, magic bytes) et les tool executions observables.
   - Rejet immédiat de toute tentative de substitution locale non sollicitée.

---

## 3. Risques de Sécurité et Défauts Architecturaux Identifiés

| ID | Risque / Défaut | Localisation | Impact | Gravité |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | **Backdoor hors ToolRegistry** | `core/agent_loop.py:478, 560` | Appels directs à `autonomous_web_retrieve_and_download` en chemin d'exception, contournant les permissions, le mode `PLAN` et le bus d'événements. | **CRITIQUE** |
| **SEC-02** | **Injection de prompt via sorties d'outils** | `core/agent_loop.py:708-725` | Les sorties textuelles d'outils ou pages web sont injectées brutes dans `pending_tool_results` sans balise de confinement de données non fiables. | **HAUTE** |
| **ARCH-01** | **Fausse complétion sur chemin d'échec** | `core/agent_loop.py:488-504` | Assignation de `status="success"` et `[DELIVERY OK]` alors que le provider LLM a échoué (quota ou indisponibilité). | **HAUTE** |
| **ARCH-02** | **Détection d'intention par sous-chaînes vulnérables** | `core/agent_loop.py:473, 508, 547` | Détection naïve `in` (ex. `"lis"`, `"lit"` déclenchés par *"politique"*, *"liste"*). Doit utiliser `intent_decision` ou regex à frontières de mots `\b`. | **MOYENNE** |
| **ARCH-03** | **Logique métier spécifique codée en dur dans la boucle générique** | `core/agent_loop.py:826, 881` | Chaînes en dur `"Compléter le livrable BacBlanc..."` et `"bacblanc_complete_deliverable"` dans `AgentLoop`. Doit provenir dynamiquement de l'agent. | **MOYENNE** |
| **ARCH-04** | **Mutation directe de l'état du provider** | `core/agent_loop.py:363, 375` | Mutation in-place de `provider.max_output_tokens` et `provider.stream_callback` au lieu de passer par des paramètres d'appel explicites. | **MOYENNE** |
| **ARCH-05** | **Absence de garde-fou de répétition d'outils** | `core/agent_loop.py:613-735` | Aucune détection d'appels d'outils identiques successifs en boucle avec les mêmes arguments et la même erreur. | **MOYENNE** |
| **ARCH-06** | **Absence de budget de mission formel** | `core/agent_loop.py:322` | La boucle ne suit que le nombre d'itérations, sans budget plafond de tokens consommés, ni durée maximale absolue en secondes. | **MOYENNE** |
| **ARCH-07** | **PlanStep marqué malhonnêtement comme "completed"** | `core/agent_loop.py:943-945` | Toutes les étapes du plan sont passées à `completed` lors de la livraison, même celles non exécutées ou sans observation. | **BASSE** |

---

## 4. État de Base des Tests (Baseline Tests)

Exécution des tests de base réels du projet :
- **Suites de base (runtime, skills, multi-agent)** :
  `python -m unittest tests/test_runtime.py tests/test_skills.py tests/test_multi_agent_runtime.py tests/test_general_skills.py`
  - **Résultat :** **79/79 tests validés avec succès** (100% OK en 9.18s).
- **Suites d'intégrité et isolation des téléchargements** :
  `python -m unittest tests/test_download_mission_isolation_and_integrity.py tests/test_autonomous_web_retrieval.py`
  - **Résultat :** **12/12 tests validés avec succès** (100% OK en 6.08s).
- **Suite UI & gouvernance** :
  `python -m unittest tests/test_ui_environment.py`
  - **Résultat :** **22/22 tests validés avec succès** (100% OK en 20.85s).

---

## 5. Classification des 206 Diagnostics Ruff et 72 Diagnostics Pyright sur `core/`

### A. Répartition Pyright (72 erreurs de typage strict)
1. **Appels invalides du constructeur `AgentResult` (12 erreurs)** :
   `AgentResult(task_id=..., steps_executed=..., files=...)` -> Paramètres non déclarés dans la dataclass `AgentResult`.
2. **Utilisation d'un membre d'enum inexistant (4 erreurs)** :
   `TaskStatus.FINISHED` n'existe pas dans `TaskStatus` (`COMPLETED` et `FAILED` existent).
3. **Module introuvable (1 erreur)** :
   `from tools.document_reader import read_document` -> le module réel est `tools.documents`.
4. **Accès d'attributs non typés sur `object` (42 erreurs)** :
   Dans `core/planner.py` et `core/agent_loop.py`, manipulations de `skill.config`, `skill.agent`, `specialized_report.get` sur des variables typées `object`.
5. **Variables ou types non importés (13 erreurs)** :
   `Path` non importé dans `core/task_context.py:314`, `Any` non importé dans `core/task.py:27`.

### B. Répartition Ruff (206 alertes linter)
1. **Ordre des imports et formatage (`I001`, 38 alertes)** : Blocs d'imports non triés selon PEP 8.
2. **Concaténation implicite de chaînes non parenthésées (`ISC004`, 22 alertes)** : Dans les listes de prompts système de `core/agent.py`.
3. **Capture d'exceptions aveugle (`BLE001`, `S110`, 35 alertes)** : `try: ... except Exception: pass` sans logger ni commentaire d'intention.
4. **Utilisation d'alias regex dépréciés (`FURB167`, 18 alertes)** : `re.I` au lieu de `re.IGNORECASE`.
5. **Imports inutilisés (`F401`, 15 alertes)** : Ex. `from pathlib import Path` inutilisé dans `core/verifier.py`.
6. **Modernisation syntaxique (`UP035`, `FURB188`, 78 alertes)** : Remplacement de `typing.List` par `list`, `slug[:-6]` par `removesuffix`.

---

## 6. Critères de Passage Phase 0.A
- [x] Mermaid flowchart complet du flux d'exécution et de décision.
- [x] Points d'extension identifiés et documentés.
- [x] Risques de sécurité et faiblesses architecturales recensés.
- [x] État de base des tests exécuté et mesuré.
- [x] Classification exhaustive des problèmes de typage et de linter sur `core/`.


---

## 7. Réalisation et Validation de la Phase 0.C (Assainissement ciblé)

Tous les 10 points prescrits ont été exécutés et vérifiés par tests unitaires dédiés (`tests/test_phase0c_sanitization.py` et `tests/test_agent_loop_characterization.py`) :

1. **Suppression des backdoors de contournement** : Les appels directs hors permissions à `autonomous_web_retrieve_and_download` et `tools.document_reader` sur échec provider ou refus du modèle ont été intégralement éradiqués. Tout appel passe par `ToolRegistry`.
2. **Élimination de la fausse réussite** : Aucun chemin d'erreur provider ne retourne `status="success"` ou n'annonce de faux `[DELIVERY OK]`. En cas d'échec, le statut est strictement `failed` ou `incomplete`.
3. **Remplacement des heuristiques de sous-chaîne** : `_contains_any_word` avec frontières de mots regex (`\b`) déployé dans `core/agent_loop.py` et `core/intent_engine.py`. Les termes comme « politique » ou « liste » ne déclenchent plus d'action documentaire erronée.
4. **Refactorisation du retry provider et rupture de cycle dans le failover** : Distinction stricte entre erreurs de quota (failover immédiat) et erreurs transitoires (backoff borné). Détection de cycle sur l'ensemble des providers candidats : la boucle s'arrête proprement dès épuisement sans jamais boucler indéfiniment.
5. **Neutralisation des données non fiables** : Encapsulation systématique de tout retour d'outil dans des balises `<donnees_non_fiables>...</donnees_non_fiables>` assorties d'une directive d'inviolabilité d'instruction.
6. **Découplage de `bacblanc_complete_deliverable`** : Les noms de vérification sont dérivés dynamiquement de la configuration de l'agent et du livrable (`{agent_name}_complete_deliverable`).
7. **Encapsulation et hygiène d'état** : Initialisation complète de tous les attributs dans `AgentLoop.__init__` (`_stop_requested`, `router`, `delegation_engine`, `consecutive_tool_failures`). Suppression des mutations d'instance non protégées.
8. **Garde-fou anti-bégaiement (repetition guard)** : Détection et arrêt immédiat avec levée d'erreur structurée dès que 3 appels consécutifs échouent avec le même hash d'arguments.
9. **Budget de mission (`MissionBudget`)** : Dataclass encadrant les tokens, le temps d'exécution, le nombre d'outils et la profondeur de délégation avec arrêt propre sur épuisement.
10. **Honnêteté du statut de `PlanStep`** : Élimination de la boucle qui marquait frauduleusement toutes les étapes comme « completed » à la livraison. Seules les étapes disposant d'une preuve d'observation ou de validation passent à `completed`.

---

## 8. Métriques Avant / Après Phase 0

| Métrique | État Initial (Master) | État Final (Phase 0) | Statut |
| :--- | :--- | :--- | :--- |
| **Backdoors autonomes hors permissions** | 2 appels directs non sécurisés | 0 (100% via ToolRegistry & permissions) | **RÉSOLU** |
| **Risque de boucle infinie sur provider** | Non borné (jusqu'à 264 étapes en UI) | Rupture de cycle déterministe (arrêt propre) | **RÉSOLU** |
| **Fausse réussite sur erreur provider** | Présente (`status="success"` simulé) | Supprimée (`status="failed"` honnête) | **RÉSOLU** |
| **Faux positifs sous-chaîne ('politique', 'liste')**| Déclenchait des actions intempestives | 0 faux positif (frontières `\b`) | **RÉSOLU** |
| **Garde-fou anti-bégaiement outils** | Inexistant (boucle jusqu'à max_iterations) | Actif (arrêt propre à $K=3$ échecs identiques) | **RÉSOLU** |
| **Isolation des données non fiables** | Données injectées brutes | Délimitées `<donnees_non_fiables>` | **RÉSOLU** |
| **Tests de caractérisation AgentLoop** | 0 test | 8 tests dédiés (100% passants) | **VALIDÉ** |
| **Tests de non-régression Phase 0.C** | 0 test | 8 tests dédiés (100% passants) | **VALIDÉ** |
| **Tests existants de non-régression** | 192 tests passants | 195 tests passants (100% passants) | **PRÉSERVÉ** |
