# 🗂️ Arborescence Complète du Projet NeoHarness AI

Ce document détaille la structure physique et logique du dépôt `my_ai_harness`, l'organisation modulaire du système agentique et le rôle de chaque composant.

---

## 🌳 Vue d'Ensemble de l'Arborescence

```text
my_ai_harness/
├── agents/                       # Définitions des agents spécialisés (rôles et compétences)
│   ├── __init__.py               # Exports du package agents
│   ├── coder.py                  # Agent Développeur (génération, refactoring, code Python/LaTeX)
│   ├── researcher.py             # Agent Chercheur / Rédacteur (recherche documentaire, Web, synthèse)
│   ├── reviewer.py               # Agent Critique / Réviseur (audit de code, qualité, conformité)
│   └── tester.py                 # Agent Testeur (conception et exécution de tests TDD)
│
├── config/                       # Configuration déclarative du runtime
│   └── config.yaml               # Modèles actifs, routes par intention et feature flags
│
├── core/                         # Cœur de l'architecture agentique
│   ├── artifacts/                # Moteur d'artefacts universel
│   │   ├── engine.py             # Extraction, détection et matérialisation des fichiers produits
│   │   ├── handlers.py           # Gestionnaires de formats (DOCX, PDF, HTML, Python, images)
│   │   ├── models.py             # Modèles de données des artefacts (types, métadonnées, état)
│   │   ├── provenance.py         # Traçabilité cryptographique SHA-256 et isolation par task_id
│   │   └── verifier.py           # Vérification physique et déterministe des fichiers sur disque
│   ├── agent.py                  # Classe abstraite de base d'un Agent
│   ├── agent_loop.py             # BOUCLE AGENTIQUE PRINCIPALE (planifie, appelle le LLM, exécute, vérifie)
│   ├── agent_registry.py         # Registre central des agents enregistrés
│   ├── agent_selector.py         # Sélection dynamique de l'agent selon l'intention
│   ├── artifact_intent.py        # Analyse d'intention de génération de documents (PDF, Word, etc.)
│   ├── checkpoint.py             # Snapshots d'état et retour arrière (Shadow Git rollback)
│   ├── context.py                # Contexte d'exécution de la session
│   ├── context_manager.py        # Gestion et compactage de la fenêtre de contexte
│   ├── dag_engine.py             # MOTEUR DAG ASYNCHRONE : parallélisme, tri topologique, isolation
│   ├── delegation.py             # Moteur de délégation multi-agents (Manager -> Spécialiste)
│   ├── event_bus.py              # Bus d'événements normalisés en temps réel (SSE / UI)
│   ├── events.py                 # Types d'événements natifs et traducteur utilisateur
│   ├── intent_engine.py          # Classification de l'intention utilisateur
│   ├── memory.py                 # Mémoire réflexive cross-missions persistante
│   ├── metrics_sink.py           # Collecte des métriques d'exécution et budgets
│   ├── model_registry.py         # Registre des modèles LLM supportés
│   ├── modes.py                  # Modes de permissions (AUTO, ACCEPT, PLAN)
│   ├── multi_agent_coordinator.py# Coordination hiérarchique Manager / Worker / Critic
│   ├── orchestrator.py           # Orchestration centrale : cycle de vie d'une tâche
│   ├── permissions.py            # Politiques d'autorisation et barrières de sécurité
│   ├── planner.py                # Planification déterministe d'étapes (PlanStep)
│   ├── replay.py                 # Rejeu et débogage de trajectoires agentiques
│   ├── router.py                 # ModelRouter : aiguillage et failover automatique des LLM
│   ├── skill_compatibility.py    # Validation de compatibilité agent / compétences
│   ├── task.py                   # Modèle de tâche et paramètres d'exécution
│   ├── task_context.py           # Continuité contextuelle entre tâches successives
│   ├── task_state.py             # Machine à états de la tâche (TaskState, TaskStatus, AgentResult)
│   ├── tdd_engine.py             # Moteur TDD boucle fermée (Red-Green-Refactor)
│   ├── title_generator.py        # Génération intelligente de titres de conversations
│   └── verifier.py               # Oracle de vérification déterministe des livrables
│
├── docs/                         # Documentation technique et d'ingénierie
│   ├── ARCHITECTURE.md           # Spécifications de l'architecture globale
│   ├── AUDIT.md                  # Historique des audits et corrections
│   ├── EVALS.md                  # Cadre d'évaluation des performances agentiques
│   ├── SECURITY.md               # Directives de sécurité et politique de sandboxing
│   └── VISION.md                 # Vision cible industrielle
│
├── evals/                        # Suite d'évaluations automatisées
│   ├── BASELINE.md               # Mesures de référence
│   ├── results.json              # Résultats d'évaluations
│   ├── RESULTS.md                # Rapport d'analyse comparative
│   ├── runner.py                 # Exécuteur des scénarios d'évaluation
│   └── tasks.py                  # Définition des tâches d'évaluation benchmark
│
├── providers/                    # Adaptateurs d'accès aux modèles LLM
│   ├── base_provider.py          # Interface abstraite commune BaseProvider
│   ├── claude.py                 # Adaptateur Anthropic Claude
│   ├── gemini.py                 # Adaptateur Google Gemini (Flash, Flash-Lite, Pro)
│   ├── local.py                  # Adaptateur heuristique local (offline / tests)
│   ├── mistral.py                # Adaptateur Mistral AI
│   ├── ollama.py                 # Adaptateur Ollama local (modèles open-weights)
│   └── openai.py                 # Adaptateur OpenAI (GPT-4o, GPT-5-mini)
│
├── runtime/                      # Binaires et exécutables locaux embarqués
│   └── pandoc/                   # Pandoc local autonome (pandoc.exe pour DOCX/OMML)
│
├── skills/                       # Compétences métier déclaratives (plugins)
│   ├── analyze/                  # Compétence d'analyse de code ou de données
│   ├── auto/                     # Commande /auto pour réactiver le routage automatique
│   ├── compare/                  # Outil de comparaison avant/après
│   ├── context/                  # Visualisation et gestion du contexte actif
│   ├── debug/                    # Diagnostic et débogage autonome
│   ├── diagnostic/               # Rapport d'état de l'environnement
│   ├── education/                # Compétences pédagogiques spécialisées (Lycée français)
│   │   ├── bacblanc/             # Sujets officiels de Bac Blanc + barèmes
│   │   ├── dm/                   # Devoirs maison complets et corrigés
│   │   ├── exercice/             # Fiches d'exercices progressifs
│   │   └── rag/                  # Documents de référence RAG des programmes officiels
│   ├── export/                   # Exportation de session et livrables
│   ├── memory/                   # Gestion de la mémoire persistante
│   ├── mode/                     # Bascule de mode (/plan, /accept, /auto)
│   ├── model/                    # Sélection explicite du modèle LLM (/model)
│   ├── plan/                     # Mode planification sans modification
│   ├── refactor/                 # Refactorisation propre de code
│   ├── research/                 # Recherche bibliographique et Web
│   ├── review/                   # Revue critique de code et de livrables
│   ├── route/                    # Inspection des routes actives
│   ├── test/                     # Exécution ciblée de suites de tests
│   ├── workflow/                 # Enchaînement de workflows automatisés
│   ├── loader.py                 # Chargement des compétences depuis le disque
│   ├── registry.py               # Enregistrement et indexation des compétences
│   ├── router.py                 # Routage des slash commands vers la compétence adéquate
│   └── runtime.py                # Exécution et injection des paramètres de compétences
│
├── tests/                        # Suite complète de tests unitaires et d'intégration
│   ├── test_agent_loop_characterization.py
│   ├── test_autonomous_agent_e2e.py
│   ├── test_autonomous_production_reinforcement.py
│   ├── test_autonomous_web_retrieval.py
│   ├── test_bacblanc_completion.py
│   ├── test_checkpoint_backtracking.py
│   ├── test_compiler_autofix.py
│   ├── test_conversational_memory.py
│   ├── test_dag_orchestration.py # Validation du moteur DAG asynchrone (Kahn, concurrence, Critic)
│   ├── test_download_mission_isolation_and_integrity.py
│   ├── test_dynamic_browser.py
│   ├── test_html_rendering_pipeline.py
│   ├── test_live_activity_ui.py
│   ├── test_math_tikz.py
│   ├── test_multi_agent_hierarchy.py
│   ├── test_phase0c_sanitization.py
│   ├── test_tdd_and_critic.py
│   └── test_ui_environment.py
│
├── tools/                        # Outils mis à la disposition des agents (fonctions d'action)
│   ├── python_sandbox/           # Bac à sable d'exécution Python isolé
│   ├── browser.py                # Navigation dynamique Playwright (headless)
│   ├── code_search.py            # Recherche sémantique et lexicale dans le code
│   ├── compiler.py               # Compilateur LaTeX/Tectonic avec auto-correction
│   ├── documents.py              # Parsing et extraction de texte de documents (PDF/DOCX)
│   ├── docx.py                   # Générateur de documents Word via Pandoc + équations OMML
│   ├── editor.py                 # Édition chirurgicale de fichiers (remplacements ciblés)
│   ├── filesystem.py             # Opérations de système de fichiers restreintes au workspace
│   ├── git.py                    # Contrôle de version Shadow Git (checkpoints)
│   ├── math_tikz.py              # Compilation de figures géométriques TikZ / PGFPlots
│   ├── python_runtime.py         # Exécution de scripts Python en sous-processus isolé
│   ├── registry.py               # ToolRegistry central : vérification stricte des autorisations
│   ├── search.py                 # Recherche Web multi-fournisseurs (DuckDuckGo, SearX, Gemini)
│   ├── terminal.py               # Exécution de commandes bash/powershell sous contrôle
│   ├── viewer.py                 # Visualisation et inspection de fichiers
│   └── vision.py                 # Analyse visuelle d'images pour modèles multimodaux
│
├── ui/                           # Interface utilisateur Web (Cockpit NeoHarness)
│   ├── static/                   # Assets front-end (HTML5 / Vanilla JS / CSS moderne)
│   │   ├── app.js                # Contrôleur front-end : SSE, rendu du chat, streaming, artefacts
│   │   ├── index.html            # Structure de l'interface (3 colonnes : sidebar, chat, aperçu)
│   │   └── styles.css            # Feuille de style responsive (thème clair/sombre, typographie)
│   ├── server.py                 # Serveur HTTP local (FastAPI / stdlib http.server) avec endpoints REST et SSE
│   └── __init__.py
│
├── workspace/                    # ESPACE DE TRAVAIL ISOLÉ (fichiers créés par les missions)
│   ├── .harness/                 # Métadonnées locales (conversations.json, provenance_ledger.json)
│   ├── downloads/                # Fichiers téléchargés depuis le Web
│   ├── output/                   # Documents finaux générés
│   └── uploads/                  # Fichiers et images déposés par l'utilisateur
│
├── arborescence/                 # Ce dossier d'architecture et de cartographie
│   ├── ARBORESCENCE.md           # Ce guide descriptif
│   └── ARCHITECTURE_HARNESS_LLM.md # Schémas et fonctionnement de la boucle agentique
│
├── .env                          # Variables d'environnement et clés d'API (GEMINI, OPENAI, MISTRAL)
├── .gitignore                    # Exclusion git (runtimes volumineux, caches, fichiers temporaires)
├── main.py                       # Point d'entrée principal en ligne de commande (CLI / Web UI)
├── requirements.txt              # Dépendances Python requises
└── README.md                     # Documentation d'accueil du projet
```

