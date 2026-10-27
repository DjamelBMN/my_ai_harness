Voici le document NEOHARNESS_ARCHITECTURE.md complet et intégralement mis à
jour, prêt à être copié-collé pour remplacer le fichier existant à la racine de
ton projet :

# NEOHARNESS_ARCHITECTURE.md — Documentation Technique et Architecture Complète de NeoHarness AI

> **Créateur & Architecte : Djamel BENMAKHLOUF**
> **Document de référence d'architecture, de fonctionnement interne et de maintenance de NeoHarness AI**
> Ce document reflète **strictement l'état réel du dépôt** vérifié fichier par fichier et par exécution directe, sans inventer de composant, de modèle, de skill ou d'outil inexistant.

---

## Table des matières

- [NEOHARNESS\_ARCHITECTURE.md — Documentation Technique et Architecture Complète de NeoHarness AI](#neoharness_architecturemd--documentation-technique-et-architecture-complète-de-neoharness-ai)
  - [Table des matières](#table-des-matières)
  - [1. Vue d'ensemble du projet](#1-vue-densemble-du-projet)
    - [1.1 Qu'est-ce que NeoHarness AI ?](#11-quest-ce-que-neoharness-ai-)
    - [1.2 Philosophie : « Complexité cachée. Fonctionnalités 100 % réelles. Zéro simulation. Sécurité proportionnée. »](#12-philosophie---complexité-cachée-fonctionnalités-100--réelles-zéro-simulation-sécurité-proportionnée-)
  - [2. Arborescence complète finale](#2-arborescence-complète-finale)
- [Lancer le serveur web NeoHarness AI (en ignorant les anciens caches .pyc)](#lancer-le-serveur-web-neoharness-ai-en-ignorant-les-anciens-caches-pyc)
- [Lancer les tests de l'agent opérateur Windows (Computer Use, HITL, Policy Engine, Terminal)](#lancer-les-tests-de-lagent-opérateur-windows-computer-use-hitl-policy-engine-terminal)
- [Lancer les suites de validation du noyau, des skills et de l'interface UI](#lancer-les-suites-de-validation-du-noyau-des-skills-et-de-linterface-ui)

---

## 1. Vue d'ensemble du projet

### 1.1 Qu'est-ce que NeoHarness AI ?
**NeoHarness AI** est un **harness agentique multi-modèles, multi-agents et opérateur Windows en boucle fermée (Computer Use)** écrit en Python, doté à la fois :
- d'une interface **CLI interactive** complète (`python main.py`),
- et d'une **interface web minimaliste d'environnement opératoire IA** (`python -B main.py --ui --port 8765`), bâtie sans dépendance externe lourde (serveur HTTP/SSE natif Python + interface HTML5/CSS3/JS épurée avec KaTeX, MathJax, Web Audio API et aperçu documentaire multi-formats).

### 1.2 Philosophie : « Complexité cachée. Fonctionnalités 100 % réelles. Zéro simulation. Sécurité proportionnée. »
NeoHarness AI combine :
- un **Mode Clair raffiné par défaut** (`data-theme="light"`, palette pierre chaude `#F6F5F0` / `#EFECE6` / `#FFFFFF`) avec bascule instantanée vers le Mode Sombre (`data-theme="dark"`, `#0B0D10`) persistée dans `localStorage` ;
- une **palette flottante immédiate des Slash Commands (`/`)** dans l'ordre canonique strict qui s'ouvre dès la saisie de `/` au début du compositeur ou après un espace ;
- un **panneau latéral droit unifié (`#right-inspector`)**, fermé par défaut, capable d'afficher soit l'**Aperçu de Document** (**PDF compilé réellement avec Tectonic**, **Document Word `.docx` converti via Pandoc** ou **HTML interactif dans un `<iframe>` sandboxé**) soit l'**Inspecteur Technique**, sans jamais ouvrir une troisième colonne ;
- une **dictée vocale style GPT** dans le compositeur utilisant de vraies données d'amplitude microphone (`navigator.mediaDevices.getUserMedia` + `AudioContext` + `AnalyserNode`) et la transcription vocale réelle (`SpeechRecognition` / `webkitSpeechRecognition`) ;
- un **moteur d'agent opérateur Windows en boucle fermée (`Perception → Action → Observation → Vérification`)** contrôlé par un **Tool Gateway** central (`core/tool_gateway.py`), un **Policy Engine** déclaratif (`core/policy_engine.py`) et une validation **Human-In-The-Loop (HITL)** proportionnée au risque (`SAFE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, `BLOCKED`) ;
- un **principe UX de proportionnalité stricte** : les actions simples et sûres (ex: prendre une capture d'écran et la poser sur le Bureau Windows, lister les fenêtres, copier dans le presse-papiers) s'exécutent directement via leur outil natif spécialisé en un minimum d'étapes, sans script Python intermédiaire ni confirmation bureaucratique inutile.

---

## 2. Arborescence complète finale

```text
my_ai_harness/
├── .gitignore                        # Règles d'exclusion Git (.env, __pycache__, etc.)
├── README.md                         # Présentation rapide et commandes de base
├── NEOHARNESS_ARCHITECTURE.md        # Documentation technique complète (ce document)
├── NEOHARNESS_ARTIFACT_ENGINE.md     # Documentation du moteur universel d'artefacts
├── NEOHARNESS_RUNTIME_VALIDATION.md  # Rapport de vérification runtime réelle de bout en bout
├── requirements.txt                  # Dépendances Python (openai, google-genai, mistralai, Pillow, pytesseract, PyMuPDF, pypdf, PyYAML, prompt-toolkit)
├── main.py                           # Point d'entrée principal CLI et lanceur UI (--ui)
│
├── config/
│   ├── config.yaml                   # Configuration centrale (providers, profils rate-limit, agents, routes, feature flags)
│   └── custom_models.json            # Modèles LLM personnalisés ajoutés dynamiquement sans mise à jour
│
├── agents/
│   ├── __init__.py                   # Package des agents spécialisés
│   ├── coder.py                      # CodeAgent : développement, édition de fichiers, refactoring et pilotage Computer Use Windows
│   ├── researcher.py                 # ResearchAgent : recherche locale et Internet, récupération et génération documentaire
│   ├── reviewer.py                   # ReviewAgent & IndependentCritic : revue critique sur contexte vierge, audit qualité et risques
│   └── tester.py                     # TestAgent : exécution et validation déterministe des suites de tests
│
├── core/
│   ├── __init__.py                   # Package du noyau d'orchestration
│   ├── agent.py                      # Classe de base Agent (directive d'identité, directive opérateur Windows, ensure_task)
│   ├── agent_loop.py                 # Boucle d'exécution agentique fermée (tools, web_search, streaming, auto-réparation, vérification)
│   ├── agent_registry.py             # Registre des agents disponibles (AgentRegistry)
│   ├── agent_selector.py             # Sélection d'agent par scoring de capacités et d'intentions (AgentSelector)
│   ├── artifact_intent.py            # Détection d'intention d'artefact, classification d'origine et conformité de livrable
│   ├── checkpoint.py                 # Points de reprise et backtracking (Shadow Git / snapshots)
│   ├── context.py                    # Historique d'interactions léger et mémoire de mission (Context)
│   ├── context_manager.py            # Gestionnaire de contexte workspace et budget de tokens (ContextManager)
│   ├── dag_engine.py                 # Moteur d'exécution de graphes multi-agents acycliques (DAGEngine)
│   ├── delegation.py                 # Délégation contrôlée de sous-tâches et graphes DAG entre agents (DelegationEngine)
│   ├── event_bus.py                  # Bus d'événements normalisés temps réel et SSE (NormalizedEventBus)
│   ├── events.py                     # Événements bas niveau du runtime et traducteur français (HarnessEvent, EventTranslator)
│   ├── intent_engine.py              # Moteur de classification d'intention (coding, testing, research, computer_use, etc.)
│   ├── library.py                    # Bibliothèque intelligente persistante (LibraryManager, .harness/library.json)
│   ├── mcp_client.py                 # Client MCP JSON-RPC 2.0 stdio (MCPStdioClient, MCPClientManager) raccordé au ToolGateway
│   ├── memory.py                     # Mémoire persistante cross-session, leçons expérientielles & injection prompt (MemoryManager, ReflectiveMemory)
│   ├── metrics_sink.py               # Collecteur de métriques d'exécution
│   ├── model_registry.py             # Registre vérifié des Providers, Modèles et Capabilities (ModelCapabilityRegistry)
│   ├── modes.py                      # Modes d'exécution globaux (EDIT, PLAN, ACCEPT, AUTO)
│   ├── multi_agent_coordinator.py    # Coordination séquentielle et hiérarchique multi-agents (MultiAgentCoordinator)
│   ├── orchestrator.py               # Orchestrateur central (Orchestrator, run, run_agentic)
│   ├── permissions.py                # Politique de permissions (PermissionPolicy, RiskLevel, PermissionLevel STRICT/SESSION/AUTOMATIC, format_hitl_box)
│   ├── planner.py                    # Planificateur d'étapes minimalistes et observations initiales (Planner, PlanStep)
│   ├── policy_engine.py              # Moteur de sécurité (PolicyEngine, PolicyEvaluation, SAFE/LOW/MEDIUM/HIGH/CRITICAL/BLOCKED)
│   ├── rate_limit_manager.py         # Gestionnaire de concurrence LLM, backoff, retry et circuit breaker (RateLimitManager)
│   ├── replay.py                     # Rejeu déterministe de missions enregistrées (replay_mission)
│   ├── router.py                     # Routeur de modèles par agent, intention, complexité et failover (ModelRouter)
│   ├── self_audit.py                 # Télémétrie, auto-audit et benchmark interne (TelemetryStore)
│   ├── skill_compatibility.py        # Moteur de compatibilité Provider -> Model -> Capabilities -> Skills
│   ├── task.py                       # Contrat de tâche (Task) et normalisateur strict ensure_task()
│   ├── task_context.py               # Continuité multi-tours par conversation (TaskContext)
│   ├── task_state.py                 # État riche d'exécution d'une tâche (TaskState, PlanStep, AgentResult)
│   ├── tdd_engine.py                 # Moteur TDD en boucle fermée et scellement SHA-256 des tests (TestTamperingError)
│   ├── title_generator.py            # Générateur intelligent de titres de tâches
│   ├── tool_gateway.py               # Couche centrale Tool Gateway & journal d'observabilité (.harness/operator_audit.jsonl)
│   ├── verifier.py                   # Vérificateur final déterministe (fichiers, tests, provenance Web, boucle fermée Computer Use)
│   └── artifacts/
│       ├── __init__.py
│       ├── engine.py                 # UniversalArtifactEngine (cycle de vie multi-formats, versions, rollback)
│       ├── handlers.py               # Handlers de validation/compilation par type d'artefact
│       ├── models.py                 # Modèles de données d'artefacts (Artifact, ArtifactStatus, ArtifactType)
│       ├── provenance.py             # Chaîne de provenance cryptographique des téléchargements (ProvenanceLedger)
│       └── verifier.py               # Vérificateur physique d'artefacts (magic bytes, structure)
│
├── providers/
│   ├── __init__.py                   # Package des adaptateurs de fournisseurs LLM
│   ├── base_provider.py              # Contrat abstrait BaseProvider, AgentTurn et ProviderToolCall
│   ├── claude.py                     # ClaudeProvider (squelette non connecté par défaut)
│   ├── gemini.py                     # GeminiProvider (API Google Gemini native, streaming, fallback quota 429 google_search -> web_search)
│   ├── local.py                      # LocalProvider (fournisseur local déterministe pour tests hors-ligne)
│   ├── mistral.py                    # MistralProvider (SDK mistralai + client HTTP)
│   ├── ollama.py                     # OllamaProvider (exécution locale via serveur HTTP Ollama)
│   └── openai.py                     # OpenAIProvider (API OpenAI Responses / Chat Completions)
│
├── skills/
│   ├── __init__.py                   # Export public du système de Skills
│   ├── loader.py                     # Chargement dynamique des dossiers de Skills, commandes, agents, RAG et templates
│   ├── registry.py                   # Registre central des Skills dans l'ordre canonique
│   ├── router.py                     # Routage automatique par mots-clés, triggers et commandes slash (SkillRouter)
│   ├── runtime.py                    # Exécution des commandes slash et état de session (SkillRuntime)
│   ├── education/                    # Skills éducatifs spécialisés (bacblanc, dm, exercice) avec RAG et templates LaTeX officiels
│   └── <dossiers de skills>/         # analyze, auto, compare, context, debug, diagnostic, export, memory,
│                                     # mode, model, plan, refactor, research, review, route, test, workflow
│
├── tools/
│   ├── __init__.py                   # Package des outils (Tools)
│   ├── browser.py                    # Navigateur dynamique Playwright Chromium avec conformité robots.txt et repli statique (DynamicBrowser)
│   ├── clipboard.py                  # Presse-papiers Windows natif Win32 Unicode (clipboard_get, clipboard_set)
│   ├── code_search.py                # Recherche de code par regex rapide (search_code)
│   ├── compiler.py                   # Compilateur autonome LaTeX avec auto-correction (AutonomousCompiler)
│   ├── computer_use.py               # Couche Computer Use Windows (screenshots, Bureau, diff d'écran, OCR, souris, clavier, boucle fermée)
│   ├── documents.py                  # Lecture documentaire (read_document) et compilation LaTeX/HTML (compile_latex, compile_html)
│   ├── docx.py                       # Génération et vérification physique de documents Word .docx via Pandoc (generate_docx)
│   ├── editor.py                     # Édition chirurgicale de fichiers avec validation syntaxique (edit_file)
│   ├── filesystem.py                 # Opérations fichiers confinées dans workspace/ (WorkspaceFilesystem)
│   ├── git.py                        # Inspection et opérations Git (GitWorkspace)
│   ├── math_tikz.py                  # Génération déterministe de tableaux de variations, arbres et courbes TikZ/pgfplots
│   ├── process_manager.py            # Gestionnaire de processus Windows (process_list, process_start, process_status, process_stop)
│   ├── process_utils.py              # Environnement de sous-processus nettoyé des secrets API (safe_subprocess_environment)
│   ├── python_runtime.py             # Exécution Python headless avec capture automatique des figures Matplotlib
│   ├── rasterizer.py                 # Rastérisation de pages PDF en PNG pour inspection visuelle
│   ├── registry.py                   # Registre central des outils et intégration au ToolGateway (ToolRegistry)
│   ├── search.py                     # Recherche Internet réelle (web_search), fetch_url et téléchargement vérifié (download_resource)
│   ├── terminal.py                   # Exécution de tests (run_test_suite), scripts (run_python_script) et façade du terminal persistant
│   ├── terminal_session.py           # Terminal interactif persistant Windows PowerShell/CMD/ConPTY (PersistentTerminalManager)
│   ├── viewer.py                     # Lecture fenêtrée de fichiers avec numéros de lignes (view_file)
│   ├── vision.py                     # Transcription OCR multi-passes fidèle avec marquage [illisible] (transcribe_image)
│   └── windows.py                    # Contrôle natif Win32 des fenêtres Windows (window_list, window_active, window_find, window_focus, etc.)
│
├── ui/
│   ├── __init__.py                   # Package de l'interface web
│   ├── server.py                     # Pont runtime (NeoHarnessRuntimeBridge) + serveur HTTP REST, SSE, HITL & aperçu PDF/DOCX/HTML
│   └── static/
│       ├── index.html                # Interface Mode Clair par défaut, Palette Slash (/), Dictée Vocale GPT, Panneau Aperçu
│       ├── styles.css                # Design system pierre chaude (#F6F5F0) / sombre (#0B0D10)
│       └── app.js                    # Logique client réactive (SSE, HITL proportionné, Slash Palette, Web Audio, KaTeX, Aperçu)
│
├── docs/                             # Documentation spécialisée (ARCHITECTURE.md, AUDIT.md, EVALS.md, SECURITY.md, VISION.md)
├── evals/                            # Suite de benchmarks et d'évaluation automatisée (runner.py, tasks.py)
├── runtime/pandoc/                   # Binaire Pandoc embarqué (pandoc.exe) pour génération Word .docx / OMML
├── tests/                            # Suites complètes de tests unitaires, d'intégration et E2E (dont test_windows_computer_use_agent.py)
└── workspace/                        # Répertoire de travail isolé pour les opérations fichiers et livrables des agents

3. Description détaillée fichier par fichier

3.1 Entrée et Normalisation des Contrats (core/task.py, core/planner.py, core/orchestrator.py, core/agent_loop.py)

  - core/task.py : Définit Task et la fonction frontière ensure_task(task: Task
    | str, ...) qui convertit de manière déterministe toute chaîne brute en
    instance Task typée.
  - core/task_state.py : Normalise dans TaskState.__post_init__ tout élément de
    self.plan en instance PlanStep et trace l'historique complet des outils,
    sources et vérifications.
  - core/planner.py, core/orchestrator.py, core/agent.py, core/agent_loop.py :
    Appliquent ensure_task(...) dès l'entrée, injectent la directive d'identité
    NeoHarness AI et la directive d'Agent Opérateur Windows, et exécutent la
    boucle fermée d'action et de vérification.

3.2 Sécurité, Gouvernance & Tool Gateway (core/policy_engine.py, core/permissions.py, core/tool_gateway.py, core/mcp_client.py)

  - core/policy_engine.py : Évalue dynamiquement chaque appel d'outil (nom +
    arguments) pour déterminer son action canonique (filesystem.read,
    filesystem.write, filesystem.delete_many, process.start, package.install,
    registry.modify, system.shutdown, computer_use.*, terminal.*, etc.), son
    niveau de risque (SAFE, LOW, MEDIUM, HIGH, CRITICAL, BLOCKED), sa
    description humaine en français et l'éligibilité à l'approbation de session
    (allow_session_approval = False pour HIGH, CRITICAL et BLOCKED). Bloque
    strictement toute tentative de contournement UAC, de désactivation de
    Windows Defender ou d'extraction de secrets système.
  - core/permissions.py : Implémente PermissionPolicy, RiskLevel et
    PermissionLevel (STRICT, SESSION, AUTOMATIC). Applique le principe de
    proportionnalité UX : les lectures (SAFE) et les actions opérateur simples à
    faible risque (computer_screenshot, copy_to_desktop, clipboard_set,
    window_focus, window_minimize, window_maximize, window_restore,
    terminal_start, terminal_stop) s'exécutent directement sans popup
    bureaucratique (hors mode STRICT), tandis que les actions MEDIUM
    (process_start, terminal_send, clics/clavier computer_*) et HIGH/CRITICAL
    déclenchent une validation Human-In-The-Loop adaptée.
  - core/tool_gateway.py : Point de passage unique entre les agents et les
    outils. Regroupe les outils selon 11 domaines (filesystem, terminal,
    computer_use, windows, process, clipboard, browser, git, search, documents,
    mcp) et enregistre chaque étape horodatée (AGENT_CALL, POLICY, HITL,
    VERIFICATION) en mémoire et dans workspace/.harness/operator_audit.jsonl.
  - core/mcp_client.py : Client JSON-RPC 2.0 stdio permettant de connecter des
    serveurs MCP externes et d'exposer leurs outils dans le ToolGateway sous le
    contrôle du PolicyEngine.

3.3 Couche Opérateur Windows & Computer Use (tools/computer_use.py, tools/windows.py, tools/terminal_session.py, tools/process_manager.py, tools/clipboard.py)

  - tools/computer_use.py :
      - computer_screenshot : capture l'écran actif (ou une région) via
        PIL.ImageGrab, résout le vrai Bureau Windows via l'API Win32
        SHGetFolderPathW(CSIDL_DESKTOPDIRECTORY) (compatible Bureau local et
        OneDrive Bureau), et sauvegarde directement sur le Bureau lorsque
        save_to_desktop=True.
      - copy_to_desktop : copie nativement tout fichier ou capture du workspace
        vers le Bureau Windows sans script Python intermédiaire.
      - computer_ocr : extrait le texte à l'écran via pytesseract avec les
        coordonnées (x, y) du centre de chaque mot pour permettre un clic
        précis.
      - computer_compare_screens : compare deux captures avant/après via
        PIL.ImageChops.difference et calcule le diff_ratio, le nombre de pixels
        modifiés et la boîte englobante du changement.
      - computer_mouse_move, computer_click, computer_drag, computer_scroll,
        computer_type, computer_press, computer_hotkey : pilotage souris/clavier
        via l'API Win32 user32 avec Fail-Safe d'urgence au coin (0, 0).
      - computer_action_verified : exécute une action GUI en boucle fermée
        (Screenshot Avant → Action → Pause de stabilisation → Screenshot Après →
        Comparaison d'écran & Vérification de la fenêtre attendue).
  - tools/windows.py : Enumération et contrôle des fenêtres Windows via
    ctypes.windll.user32 (window_list, window_active, window_find, window_focus,
    window_minimize, window_maximize, window_restore, window_close).
  - tools/terminal_session.py : Sessions persistantes PowerShell (powershell.exe
    -NoLogo -NoProfile -NoExit -Command -) et CMD (cmd.exe /Q /K) avec support
    ConPTY optionnel (pywinpty), threads de lecture non-bloquants stdout/stderr,
    marqueur de fin d'exécution instantané (__NEOHARNESS_CMD_DONE__), détection
    de prompts interactifs et maintien des serveurs de développement (npm run
    dev) en arrière-plan.
  - tools/process_manager.py : Inspection et gestion des processus Windows
    (process_list, process_start avec vérification de survie post-démarrage,
    process_status, process_stop).
  - tools/clipboard.py : Lecture et écriture native du presse-papiers Windows en
    Unicode (CF_UNICODETEXT) via user32 / kernel32 (clipboard_get,
    clipboard_set).

4. Fonctionnement global de bout en bout

┌────────────────────────────────────────────────────────────────────────────────────────┐
│            UTILISATEUR (Interface Web Mode Clair par défaut ou CLI)                    │
│   Palette Slash (/) │ Dictée Vocale GPT │ Bannière HITL │ Aperçu PDF/DOCX/HTML         │
└───────────────────┬────────────────────────────────────────────────────▲───────────────┘
                    │ 1. Demande utilisateur                             │ 9. Flux SSE
                    ▼                                                    │ & Livrables
┌────────────────────────────────────────────────────────────────────────┴───────────────┐
│                   PONT D'EXÉCUTION : NeoHarnessRuntimeBridge (ui/server.py)            │
│   • IntentEngine & Planner : détection d'intention et construction du plan minimal     │
│   • Orchestrator & AgentLoop : sélection de l'agent et boucle fermée d'exécution       │
│   • ToolGateway & PolicyEngine : évaluation du risque (SAFE/LOW/MEDIUM/HIGH/CRITICAL)  │
│   • HITL proportionné : exécution directe si SAFE/LOW, validation humaine si sensible  │
│   • Action Windows / Workspace -> Observation post-action -> Verifier déterministe     │
└────────────────────────────────────────────────────────────────────────────────────────┘

5. Cycle de vie complet d'une requête

1.  Saisie ou Dictée Vocale : L'utilisateur saisit sa demande, utilise / pour
    sélectionner un skill, ou dicte sa demande au microphone.
2.  Classification d'Intention & Planification Minimale : IntentEngine.decide()
    identifie l'intention (coding, testing, research, file_analysis,
    exam_creation, document_generation, computer_use, general_question) et
    sélectionne uniquement les outils natifs pertinents. Planner.plan() génère
    le plan le plus court suffisant (3 étapes pour une action opérateur simple).
3.  Perception Initiale Automatique : Pour une tâche sur fichiers ou une tâche
    simple de capture/fenêtres Windows, Planner.initial_observation_tools()
    exécute immédiatement l'outil natif d'observation (computer_screenshot,
    window_list, read_document). Si l'action simple demandée (ex: capture
    d'écran posée sur le Bureau) est déjà accomplie et vérifiée par cette étape,
    l'agent répond dès le premier tour sans appel redondant.
4.  Passage par le Tool Gateway, le Policy Engine et le HITL : Chaque appel
    d'outil est évalué par PolicyEngine.evaluate(). Les actions SAFE et LOW
    s'exécutent sans friction ; les actions MEDIUM proposent [ Refuser ], [
    Autoriser ], [ Autoriser pour cette session ] ; les actions HIGH et CRITICAL
    proposent uniquement [ Refuser ] et [ Autoriser une fois ] ; les actions
    BLOCKED sont rejetées.
5.  Boucle Fermée & Vérification Déterministe : Après l'action,
    Verifier.verify() contrôle les preuves physiques (hash SHA-256 des fichiers,
    code retour des tests, chaîne de provenance Web, ou verified == True sur la
    boucle fermée Computer Use). En cas d'action sans effet, AgentLoop injecte
    un conseil d'auto-réparation ciblé.

6. Fonctionnement détaillé du Model Router & Streaming

| ID Modèle           | Classe Provider                            | Modèle configuré (`config.yaml`) | État de connexion                         | Capacités principales                                                                              |
| :------------------ | :----------------------------------------- | :------------------------------- | :---------------------------------------- | :------------------------------------------------------------------------------------------------- |
| `gemini`            | `GeminiProvider` (`providers/gemini.py`)   | `gemini-3.5-flash-lite`          | **Connecté** (`GEMINI_API_KEY`)           | Vision, Long Context, Function Calling, Web Search, Streaming temps réel                           |
| `gemini_flash_lite` | `GeminiProvider` (`providers/gemini.py`)   | `gemini-3.5-flash-lite`          | **Connecté** (`GEMINI_API_KEY`)           | Vision, Long Context, Function Calling, Web Search (fallback auto `web_search` sur 429), Streaming |
| `openai`            | `OpenAIProvider` (`providers/openai.py`)   | `gpt-5-mini`                     | Actif si `OPENAI_API_KEY` présente        | Vision, Long Context, Function Calling, `web_search`, Reasoning                                    |
| `mistral`           | `MistralProvider` (`providers/mistral.py`) | `mistral-small-latest`           | Actif si `MISTRAL_API_KEY` présente       | Function Calling, `web_search`, Structured Output                                                  |
| `ollama`            | `OllamaProvider` (`providers/ollama.py`)   | `qwen3:1.7b`                     | **Connecté en local** (`127.0.0.1:11434`) | Exécution locale, Function Calling JSON, `web_search`                                              |
| `claude`            | `ClaudeProvider` (`providers/claude.py`)   | `claude-sonnet-4`                | **Non connecté** (squelette)              | Signalé honnêtement comme indisponible                                                             |

6.1 Extensibilité des Modèles LLM Personnalisés (config/custom_models.json)

Tout utilisateur peut ajouter dynamiquement un modèle LLM via la modale
#modal-add-custom-model (POST /api/models/custom/add), persisté dans
config/custom_models.json.

7. Architecture complète des Skills (Ordre Canonique & Éducation)

Les Skills chargés par SkillRegistry (skills/registry.py) couvrent les commandes
générales et les skills éducatifs spécialisés :

  - Skills généraux : /analyze, /auto, /compare, /context, /debug, /diagnostic,
    /export, /memory, /mode, /model, /plan, /refactor, /research, /review,
    /route, /test, /workflow.
  - Skills éducatifs (skills/education/) : /bacblanc, /dm, /exercice — équipés
    des programmes officiels de mathématiques en RAG et de gabarits LaTeX
    officiels compilés automatiquement via Tectonic.

8. Architecture des Agents

Les agents enregistrés dans AgentRegistry sont :

1.  CodeAgent (coder) : Programmation, débogage, édition de fichiers et pilotage
    de l'environnement Windows / Computer Use / Terminal.
2.  ResearchAgent (researcher) : Recherche locale et Web, récupération
    authentifiée de documents distants et génération Word .docx.
3.  ReviewAgent (reviewer) & IndependentCritic : Revue de code et audit critique
    sur contexte vierge.
4.  TestAgent (tester) : Exécution et diagnostic des suites de tests unitaires
    et de régression.
5.  BacBlancAgent (bacblanc) : Conception complète de sujets et barèmes LaTeX
    conformes aux programmes officiels.

9. Architecture Opérateur Windows : Tool Gateway, Computer Use, Policy Engine, HITL & Terminal Persistant

9.1 Les 11 domaines du Tool Gateway (core/tool_gateway.py)

Tous les appels d'outils passent par ToolGateway adossé à ToolRegistry
(tools/registry.py) :

  - filesystem : list_files, find_file, search_files, read_file, read_document,
    view_file, search_code, write_file, patch_file, edit_file, delete_file,
    move_file, copy_to_desktop.
  - computer_use : computer_screenshot (avec save_to_desktop), computer_ocr,
    computer_compare_screens, computer_mouse_move, computer_click,
    computer_drag, computer_scroll, computer_type, computer_press,
    computer_hotkey, computer_action_verified.
  - windows : window_list, window_active, window_find, window_focus,
    window_minimize, window_maximize, window_restore, window_close.
  - terminal : terminal_start, terminal_send, terminal_read, terminal_stop,
    terminal_list, run_tests.
  - process : process_list, process_start, process_status, process_stop,
    run_python.
  - clipboard : clipboard_get, clipboard_set.
  - browser : web_search, fetch_url, download_resource, navigate_url,
    click_element, fill_input, download_via_browser, screenshot_page.
  - git : git_status, git_current_branch, git_create_branch, git_commit_staged,
    git_merge.
  - documents : compile_document, generate_math_figure, generate_docx,
    transcribe_image.
  - mcp : outils externes enregistrés dynamiquement via MCPClientManager
    (core/mcp_client.py).

9.2 Classification des risques du Policy Engine (core/policy_engine.py)

| Niveau                         | Exemples d'actions canoniques et outils                                                                                                                                   | Comportement HITL (Mode standard `SESSION` / `ACCEPT`)                                                             |
| :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------------------------------------------------------------------------------------- |
| **`SAFE`** (`READ_ONLY`)       | `filesystem.read`, `computer_screenshot`, `computer_ocr`, `window_list`, `window_active`, `process_list`, `clipboard_get`, `terminal_read`                                | **Exécution directe** (0 confirmation)                                                                             |
| **`LOW`**                      | `copy_to_desktop`, `clipboard_set`, `window_focus`, `window_minimize`, `window_maximize`, `window_restore`, `terminal_start`, `terminal_stop`, `filesystem.write`         | **Exécution directe** pour les outils opérateur simples ; aperçu direct en mode `EDIT`                             |
| **`MEDIUM`** (`MODERATE`)      | `process.start` (`process_start`), `package.install`, `terminal.send` (`terminal_send`), `computer_click`, `computer_type`, `computer_hotkey`, `computer_action_verified` | **HITL standard** : `[ Refuser ]`, `[ Autoriser ]`, `[ Autoriser pour cette session ]`                             |
| **`HIGH`**                     | `filesystem.delete` (`delete_file`), `filesystem.delete_many`, `process.stop` (`process_stop`), `windows.close` (`window_close`), `registry.modify`                       | **HITL Action à risque** : uniquement `[ Refuser ]` ou `[ Autoriser une fois ]` (jamais d'autorisation de session) |
| **`CRITICAL`** (`DESTRUCTIVE`) | `system.shutdown` (`shutdown /s`, `Stop-Computer`, `Restart-Computer`, formatage)                                                                                         | **HITL Critique systématique** : uniquement `[ Refuser ]` ou `[ Autoriser une fois ]`                              |
| **`BLOCKED`**                  | Contournement UAC (`fodhelper`, `eventvwr`), désactivation Windows Defender (`Set-MpPreference`), extraction LSASS/SAM                                                    | **Blocage immédiat et inconditionnel** par le Policy Engine                                                        |

10. Architecture de la Mémoire Persistante & de la Bibliothèque Intelligente

  - Mémoire Persistante (core/memory.py) : Stockage cross-session dans
    workspace/.harness/persistent_memory.json (rule, preference, context,
    decision, knowledge) + mémoire réflexive expérientielle (ReflectiveMemory)
    enregistrant automatiquement les leçons de résolution d'erreurs.
  - Bibliothèque Intelligente (core/library.py) : Stockage dans
    workspace/.harness/library.json synchronisé avec le workspace, recherche
    temps réel, tags, épinglage et double liaison bidirectionnelle avec la
    mémoire.

11. Architecture du RAG

Implémentée dans skills/loader.py et exposée via GET /api/rag avec extraction
documentaire directe des dossiers rag/ et templates/ de chaque Skill ainsi que
des documents du workspace/.

12. Architecture de l'interface utilisateur minimaliste (Addendum Final)

1.  Mode Clair par défaut (data-theme="light") et bascule Mode Sombre persistée.
2.  Palette flottante des Slash Commands (#slash-command-palette) à l'ouverture
    de /.
3.  Bannière Human-In-The-Loop proportionnée (#approval-banner-container) :
    affiche l'intitulé précis de l'action (human_description), l'outil
    (category), le niveau de risque traduit (risk_label_fr) et masque
    automatiquement le bouton [ Autoriser pour cette session ] lorsque l'action
    est de niveau HIGH ou CRITICAL.
4.  Panneau latéral droit unifié (#right-inspector) : Mode Aperçu Document (PDF
    Tectonic, Word .docx Pandoc, HTML sandboxé, images, graphiques Python) et
    Mode Inspecteur Technique.
5.  Dictée vocale style GPT (#voice-dictation-bar) avec onde audio temps réel
    AnalyserNode.

13. Système d'événements, Observabilité et streaming SSE temps réel

  - NormalizedEventBus (core/event_bus.py) diffuse en SSE (/api/events/stream)
    tous les événements du cycle de vie (TASK_STARTED, PLAN_CREATED, TOOL_CALL,
    TOOL_RESULT, APPROVAL_REQUIRED, STREAM_DELTA, ARTIFACT_READY,
    TASK_COMPLETED).
  - ToolGateway (core/tool_gateway.py) écrit une trace d'audit horodatée
    complète dans workspace/.harness/operator_audit.jsonl permettant de retracer
    chaque appel Agent → Policy → HITL → Verification.

14. Dépendances et bibliothèques

  - Python (requirements.txt) : openai>=1.66.0, google-genai>=1.32.0,
    mistralai>=3.2.0, Brotli>=1.2.0, PyMuPDF>=1.24.0, pypdf>=4.0.0,
    openpyxl>=3.1.0, pytesseract>=0.3.10, Pillow>=10.0.0, PyYAML>=6.0,
    prompt-toolkit>=3.0.43,<4.0.
  - APIs Windows natives : ctypes.windll.user32, ctypes.windll.kernel32,
    ctypes.windll.shell32 (zéro dépendance C++ fragile pour le contrôle
    souris/clavier, les fenêtres, le presse-papiers et la résolution du Bureau).
  - Binaires documentaires : Tectonic (compilation LaTeX \rightarrow PDF) et
    Pandoc (runtime/pandoc/pandoc.exe pour la génération Word .docx).

15. Configuration et variables d'environnement

Configurables via le bouton Paramètres de la Top Bar (POST /api/credentials),
.env ou variables d'environnement (GEMINI_API_KEY, OPENAI_API_KEY,
MISTRAL_API_KEY, ANTHROPIC_API_KEY).

16. Flux de données (Data Flow)

Composer UI / CLI
  -> IntentEngine.decide() (sélectionne l'intention et les outils natifs strictement nécessaires)
  -> Planner.plan() (construit un plan court : 3 étapes pour une action opérateur simple)
  -> AgentLoop.run()
       ├── Perception initiale (computer_screenshot / window_list / read_document)
       ├── Appel du modèle actif (streaming SSE STREAM_DELTA)
       ├── ToolRegistry.execute() <-> ToolGateway
       │     ├── PolicyEngine.evaluate(tool, arguments)
       │     ├── PermissionPolicy.authorize() (direct si SAFE/LOW, HITL si MEDIUM/HIGH/CRITICAL)
       │     └── Exécution de l'outil natif Windows / Workspace + journalisation .jsonl
       └── Verifier.verify() (contrôle déterministe du résultat et de la boucle fermée)
  -> Livraison finale + ARTIFACT_READY SSE

17. Carte des dépendances entre fichiers

  - main.py et ui/server.py assemblent core/*, providers/*, agents/*, skills/*
    et tools/*.
  - tools/registry.py instancie ToolGateway (core/tool_gateway.py), qui s'appuie
    sur PolicyEngine (core/policy_engine.py) et PermissionPolicy
    (core/permissions.py).
  - tools/registry.py expose les outils de tools/filesystem.py,
    tools/computer_use.py, tools/windows.py, tools/terminal.py
    (tools/terminal_session.py), tools/process_manager.py, tools/clipboard.py,
    tools/browser.py, tools/documents.py, tools/docx.py, tools/vision.py et
    core/mcp_client.py.

18. Guide « Où modifier quoi ? »

  - Ajouter une règle de sécurité ou ajuster le risque d'une action :
    core/policy_engine.py (CANONICAL_ACTION_RISKS ou register_rule()).
  - Modifier le comportement HITL ou la liste des outils sans friction :
    core/permissions.py (_LOW_FRICTION_OPERATOR_TOOLS, authorize(),
    format_hitl_box()).
  - Modifier les actions souris/clavier, la capture d'écran ou la boucle fermée
    GUI : tools/computer_use.py et tools/windows.py.
  - Modifier le terminal interactif persistant PowerShell / CMD :
    tools/terminal_session.py et tools/terminal.py.
  - Connecter un serveur MCP externe : core/mcp_client.py
    (MCPClientManager.register_server()).
  - Ajuster la détection d'intention ou le plan minimal : core/intent_engine.py
    et core/planner.py.

19. Guide de démarrage et de lecture du code

# Lancer le serveur web NeoHarness AI (en ignorant les anciens caches .pyc)
python -B main.py --ui --port 8765

# Lancer les tests de l'agent opérateur Windows (Computer Use, HITL, Policy Engine, Terminal)
python -B -m unittest tests/test_windows_computer_use_agent.py -v

# Lancer les suites de validation du noyau, des skills et de l'interface UI
python -B -m unittest tests/test_runtime.py tests/test_skills.py tests/test_general_skills.py tests/test_multi_agent_runtime.py tests/test_ui_environment.py tests/test_windows_computer_use_agent.py -v

20. Tests et validation

La validation automatisée couvre :

  - tests/test_windows_computer_use_agent.py (15 tests) :
      - Classification PolicyEngine (SAFE, LOW, MEDIUM, HIGH, CRITICAL) et
        blocage des actions interdites (BLOCKED : UAC, Windows Defender, LSASS)
        ;
      - Règles personnalisées du PolicyEngine ;
      - Workflow HITL complet (autorisation ponctuelle, refus, permission de
        session, interdiction d'autorisation de session sur risque
        HIGH/CRITICAL, retour au mode STRICT, timeout UI) ;
      - ToolGateway et journalisation d'observabilité dans
        .harness/operator_audit.jsonl ;
      - Computer Use : capture d'écran, sauvegarde Bureau, comparaison visuelle
        avant/après (computer_compare_screens), validation des coordonnées,
        Fail-Safe (0, 0), et boucle fermée computer_action_verified ;
      - PersistentTerminalSession (persistance des variables d'environnement
        entre commandes PowerShell et fermeture propre sans ResourceWarning),
        ProcessManager, Windows et Clipboard ;
      - Récupération E2E de AgentLoop + Verifier après un clic sans effet.
  - tests/test_ui_environment.py (32 tests), tests/test_general_skills.py,
    tests/test_multi_agent_runtime.py, tests/test_skills.py,
    tests/test_runtime.py : Validation complète de non-régression du runtime et
    de l'interface.

21. Journal des modifications architecturales

1.  Architecture Agent Opérateur Windows & Computer Use en boucle fermée :
    Création de core/policy_engine.py, core/tool_gateway.py, core/mcp_client.py,
    tools/computer_use.py, tools/windows.py, tools/terminal_session.py,
    tools/process_manager.py, tools/clipboard.py et
    tests/test_windows_computer_use_agent.py.
2.  Principe UX de Proportionnalité & Exécution Directe des Actions Simples :
      - Ajout de save_to_desktop sur computer_screenshot et de l'outil natif
        copy_to_desktop avec détection Win32 du dossier Bureau réel.
      - Exécution directe sans confirmation bureaucratique pour les actions SAFE
        et LOW non destructives (_LOW_FRICTION_OPERATOR_TOOLS).
      - Planification minimale en 3 étapes pour les missions computer_use et
        hiérarchie stricte privilégiant les outils natifs spécialisés sur
        l'écriture de scripts Python temporaires.
3.  Terminal PowerShell Persistant Instantané : Détection immédiate de fin de
    commande par sentinelle (__NEOHARNESS_DONE__) et bascule automatique vers la
    racine du projet lorsque la commande cible tests/ ou main.py.

22. Risques connus et limites actuelles

  - ClaudeProvider (providers/claude.py) reste un adaptateur squelette non
    connecté (signalé explicitement comme Non connecté).
  - OCR local (computer_ocr / transcribe_image) : L'extraction de texte dans les
    captures d'écran utilise pytesseract et requiert que le binaire système
    Tesseract OCR soit présent dans le PATH Windows pour l'analyse de texte sur
    image (la capture d'écran et la comparaison pixel par pixel
    computer_compare_screens fonctionnent nativement via Pillow sans Tesseract).

23. Feuille de route technique (Roadmap)

  - Connexion native de ClaudeProvider à l'API Anthropic Messages.
  - Inspection de l'arbre d'accessibilité Windows UI Automation
    (UIAutomationCore.dll) en complément de l'OCR et des coordonnées visuelles
    dans tools/computer_use.py.

