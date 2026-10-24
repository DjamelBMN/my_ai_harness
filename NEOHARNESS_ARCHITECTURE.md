# NEOHARNESS_ARCHITECTURE.md — Documentation Technique et Architecture Complète de NeoHarness AI

> **Créateur & Architecte : Djamel BENMAKHLOUF**
> **Document de référence d'architecture, de fonctionnement interne et de maintenance de NeoHarness AI**
> Ce document reflète **strictement l'état réel du dépôt** vérifié fichier par fichier et par exécution directe, sans inventer de composant, de modèle, de skill ou d'outil inexistant.

---

## Table des matières

1. [Vue d'ensemble du projet](#1-vue-densemble-du-projet)
2. [Arborescence complète finale](#2-arborescence-complète-finale)
3. [Description détaillée fichier par fichier](#3-description-détaillée-fichier-par-fichier)
4. [Fonctionnement global de bout en bout](#4-fonctionnement-global-de-bout-en-bout)
5. [Cycle de vie complet d'une requête](#5-cycle-de-vie-complet-dune-requête)
6. [Fonctionnement détaillé du Model Router & Streaming](#6-fonctionnement-détaillé-du-model-router--streaming)
7. [Architecture complète des 18 Skills (Ordre Canonique)](#7-architecture-complète-des-18-skills-ordre-canonique)
8. [Architecture des Agents](#8-architecture-des-agents)
9. [Architecture des Tools & Compilation PDF Tectonic](#9-architecture-des-tools--compilation-pdf-tectonic)
10. [Architecture de la Mémoire](#10-architecture-de-la-mémoire)
11. [Architecture du RAG](#11-architecture-du-rag)
12. [Architecture de l'interface utilisateur minimaliste (Addendum Final)](#12-architecture-de-linterface-utilisateur-minimaliste-addendum-final)
13. [Système d'événements et streaming SSE temps réel](#13-système-dévénements-et-streaming-sse-temps-réel)
14. [Dépendances et bibliothèques](#14-dépendances-et-bibliothèques)
15. [Configuration et variables d'environnement](#15-configuration-et-variables-denvironnement)
16. [Flux de données (Data Flow)](#16-flux-de-données-data-flow)
17. [Carte des dépendances entre fichiers](#17-carte-des-dépendances-entre-fichiers)
18. [Guide « Où modifier quoi ? »](#18-guide--où-modifier-quoi--)
19. [Guide de démarrage et de lecture du code](#19-guide-de-démarrage-et-de-lecture-du-code)
20. [Tests et validation (125 tests)](#20-tests-et-validation-125-tests)
21. [Journal des modifications de la refonte et de l'Addendum Final](#21-journal-des-modifications-de-la-refonte-et-de-laddendum-final)
22. [Risques connus et limites actuelles](#22-risques-connus-et-limites-actuelles)
23. [Feuille de route technique (Roadmap)](#23-feuille-de-route-technique-roadmap)

---

## 1. Vue d'ensemble du projet

### 1.1 Qu'est-ce que NeoHarness AI ?
**NeoHarness AI** est un **harness agentique multi-modèles et multi-agents** écrit en Python, doté à la fois :
- d'une interface **CLI interactive** complète (`python main.py`),
- et d'une **interface web minimaliste d'environnement opératoire IA** (`python main.py --ui --port 8765`), bâtie sans dépendance externe lourde (serveur HTTP/SSE natif Python + interface HTML5/CSS3/JS épurée avec KaTeX, Web Audio API et aperçu documentaire).

### 1.2 Philosophie : « Complexité cachée. Fonctionnalités 100 % réelles. Zéro simulation. »
NeoHarness AI combine :
- un **Mode Clair raffiné par défaut** (`data-theme="light"`, palette pierre chaude `#F6F5F0` / `#EFECE6` / `#FFFFFF`) avec bascule instantanée vers le Mode Sombre (`data-theme="dark"`, `#0B0D10`) persistée dans `localStorage` ;
- une **palette flottante immédiate des 18 Slash Commands (`/`)** dans l'ordre canonique strict (`1. analyze` .. `18. workflow`) qui s'ouvre dès la saisie de `/` au début du compositeur ou après un espace ;
- un **panneau latéral droit unifié (`#right-inspector`)**, fermé par défaut, capable d'afficher soit l'**Aperçu de Document** (**PDF compilé réellement avec Tectonic** ou **HTML interactif dans un `<iframe>` sandboxé**) soit l'**Inspecteur Technique**, sans jamais ouvrir une troisième colonne ;
- une **dictée vocale style GPT** dans le compositeur utilisant de vraies données d'amplitude microphone (`navigator.mediaDevices.getUserMedia` + `AudioContext` + `AnalyserNode`) et la transcription vocale réelle (`SpeechRecognition` / `webkitSpeechRecognition`) ;
- un **moteur agentique complet** normalisant strictement les contrats `Task` / `PlanStep` aux frontières (`ensure_task`), exécutant **17 outils réels** (`ToolRegistry` + `PermissionPolicy`), la recherche Internet réelle (`web_search`) et la vérification finale (`Verifier`).

---

## 2. Arborescence complète finale

```text
my_ai_harness/
├── .gitignore                        # Règles d'exclusion Git (.env, __pycache__, etc.)
├── README.md                         # Présentation rapide et commandes de base
├── NEOHARNESS_ARCHITECTURE.md        # Documentation technique complète (ce document)
├── NEOHARNESS_RUNTIME_VALIDATION.md  # Rapport de vérification runtime réelle de bout en bout
├── requirements.txt                  # Dépendances Python (pyyaml, mistralai, pypdf)
├── main.py                           # Point d'entrée principal CLI et lanceur UI (--ui)
│
├── config/
│   └── config.yaml                   # Configuration centrale (providers, agents, routes, permissions, modes, skills)
│
├── agents/
│   ├── __init__.py                   # Package des agents spécialisés
│   ├── coder.py                      # CodeAgent : développement, écriture/édition de fichiers, refactoring
│   ├── researcher.py                 # ResearchAgent : recherche locale et Internet, exploration documentaire
│   ├── reviewer.py                   # ReviewAgent : revue de code, audit qualité et risques
│   └── tester.py                     # TestAgent : exécution et validation des tests
│
├── core/
│   ├── __init__.py                   # Package du noyau d'orchestration
│   ├── agent.py                      # Classe de base Agent (normalisation ensure_task)
│   ├── agent_loop.py                 # Boucle d'exécution agentique multi-étapes (tools, web_search, streaming, vérification)
│   ├── agent_registry.py             # Registre des agents disponibles (AgentRegistry)
│   ├── agent_selector.py             # Sélection d'agent selon l'étape ou l'intention (AgentSelector)
│   ├── context.py                    # Historique d'interactions léger (Context)
│   ├── context_manager.py            # Gestionnaire de contexte workspace et budget de tokens (ContextManager)
│   ├── delegation.py                 # Délégation contrôlée de sous-tâches entre agents (DelegationManager)
│   ├── event_bus.py                  # Bus d'événements normalisés temps réel et SSE (STREAM_DELTA, ARTIFACT_READY)
│   ├── events.py                     # Événements bas niveau du runtime et traducteur (HarnessEvent, EventTranslator)
│   ├── intent_engine.py              # Moteur de classification d'intention et détection web (IntentEngine)
│   ├── memory.py                     # Gestionnaire de mémoire (MemoryManager)
│   ├── model_registry.py             # Registre vérifié des Providers, Modèles et Capabilities (ModelCapabilityRegistry)
│   ├── modes.py                      # Modes d'exécution (PLAN, ACCEPT, AUTO, EDIT)
│   ├── multi_agent_coordinator.py    # Coordination séquentielle multi-agents (MultiAgentCoordinator)
│   ├── orchestrator.py               # Orchestrateur central (Orchestrator, normalisation ensure_task)
│   ├── permissions.py                # Politique de permissions d'outils (PermissionPolicy, RiskLevel)
│   ├── planner.py                    # Planificateur d'étapes (Planner, Plan, PlanStep, normalisation ensure_task)
│   ├── router.py                     # Routeur de modèles par agent et par type de tâche (ModelRouter)
│   ├── skill_compatibility.py        # Moteur de compatibilité Provider -> Model -> Capabilities -> Skills (1..18)
│   ├── task.py                       # Modèle de tâche (Task) et normalisateur strict ensure_task()
│   ├── task_state.py                 # État riche d'exécution d'une tâche (TaskState, normalisation PlanStep)
│   └── verifier.py                   # Vérificateur final de complétude et de cohérence (Verifier)
│
├── providers/
│   ├── __init__.py                   # Package des adaptateurs de fournisseurs LLM
│   ├── base_provider.py              # Contrat abstrait BaseProvider et AgentTurn
│   ├── claude.py                     # ClaudeProvider (squelette non connecté par défaut)
│   ├── gemini.py                     # GeminiProvider (API Google Gemini native, streaming, fallback quota 429 google_search -> web_search)
│   ├── local.py                      # LocalProvider (fournisseur local déterministe pour tests hors-ligne)
│   ├── mistral.py                    # MistralProvider (SDK mistralai + client HTTP urllib)
│   ├── ollama.py                     # OllamaProvider (exécution locale via serveur HTTP Ollama)
│   └── openai.py                     # OpenAIProvider (API OpenAI Responses / Chat Completions)
│
├── skills/
│   ├── __init__.py                   # Export public du système de Skills
│   ├── loader.py                     # Chargement dynamique des dossiers de Skills, commandes, agents, RAG et templates
│   ├── registry.py                   # Registre central des 18 Skills dans l'ordre canonique (CANONICAL_SKILL_ORDER)
│   ├── router.py                     # Routage automatique par mots-clés, triggers et commandes slash (SkillRouter)
│   ├── runtime.py                    # Exécution des commandes slash et état de session (SkillRuntime)
│   └── <18 dossiers de skills>/      # 1. analyze, 2. auto, 3. bacblanc, 4. compare, 5. context, 6. debug,
│                                     # 7. diagnostic, 8. export, 9. memory, 10. mode, 11. model, 12. plan,
│                                     # 13. refactor, 14. research, 15. review, 16. route, 17. test, 18. workflow
│
├── tools/
│   ├── __init__.py                   # Package des outils (Tools)
│   ├── documents.py                  # Lecture documentaire (read_document) et compilation LaTeX via Tectonic (compile_latex, auto-réparation)
│   ├── filesystem.py                 # Opérations fichiers confinées dans workspace/ (WorkspaceFilesystem)
│   ├── git.py                        # Inspection Git (GitWorkspace : status, diff, log)
│   ├── process_utils.py              # Exécution de sous-processus robuste Windows/UTF-8 (run_text_command)
│   ├── registry.py                   # Registre central des 17 outils et schémas JSON (ToolRegistry)
│   ├── search.py                     # Recherche locale (find_file, search_files) et recherche Internet réelle (web_search)
│   └── terminal.py                   # Exécution de commandes shell et tests (run_command, run_tests)
│
├── ui/
│   ├── __init__.py                   # Package de l'interface web
│   ├── server.py                     # Pont runtime (NeoHarnessRuntimeBridge) + serveur HTTP REST, SSE & aperçu PDF/HTML
│   └── static/
│       ├── index.html                # Interface Mode Clair par défaut, Palette Slash (/), Dictée Vocale GPT, Panneau Aperçu PDF/HTML
│       ├── styles.css                # Design system pierre chaude (#F6F5F0) / sombre (#0B0D10)
│       └── app.js                    # Logique client réactive (Slash Palette, Web Audio AnalyserNode, SpeechRecognition, KaTeX, Aperçu PDF/HTML)
│
├── tests/
│   ├── test_bacblanc_completion.py   # Tests de continuation Gemini, validation LaTeX et skill bacblanc
│   ├── test_general_skills.py        # Tests des 18 skills, de leurs commandes slash et du routage
│   ├── test_mistral.py               # Tests du provider Mistral et de ses routes
│   ├── test_multi_agent_runtime.py   # Tests de la boucle multi-agents, délégation, permissions et événements
│   ├── test_runtime.py               # Tests du coeur runtime, routeur, mémoire, outils fichiers/git/terminal
│   ├── test_skills.py                # Tests du chargeur, registre et routeur de skills
│   └── test_ui_environment.py        # 31 scénarios d'intégration UI, normalisation Task, Tectonic PDF, HTML Sandbox, Slash Palette, Mode Clair
│
└── workspace/                        # Répertoire de travail isolé pour les opérations fichiers des agents
```

---

## 3. Description détaillée fichier par fichier

### 3.1 Entrée et Normalisation des Contrats (`core/task.py`, `core/planner.py`, `core/orchestrator.py`, `core/agent_loop.py`)
- **[core/task.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/task.py)** : Définit `Task` et la fonction frontière `ensure_task(task: Task | str, ...)` qui convertit de manière déterministe toute chaîne brute en instance `Task` typée et lève `TypeError` ou `ValueError` explicite en cas de type invalide ou de tâche vide.
- **[core/task_state.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/task_state.py)** : Normalise dans `TaskState.__post_init__` tout élément de `self.plan` en instance `PlanStep` afin qu'aucune chaîne brute ne puisse provoquer `AttributeError: 'str' object has no attribute 'description'`.
- **[core/planner.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/planner.py)**, **[core/orchestrator.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/orchestrator.py)**, **[core/agent.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/agent.py)**, **[core/agent_loop.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/agent_loop.py)** : Appliquent `ensure_task(...)` dès l'entrée de `plan()`, `create_plan()`, `run()`, `run_agentic()` et `AgentLoop.run()`.

### 3.2 Fournisseur Gemini & Streaming (`providers/gemini.py`)
- **[providers/gemini.py](file:///c:/Users/nanod/Desktop/my_ai_harness/providers/gemini.py)** :
  - Prend en charge le streaming temps réel via `generate_content_stream` lorsque `stream_callback` est fourni par `AgentLoop`.
  - Lorsque le palier gratuit (`free tier`) de `gemini-flash-lite-latest` retourne une erreur HTTP 429 (`RESOURCE_EXHAUSTED`) spécifiquement liée à l'outil natif `google_search`, bascule automatiquement et sans perte vers les déclarations de fonctions (`function_declarations`) incluant l'outil réel `web_search` du `ToolRegistry`.

### 3.3 Compilation PDF via Tectonic (`tools/documents.py`)
- **[tools/documents.py](file:///c:/Users/nanod/Desktop/my_ai_harness/tools/documents.py)** :
  - `compile_latex()` privilégie **Tectonic** (`tectonic --chatter minimal --outdir <tmp_dir> <work_tex>`) avec fallback sur `pdflatex`.
  - Compile dans un dossier temporaire isolé (`tempfile.TemporaryDirectory`) afin de **ne jamais retourner un ancien PDF obsolète** si une compilation échoue.
  - Vérifie l'intégrité binaire du PDF produit (`%PDF-`, taille non nulle, nombre de pages `>= 1` via `pypdf`).
  - `_repair_latex_source()` répare automatiquement les erreurs LaTeX courantes (ajout de `\documentclass` / `\begin{document}` / `\end{document}` manquants, remplacement de `\usepackage{libertinus-otf}` / `\usepackage{fontspec}` incompatibles hors-cache par `lmodern`, fermeture des accolades non équilibrées) et retente la compilation Tectonic.

---

## 4. Fonctionnement global de bout en bout

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│            UTILISATEUR (Interface Web Mode Clair par défaut ou CLI)                    │
│   Palette Slash (/) │ Dictée Vocale GPT (Web Audio) │ Aperçu PDF/HTML à droite         │
└───────────────────┬────────────────────────────────────────────────────▲───────────────┘
                    │ 1. POST /api/tasks/run                             │ 8. Flux SSE
                    ▼                                                    │ (STREAM_DELTA,
┌────────────────────────────────────────────────────────────────────────┴───────────────┐
│                   PONT D'EXÉCUTION : NeoHarnessRuntimeBridge (ui/server.py)            │
│   • Commandes utilitaires locales (/export, /model, /mode, /memory, /diagnostic) :     │
│     exécution directe via SkillRuntime SANS faux événements PLANNER_STARTED            │
│   • Missions agentiques : normalisation ensure_task, lancement Orchestrator+AgentLoop  │
│   • Post-traitement : détection .tex/.html/.pdf, compilation Tectonic, ARTIFACT_READY  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Cycle de vie complet d'une requête

1. **Saisie ou Dictée Vocale** : L'utilisateur saisit sa demande, utilise `/` pour sélectionner l'un des 18 skills dans l'ordre canonique, ou dicte sa demande au microphone (barre vocale style GPT avec onde audio temps réel `AnalyserNode`).
2. **Normalisation & Planification** : `ensure_task()` garantit un objet `Task` valide ; `Planner` construit les étapes `PlanStep`.
3. **Exécution & Streaming SSE** : Le modèle actif exécute ses outils (`web_search`, `write_file`, `compile_latex`, etc.) et émet `STREAM_DELTA` en temps réel vers l'interface qui rend le Markdown et les formules KaTeX au fil de l'eau.
4. **Compilation & Aperçu Automatique** : Si un fichier `.tex`, `.pdf` ou `.html` est créé ou modifié, `NeoHarnessRuntimeBridge` compile automatiquement le `.tex` avec **Tectonic**, vérifie le PDF produit, émet `ARTIFACT_READY` et ouvre le panneau latéral droit en mode **Aperçu Document**.

---

## 6. Fonctionnement détaillé du Model Router & Streaming

| ID Modèle | Classe Provider | Modèle configuré (`config.yaml`) | État de connexion | Capacités principales |
| :--- | :--- | :--- | :--- | :--- |
| `gemini` | `GeminiProvider` (`providers/gemini.py`) | `gemini-2.5-flash` | **Connecté** (`GEMINI_API_KEY`) | Vision, Long Context, Function Calling, Web Search, Streaming temps réel |
| `gemini_flash_lite` | `GeminiProvider` (`providers/gemini.py`) | `gemini-flash-lite-latest` | **Connecté** (`GEMINI_API_KEY`) | Vision, Long Context, Function Calling, Web Search (avec fallback auto `web_search` sur quota 429 grounding), Streaming |
| `openai` | `OpenAIProvider` (`providers/openai.py`) | `gpt-5-mini` | Actif si `OPENAI_API_KEY` présente | Vision, Long Context, Function Calling, `web_search`, Reasoning |
| `mistral` | `MistralProvider` (`providers/mistral.py`) | `mistral-small-latest` | Actif si `MISTRAL_API_KEY` présente | Function Calling, `web_search`, Structured Output |
| `ollama` | `OllamaProvider` (`providers/ollama.py`) | `qwen3:1.7b` | **Connecté en local** (`127.0.0.1:11434`) | Exécution locale, Function Calling JSON, `web_search` |
| `claude` | `ClaudeProvider` (`providers/claude.py`) | `claude-sonnet-4` | **Non connecté** (squelette) | Signalé honnêtement comme indisponible |

---

## 7. Architecture complète des 18 Skills (Ordre Canonique)

Les **18 Skills réels** sont ordonnés de manière canonique (`CANONICAL_SKILL_ORDER` dans [skills/registry.py](file:///c:/Users/nanod/Desktop/my_ai_harness/skills/registry.py)) dans le backend, l'API `/api/skills`, la palette `/` et l'Inspecteur :
1. `analyze` (`/analyze`)
2. `auto` (`/auto`)
3. `bacblanc` (`/bacblanc`)
4. `compare` (`/compare`)
5. `context` (`/context`)
6. `debug` (`/debug`)
7. `diagnostic` (`/diagnostic`)
8. `export` (`/export`)
9. `memory` (`/memory`)
10. `mode` (`/mode`)
11. `model` (`/model`)
12. `plan` (`/plan`)
13. `refactor` (`/refactor`)
14. `research` (`/research`)
15. `review` (`/review`)
16. `route` (`/route`)
17. `test` (`/test`)
18. `workflow` (`/workflow`)

---

## 8. Architecture des Agents

Les **5 Agents réels** sont : `CodeAgent` (`coder`), `ResearchAgent` (`researcher`), `ReviewAgent` (`reviewer`), `TestAgent` (`tester`), et `BacBlancAgent` (`bacblanc`).

---

## 9. Architecture des Tools & Compilation PDF Tectonic

Les **17 Tools réels** enregistrés dans `ToolRegistry` ([tools/registry.py](file:///c:/Users/nanod/Desktop/my_ai_harness/tools/registry.py)) incluent notamment `compile_latex` (utilisant **Tectonic 0.3.2** installé sur le système avec auto-réparation LaTeX déterministe et vérification `%PDF-` + nombre de pages) et `web_search` (recherche Internet réelle).

---

## 10. Architecture de la Mémoire

Implémentée dans [core/memory.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/memory.py) (`MemoryManager`) avec portées Session, Projet, Décisions et Préférences, et signalement honnête `Non configuré` pour les portées Long terme et Procédurale.

---

## 11. Architecture du RAG

Implémentée dans [skills/loader.py](file:///c:/Users/nanod/Desktop/my_ai_harness/skills/loader.py) et exposée via `GET /api/rag` avec indexation lexicale réelle et déclaration honnête `Non configuré` pour les embeddings vectoriels.

---

## 12. Architecture de l'interface utilisateur minimaliste (Addendum Final)

1. **Mode Clair par défaut (`data-theme="light"`)** : Palette pierre chaude (`--bg-primary: #F6F5F0`, `--bg-secondary: #EFECE6`, `--bg-surface: #FFFFFF`, `--text-primary: #181816`, `--accent: #2563EB`) au premier lancement, avec bascule Mode Sombre persistée dans `localStorage`.
2. **Palette flottante des Slash Commands (`#slash-command-palette`)** : S'ouvre immédiatement au-dessus du compositeur dès la saisie de `/` au début du champ ou après un espace (sans s'ouvrir dans une URL ou un chemin de fichier), affiche les 18 skills numérotés de `1.` à `18.`, filtre en temps réel, gère `↑`, `↓`, `Entrée`, `Tab`, `Échap` et clic souris.
3. **Panneau latéral droit unifié (`#right-inspector`)** :
   - **Mode Aperçu Document (`#doc-preview-container`)** :
     - **PDF (Tectonic)** : Affiche le PDF compilé (`#doc-pdf-frame`), le nom du fichier, le nombre de pages, la taille, les contrôles de zoom (`-`, `100%`, `+`), la bascule `Aperçu` / `Source .tex`, le bouton `⚡ Compiler` (recompilation Tectonic en direct), le téléchargement, le plein écran et la fermeture.
     - **HTML Sandboxé** : Affiche le rendu HTML dans `<iframe id="doc-html-frame" sandbox="allow-scripts">` servi par `/api/preview/workspace/<path>` (avec rejet `403 Forbidden` sur `Origin: null` dans `do_POST`), bascule `Aperçu` / `Code source` avec édition et sauvegarde en direct (`💾 Enregistrer`), rafraîchissement, téléchargement et plein écran.
   - **Mode Inspecteur Technique (`#inspector-tech-container`)** : Onglets `Modèle`, `Skills`, `Activité`, `Fichiers & Diff`, `Outils`, `Mémoire`, `RAG`, `Contexte`.
4. **Dictée vocale style GPT (`#voice-dictation-bar`)** : Bouton microphone `#btn-voice-dictate`, barre d'enregistrement avec annulation (`✕`), onde audio `<canvas id="voice-waveform-canvas">` pilotée par les fréquences réelles du microphone (`AnalyserNode`), compteur temporel, aperçu de transcription en direct et validation (`✓ Terminer`) insérant le texte dans le compositeur sans envoi automatique.

---

## 13. Système d'événements et streaming SSE temps réel

`NormalizedEventBus` ([core/event_bus.py](file:///c:/Users/nanod/Desktop/my_ai_harness/core/event_bus.py)) diffuse en SSE (`/api/events/stream`) tous les événements du cycle de vie ainsi que `STREAM_DELTA` (streaming token par token) et `ARTIFACT_READY` (ouverture automatique de l'aperçu PDF/HTML).

---

## 14. Dépendances et bibliothèques

- Python : `pyyaml`, `mistralai`, `pypdf`, `google-genai`.
- Binaire système LaTeX : **Tectonic** (`C:\ProgramData\chocolatey\bin\tectonic.EXE`, v0.3.2).
- Frontend : HTML5, CSS3, JavaScript ES2022, KaTeX 0.16.11, Web Audio API, Web Speech API.

---

## 15. Configuration et variables d'environnement

Configurables via le bouton `⚙` de la Top Bar (`POST /api/credentials`), `.env` ou variables d'environnement (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `MISTRAL_API_KEY`).

---

## 16. Flux de données (Data Flow)

- **Exécution de tâche** : `Composer UI` -> `POST /api/tasks/run` -> `NeoHarnessRuntimeBridge.execute_task()` -> `Orchestrator.run_agentic()` -> `AgentLoop.run()` -> ` STREAM_DELTA` -> `_collect_and_compile_task_artifacts()` (Tectonic / HTML) -> `ARTIFACT_READY` -> `Aperçu Document à droite`.

---

## 17. Carte des dépendances entre fichiers

- `main.py` assemble `core/*`, `providers/*`, `agents/*`, `skills/*`, `tools/*` et lance `ui/server.py`.
- `ui/server.py` expose `/api/state`, `/api/tasks/run`, `/api/files/raw`, `/api/files/pdf-info`, `/api/files/compile-latex`, `/api/files/write`, `/api/preview/workspace/<path>` et `/api/events/stream`.

---

## 18. Guide « Où modifier quoi ? »

- **Normalisation des tâches** : `core/task.py:ensure_task`.
- **Compilation PDF Tectonic & auto-réparation LaTeX** : `tools/documents.py:compile_latex` et `_repair_latex_source`.
- **Palette Slash Commands, Dictée Vocale & Aperçu PDF/HTML** : `ui/static/index.html`, `ui/static/styles.css`, `ui/static/app.js`.

---

## 19. Guide de démarrage et de lecture du code

```powershell
# Lancer le serveur web NeoHarness AI sur http://127.0.0.1:8765
python main.py --ui --port 8765

# Lancer la suite complète de 125 tests
python -B -m unittest discover -s tests -t . -v
```

---

## 20. Tests et validation (125 tests)

La suite complète comporte **125 tests automatisés** (`Ran 125 tests in 33.342s — OK`), incluant les tests de régression `test_27` à `test_31` pour l'Addendum Final Prioritaire.

---

## 21. Journal des modifications de la refonte et de l'Addendum Final

1. **Correction définitive de `AttributeError: 'str' object has no attribute 'description'`** : Ajout de `ensure_task()` dans `core/task.py` et normalisation aux frontières de `Planner`, `Orchestrator`, `Agent`, `AgentLoop` et `TaskState`, correction de `state.target_paths` dans `core/agent_loop.py:331` et retour explicite de `AgentResult` dans `skills/{auto,route,workflow}/command.py`.
2. **Fallback automatique Gemini Free Tier sur `google_search` 429** : Bascule transparente vers `function_declarations` (`web_search`) dans `providers/gemini.py` et `core/agent_loop.py`.
3. **Palette immédiate des 18 Slash Commands (`/`)** : Ordre canonique `1..18` dans `skills/registry.py`, `core/skill_compatibility.py` et `#slash-command-palette` dans `ui/static/*`.
4. **Compilation PDF Tectonic & Aperçu HTML Sandboxé à droite** : Implémentation de `compile_latex` via Tectonic avec auto-réparation dans `tools/documents.py`, routes `/api/files/compile-latex`, `/api/files/pdf-info`, `/api/files/raw`, `/api/preview/workspace/<path>` dans `ui/server.py`, et panneau `#doc-preview-container` dans `ui/static/*`.
5. **Mode Clair par défaut & Dictée Vocale style GPT** : Thème clair pierre chaude par défaut (`data-theme="light"`) et dictée vocale `#voice-dictation-bar` avec onde audio réelle `AnalyserNode` et `SpeechRecognition`.

---

## 22. Risques connus et limites actuelles

- **`ClaudeProvider`** (`providers/claude.py`) reste un adaptateur squelette non connecté (signalé explicitement comme `Non connecté`).
- **Reconnaissance vocale du navigateur (`SpeechRecognition`)** : Dépend du support Web Speech API du navigateur utilisé (Chrome/Edge sur Windows prennent en charge `webkitSpeechRecognition` ; en cas d'indisponibilité ou de refus de permission micro, un diagnostic explicite est affiché).

---

## 23. Feuille de route technique (Roadmap)

- Connexion native de `ClaudeProvider` à l'API Anthropic Messages.
- Persistance disque SQLite optionnelle pour `MemoryManager`.