---

## 🔍 Responsabilités des Modules Clés

### 1. `core/agent_loop.py`
Le cœur battant du système. Il orchestre chaque étape de réflexion, d'appel d'outil, d'observation, de vérification et d'auto-correction selon les budgets alloués (`MissionBudget`).

### 2. `core/orchestrator.py`
Reçoit l'intention de l'utilisateur, configure la session, sélectionne l'agent initial (`coder`, `researcher`, `reviewer`, `tester`), charge les compétences requises et initialise le `DelegationEngine`.

### 3. `core/router.py` & `providers/`
Permet la bascule dynamique et transparente entre fournisseurs (`Gemini`, `OpenAI`, `Mistral`, `Ollama`). Gère le **Failover automatique** avec protection contre les dépassements de quotas (HTTP 429) et les boucles infinies.

### 4. `tools/registry.py` & `core/permissions.py`
Garantit que chaque outil invoqué par le LLM respecte scrupuleusement les permissions accordées (lecture seule, modification autorisée, confirmation humaine requise).

### 5. `core/artifacts/` & `tools/docx.py`
Détecte l'intention de production de fichiers réels (PDF, Word DOCX, scripts Python), convertit le Markdown/LaTeX mathématique en Word natif OMML via Pandoc local, et valide physiquement l'intégrité de l'artefact avant toute notification à l'utilisateur.

