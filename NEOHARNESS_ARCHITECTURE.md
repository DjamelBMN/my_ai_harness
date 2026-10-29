Voici le document NEOHARNESS_ARCHITECTURE.md intégralement mis à jour, complet
de la première à la dernière ligne, intégrant l'ensemble des nouveaux moteurs et
capacités validés lors de cette session (Computer Use 2.0 Set-of-Mark, Canvas
Co-Éditable 2.0 & Diff, NeoDeepSearch Google Grounding, Intelligence du Code
AST, Mémoire Hybride & Graphe, Data Analyst Excel/Outliers, Voix Live &
Sentinelle).

Tu peux copier-coller l'intégralité du contenu ci-dessous pour remplacer le
fichier existant à la racine de ton projet :

NEOHARNESS_ARCHITECTURE.md — Documentation Technique et Architecture Complète de NeoHarness AI

Créateur & Architecte : Djamel BENMAKHLOUF
Document de référence d'architecture, de fonctionnement interne et de
maintenance de NeoHarness AI
Ce document reflète strictement l'état réel du dépôt vérifié fichier par fichier
et par exécution directe, sans inventer de composant, de modèle, de skill ou
d'outil inexistant.

Table des matières

  - 1. Vue d'ensemble du projet
      - 1.1 Qu'est-ce que NeoHarness AI ?
      - 1.2 Philosophie : « Complexité cachée. Fonctionnalités 100 % réelles.
        Zéro simulation. Sécurité proportionnée. »
  - 2. Arborescence complète finale
  - 3. Description détaillée fichier par fichier
      - 3.1 Entrée et Normalisation des Contrats
      - 3.2 Sécurité, Gouvernance & Tool Gateway
      - 3.3 Couche Opérateur Windows & Computer Use 2.0 (UI Automation &
        Set-of-Mark)
      - 3.4 Intelligence du Code Chirurgicale (AST & Diagnostic Statique)
      - 3.5 Moteur de Recherche Web & NeoDeepSearch (Google Grounding Officiel)
      - 3.6 Data Analyst Autonome (Profilage Statistique, Outliers & Excel
        Natif)
      - 3.7 Mémoire Hybride Sémantique, Graphe de Connaissances & Compaction
      - 3.8 Interface Utilisateur, Canvas Co-Éditable 2.0, Voix Live &
        Sentinelle
  - 4. Fonctionnement global de bout en bout
  - 5. Cycle de vie complet d'une requête
  - 6. Fonctionnement détaillé du Model Router & Streaming
  - 7. Architecture complète des 22 Skills
  - 8. Architecture des Agents
  - 9. Classification des risques et politique de gouvernance (Policy Engine)
  - 10. Dépendances et bibliothèques
  - 11. Commandes de lancement et suites de tests
  - 12. Journal des modifications architecturales

1. Vue d'ensemble du projet

1.1 Qu'est-ce que NeoHarness AI ?

NeoHarness AI est un harness agentique multi-modèles, multi-agents, opérateur
Windows en boucle fermée (Computer Use 2.0) et environnement de travail IA
complet écrit en Python. Il dispose :

  - d'une interface CLI interactive (python main.py),
  - et d'une interface web opératoire d'élite (python -B main.py --ui
    --port 8765), servie par un serveur HTTP/SSE natif Python avec une interface
    HTML5/CSS3/JS épurée, KaTeX, MathJax, Web Audio API, Web Speech API et
    aperçu documentaire multi-formats.

1.2 Philosophie : « Complexité cachée. Fonctionnalités 100 % réelles. Zéro simulation. Sécurité proportionnée. »

  - Design System Pierre Chaude (#F6F5F0 / #EFECE6 / #FFFFFF) avec bascule
    instantanée Mode Sombre (#0B0D10), 100 % icônes vectorielles SVG (zéro
    émoticône).
  - Palette flottante Slash (/) dans l'ordre canonique strict des 22 Skills
    disponibles.
  - Inspecteur latéral droit unifié (#right-inspector) transformé en Canvas
    Co-Éditable 2.0 : édition de code source, modification chirurgicale par IA
    d'une sélection, comparateur visuel de versions (Diff ligne par ligne V1
    \leftrightarrow V2) et aperçus documentaires réels (PDF Tectonic, Word .docx
    Pandoc, HTML sandboxé, SVG, Mermaid, Images).
  - Moteur NeoDeepSearch en essaim parallèle : exploration Web multi-axes avec
    décomposition déterministe, intégration officielle de Google Search
    Grounding, lecture intégrale de pages en parallèle, détection de
    corrélations et citations cliquables [Source N](url).
  - Opérateur Windows Computer Use 2.0 : fusion de l'arbre d'accessibilité
    Windows UI Automation (.NET), des contrôles Win32 natifs et du marquage
    visuel Set-of-Mark ([1]..[N]) permettant le clic par ID d'élément en boucle
    fermée.
  - Intelligence du Code AST & Diagnostics : cartographie structurelle du code
    (code_ast_map), recherche de définitions et références d'un symbole,
    diagnostic statique (diagnose_code) et isolation en Git Worktrees.
  - Data Analyst Autonome : profilage statistique de datasets (analyze_dataset :
    CSV, TSV, XLSX, JSON, SQLite) avec détection d'anomalies (outliers) et
    corrélations de Pearson, ainsi que génération de vrais classeurs Excel
    (generate_excel) avec formules natives (=SUM, =AVERAGE).
  - Compagnon Proactif Sentinelle & Voix Live : surveillance proactive du
    terminal Windows et lecture vocale naturelle en français avec prononciation
    adaptée des formules mathématiques.

2. Arborescence complète finale

my_ai_harness/
├── .gitignore                        # Règles d'exclusion Git (.env, __pycache__, etc.)
├── README.md                         # Présentation rapide et commandes de base
├── NEOHARNESS_ARCHITECTURE.md        # Documentation technique complète (ce document)
├── NEOHARNESS_ARTIFACT_ENGINE.md     # Documentation du moteur universel d'artefacts
├── NEOHARNESS_RUNTIME_VALIDATION.md  # Rapport de vérification runtime réelle de bout en bout
├── requirements.txt                  # Dépendances Python (google-genai, openai, mistralai, openpyxl, duckduckgo-search, primp, Pillow, pytesseract, PyMuPDF, pypdf, PyYAML, prompt-toolkit)
├── main.py                           # Point d'entrée principal CLI et lanceur UI (--ui)
│
├── config/
│   ├── config.yaml                   # Configuration centrale (providers, routes, feature flags)
│   └── custom_models.json            # Modèles LLM personnalisés ajoutés dynamiquement
│
├── agents/
│   ├── __init__.py                   # Package des agents spécialisés
│   ├── coder.py                      # CodeAgent : programmation, cartographie AST, diagnostics, Computer Use
│   ├── researcher.py                 # ResearchAgent : recherche locale, Deep Research et documents
│   ├── reviewer.py                   # ReviewAgent & IndependentCritic : audit critique sur contexte vierge
│   └── tester.py                     # TestAgent : exécution déterministe des suites de tests
│
├── core/
│   ├── __init__.py                   # Package du noyau d'orchestration
│   ├── agent.py                      # Classe de base Agent (directives d'identité et de gouvernance)
│   ├── agent_loop.py                 # Boucle d'exécution fermée (outils, auto-réparation, vérification)
│   ├── agent_registry.py             # Registre des agents disponibles (AgentRegistry)
│   ├── agent_selector.py             # Sélection d'agent par scoring de capacités et d'intentions
│   ├── artifact_intent.py            # Détection d'intention d'artefact et conformité de livrable
│   ├── checkpoint.py                 # Points de reprise et backtracking (Shadow Git / snapshots)
│   ├── context.py                    # Historique d'interactions léger et mémoire de mission (Context)
│   ├── context_manager.py            # Gestionnaire de contexte et compaction préservant les invariants
│   ├── dag_engine.py                 # Moteur d'exécution de graphes multi-agents acycliques
│   ├── delegation.py                 # Délégation contrôlée de sous-tâches entre agents
│   ├── event_bus.py                  # Bus d'événements normalisés temps réel et SSE
│   ├── events.py                     # Événements bas niveau du runtime et traducteur français
│   ├── intent_engine.py              # Classification d'intention (coding, testing, research, computer_use, file_analysis...)
│   ├── library.py                    # Bibliothèque intelligente persistante et recherche sémantique hybride
│   ├── mcp_client.py                 # Client MCP JSON-RPC 2.0 stdio raccordé au ToolGateway
│   ├── memory.py                     # Mémoire persistante, recherche hybride, graphe de connaissances et leçons réflexives
│   ├── metrics_sink.py               # Collecteur de métriques d'exécution
│   ├── model_registry.py             # Registre vérifié des Providers, Modèles et Capabilities
│   ├── modes.py                      # Modes de gouvernance globaux (AUTO, ACCEPT, EDIT, PLAN)
│   ├── multi_agent_coordinator.py    # Coordination séquentielle et hiérarchique multi-agents
│   ├── orchestrator.py               # Orchestrateur central (run, run_agentic)
│   ├── permissions.py                # Politique de permissions proportionnée et Human-In-The-Loop
│   ├── planner.py                    # Planificateur d'étapes minimalistes et observations initiales
│   ├── policy_engine.py              # Moteur de sécurité et classification des risques réels
│   ├── rate_limit_manager.py         # Gestionnaire de concurrence LLM, backoff et circuit breaker
│   ├── replay.py                     # Rejeu déterministe de missions enregistrées
│   ├── router.py                     # Routeur de modèles par agent, intention, complexité et failover
│   ├── self_audit.py                 # Télémétrie, auto-audit et benchmark interne
│   ├── skill_compatibility.py        # Moteur de compatibilité Provider -> Model -> Skills
│   ├── task.py                       # Contrat de tâche (Task) et normalisateur strict ensure_task()
│   ├── task_context.py               # Continuité multi-tours et historique persistant par conversation
│   ├── task_state.py                 # État riche d'exécution d'une tâche (PlanStep, AgentResult)
│   ├── tdd_engine.py                 # Moteur TDD en boucle fermée et scellement SHA-256
│   ├── title_generator.py            # Générateur intelligent de titres de tâches
│   ├── tool_gateway.py               # Tool Gateway central & journal d'observabilité (.harness/operator_audit.jsonl)
│   ├── verifier.py                   # Vérificateur final déterministe (fichiers, tests, provenance Web, GUI)
│   └── artifacts/                    # Moteur universel d'artefacts (UniversalArtifactEngine)
│
├── providers/
│   ├── __init__.py                   # Package des adaptateurs LLM
│   ├── base_provider.py              # Contrat abstrait BaseProvider
│   ├── claude.py                     # ClaudeProvider (squelette d'intégration Anthropic)
│   ├── gemini.py                     # GeminiProvider (Google GenAI native, streaming, Google Search Grounding)
│   ├── local.py                      # LocalProvider (fournisseur déterministe hors-ligne)
│   ├── mistral.py                    # MistralProvider (SDK mistralai + client HTTP)
│   ├── ollama.py                     # OllamaProvider (exécution locale Ollama)
│   └── openai.py                     # OpenAIProvider (API OpenAI Completions)
│
├── skills/
│   ├── __init__.py                   # Export public du système de Skills
│   ├── loader.py                     # Chargement dynamique des Skills, RAG et gabarits LaTeX
│   ├── registry.py                   # Registre central des 22 Skills dans l'ordre canonique strict
│   ├── router.py                     # Routage automatique par triggers et commandes slash
│   ├── runtime.py                    # Exécution des commandes slash et état de session
│   ├── education/                    # Skills éducatifs (/exercice, /dm, /bacblanc, /antitriche, /correction)
│   └── <dossiers de skills>/         # analyze, auto, compare, context, debug, diagnostic, export, memory,
│                                     # mode, model, plan, refactor, research, review, route, test, workflow
│
├── tools/
│   ├── __init__.py                   # Package des outils système et bureautiques
│   ├── browser.py                    # Navigateur dynamique Playwright Chromium (DynamicBrowser)
│   ├── clipboard.py                  # Presse-papiers Windows natif Win32 Unicode (clipboard_get, clipboard_set)
│   ├── code_search.py                # Regex rapide (search_code) et cartographie AST (code_ast_map)
│   ├── compiler.py                   # Compilateur autonome LaTeX avec auto-correction
│   ├── computer_use.py               # Computer Use 2.0 (UI Automation, Set-of-Mark, clic par ID, souris/clavier Win32)
│   ├── documents.py                  # Lecture (read_document), compilation (LaTeX, HTML), profilage (analyze_dataset) et Excel (generate_excel)
│   ├── docx.py                       # Génération Word .docx Pandoc avec équations OMML
│   ├── editor.py                     # Édition chirurgicale (edit_file) et diagnostic statique AST (diagnose_code)
│   ├── filesystem.py                 # Opérations fichiers confinées dans workspace/
│   ├── git.py                        # Inspection Git et isolation en Git Worktrees (create_worktree)
│   ├── math_tikz.py                  # Génération déterministe de figures mathématiques TikZ / SymPy
│   ├── process_manager.py            # Gestionnaire de processus Windows (process_list, process_start, process_stop)
│   ├── process_utils.py              # Environnement nettoyé des secrets API
│   ├── python_runtime.py             # Exécution Python headless avec capture automatique Matplotlib
│   ├── rasterizer.py                 # Rastérisation PDF -> PNG
│   ├── registry.py                   # Registre central des outils et intégration au ToolGateway
│   ├── search.py                     # Recherche Web, Google Search Grounding officiel, NeoDeepSearch et téléchargement vérifié
│   ├── terminal.py                   # Façade du terminal persistant et exécution de scripts
│   ├── terminal_session.py           # Sessions interactives Windows PowerShell/CMD avec sentinelles
│   ├── viewer.py                     # Lecture fenêtrée de fichiers avec numéros de lignes
│   ├── vision.py                     # Transcription OCR multi-passes fidèle
│   └── windows.py                    # Contrôle natif Win32 des fenêtres (window_list, window_focus, etc.)
│
├── ui/
│   ├── __init__.py                   # Package de l'interface web opératoire
│   ├── server.py                     # Pont runtime (NeoHarnessRuntimeBridge) + REST/SSE, Canvas IA, NeoDeepSearch & Sentinelle
│   └── static/
│       ├── index.html                # Interface HTML5 épurée (100% SVG vectoriel, Canvas IA, NeoDeepSearch, Voix Live)
│       ├── styles.css                # Design system pierre chaude (#F6F5F0) / sombre (#0B0D10) et styles Canvas/Diff
│       └── app.js                    # Logique client réactive, Canvas Co-Éditable, Diff, Voix Live et Sentinelle
│
├── docs/                             # Documentation spécialisée
├── evals/                            # Suite de benchmarks automatisée
├── runtime/pandoc/                   # Binaire Pandoc embarqué (pandoc.exe)
├── tests/                            # Suites de tests complètes (100 % validées au vert)
└── workspace/                        # Espace de travail confiné pour les opérations des agents

3. Description détaillée fichier par fichier

3.1 Entrée et Normalisation des Contrats

  - core/task.py : Définit Task et la fonction frontière ensure_task(task: Task
    | str, ...), garantissant qu'aucune chaîne brute ne parvient aux moteurs
    d'orchestration sans conversion en contrat typé.
  - core/task_state.py : Maintient l'état riche d'exécution de la mission
    (PlanStep, observations, diffs, vérifications).
  - core/planner.py & core/orchestrator.py : Génèrent le plan minimaliste le
    plus court suffisant, injectent l'identité NeoHarness AI et coordonnent
    l'exécution sans étapes parasites.

3.2 Sécurité, Gouvernance & Tool Gateway

  - core/tool_gateway.py : Point de passage unique obligatoire entre les agents
    et le système. Journalise chaque étape (AGENT_CALL, POLICY, HITL, EXECUTION,
    VERIFICATION) dans workspace/.harness/operator_audit.jsonl.
  - core/policy_engine.py : Moteur déclaratif classifiant chaque action selon 6
    niveaux de risque (SAFE, LOW, MEDIUM, HIGH, CRITICAL, BLOCKED). Bloque
    inconditionnellement tout contournement UAC, désactivation d'antivirus ou
    extraction de secrets système.
  - core/permissions.py : Applique le principe de proportionnalité UX : les
    actions en lecture seule (SAFE) et les actions simples sûres s'exécutent
    directement sans friction, tandis que les actions sensibles déclenchent une
    validation humaine (HITL) adaptée.

3.3 Couche Opérateur Windows & Computer Use 2.0

  - tools/computer_use.py :
      - computer_inspect_ui : Inspection hybride de l'arbre d'accessibilité
        Windows UI Automation (.NET System.Windows.Automation) et des contrôles
        enfants Win32 (EnumChildWindows). Identifie chaque bouton, menu, champ
        ou onglet avec ses coordonnées absolues. Génère une capture annotée
        Set-of-Mark (SoM) numérotée [1]..[N] avec cadres colorés et badges haute
        lisibilité.
      - computer_click_element : Permet de cliquer sur l'élément [element_id] et
        d'y saisir du texte en boucle fermée sans deviner de coordonnées (x, y)
        manuelles.
      - computer_screenshot : Capture d'écran Win32 haute fidélité avec
        résolution automatique du vrai Bureau Windows (local ou OneDrive) via
        SHGetFolderPathW.
      - computer_compare_screens : Diff pixel par pixel (PIL.ImageChops) pour
        détecter l'impact d'une action.
      - computer_mouse_* & computer_type / computer_hotkey : Pilotage souris et
        clavier via user32 avec Fail-Safe d'urgence au coin (0, 0).
      - computer_action_verified : Boucle fermée GUI (Capture Avant → Action →
        Stabilisation → Capture Après → Comparaison & Validation).
  - tools/windows.py : Énumération et contrôle des fenêtres (window_list,
    window_active, window_find, window_focus, window_close, etc.).
  - tools/terminal_session.py : Sessions interactives persistantes PowerShell et
    CMD avec sentinelles instantanées (__NEOHARNESS_CMD_DONE__).

3.4 Intelligence du Code Chirurgicale

  - tools/code_search.py :
      - search_code : Recherche ciblée par expressions régulières avec exclusion
        des répertoires parasites (.git, node_modules, __pycache__).
      - code_ast_map : Analyse l'arbre syntaxique abstrait (ast) pour extraire
        la radiographie complète du code (classes, méthodes, signatures
        d'arguments avec types, docstrings, graphe d'appels et liste des
        imports). Quand un symbol_query est fourni, localise immédiatement où le
        symbole est défini et toutes ses références dans le projet.
  - tools/editor.py :
      - edit_file : Édition chirurgicale par remplacement de bloc unique avec
        linting AST instantané, détection automatique des défauts sémantiques et
        rollback immédiat en cas d'erreur.
      - diagnose_code : Diagnostic statique avant exécution détectant le code
        mort après return/raise, les arguments par défaut mutables (def
        f(x=[])), les méthodes dupliquées et la validité structurelle JSON/HTML.
  - tools/git.py :
      - GitWorkspace : Opérations Git confinées et gestion des Git Worktrees
        (create_worktree, list_worktrees) pour isoler les modifications d'agents
        parallèles.

3.5 Moteur de Recherche Web & NeoDeepSearch

  - tools/search.py :
      - _search_google_grounding : Interroge l'index officiel mondial de Google
        Search via l'outil natif google_search de Gemini (100 % officiel, sans
        scraping, zéro blocage).
      - deep_research : Moteur de recherche approfondie en essaim parallèle :
        1.  Décomposition déterministe du sujet en 5 axes thématiques structurés
            avec intitulés clairs pour l'utilisateur.
        2.  Recherches Web multi-axes en parallèle (ThreadPoolExecutor).
        3.  Lecture intégrale simultanée des pages de domaines distincts via
            fetch_url.
        4.  Calcul des scores d'autorité, détection des concepts corroborés
            entre sources indépendantes et génération de citations cliquables
            [Source N](url).
      - web_search : Recherche Web résiliente combinant Google Search Grounding
        en priorité absolue, repli Bing avec session Edge, et téléchargement
        autonome vérifié (download_resource).
      - download_resource & verify_downloaded_file : Téléchargement physique
        avec vérification des magic bytes et scellement dans la chaîne de
        provenance cryptographique (ProvenanceLedger).

3.6 Data Analyst Autonome

  - tools/documents.py :
      - analyze_dataset : Profilage statistique autonome de fichiers .csv, .tsv,
        .xlsx, .json et .sqlite/.db. Calcule le schéma, les valeurs manquantes,
        la moyenne, médiane, écart-type, quartiles, corrélations de Pearson
        entre variables numériques, et détecte automatiquement les valeurs
        aberrantes (outliers) par score Z et écart interquartile (IQR).
      - generate_excel_workbook : Génération de classeurs Microsoft Excel .xlsx
        professionnels avec mise en forme institutionnelle (#185ABD), ajustement
        automatique de la largeur des colonnes et injection de formules natives
        (=SUM(...), =AVERAGE(...)).
      - compile_latex & compile_html : Compilateurs autonomes avec boucles
        d'auto-réparation.

3.7 Mémoire Hybride Sémantique, Graphe de Connaissances & Compaction

  - core/memory.py :
      - MemoryManager : Stockage cross-session (.harness/persistent_memory.json)
        avec moteur de recherche hybride (hybrid_semantic_score) combinant
        racines lexicales et trigrammes de caractères.
      - build_knowledge_graph : Graphe de connaissances personnel reliant
        automatiquement les souvenirs, les fichiers mentionnés, les concepts et
        les ressources de bibliothèque sous forme de nœuds et d'arêtes.
      - ReflectiveMemory : Base SQLite/FTS5 enregistrant les leçons
        expérientielles post-mission avec décroissance temporelle (decay).
  - core/library.py : Bibliothèque intelligente (.harness/library.json)
    synchronisée avec le workspace et dotée de recherche sémantique hybride.
  - core/context_manager.py : Compaction de contexte sanctuarisant
    automatiquement tous les fichiers manipulés, symboles de code et décisions
    validées lors de l'archivage des tours anciens.

3.8 Interface Utilisateur, Canvas Co-Éditable 2.0, Voix Live & Sentinelle

  - ui/server.py : Pont runtime REST et flux SSE temps réel
    (/api/events/stream), gestion des routes d'approbation HITL, compilation
    documentaire, endpoint Canvas IA (POST /api/artifacts/ai-edit), comparateur
    de versions (GET /api/artifacts/diff), mode d'exécution NeoDeepSearch en
    streaming et surveillance GET /api/sentinel.
  - ui/static/index.html :
      - Design system pierre chaude sans aucune émoticône (100 % icônes
        vectorielles SVG).
      - Bouton 1-clic et menu popover NeoDeepSearch.
      - Boutons vectoriels Voix Live (#btn-voice-tts-toggle) et Sentinelle
        (#btn-sentinel-scan).
      - Panneau latéral droit #right-inspector unifié intégrant le Canvas
        Co-Éditable (bouton Éditer IA, barre d'actions rapides, visualiseur de
        Diff V1 \leftrightarrow V2).
  - ui/static/app.js :
      - Gestion du streaming SSE avec ouverture immédiate des 5 axes
        déterministes de recherche à t = 0\text{s}.
      - Mode Voix Live utilisant la synthèse vocale (SpeechSynthesis) en
        français naturel avec traduction orale des formules mathématiques
        (\sqrt{x} \rightarrow « racine carrée de x »).
      - Sentinelle proactive surveillant périodiquement le terminal et proposant
        des corrections en 1 clic en cas d'erreur.
  - ui/static/styles.css : Design system complet, styling du Canvas IA, des
    badges de diffs et des boutons d'état actif.

4. Fonctionnement global de bout en bout

┌────────────────────────────────────────────────────────────────────────────────────────┐
│            UTILISATEUR (Interface Web Mode Clair / Sombre ou CLI)                      │
│   Palette Slash (22) │ Canvas Co-Éditable │ Voix Live │ Sentinelle │ NeoDeepSearch     │
└───────────────────┬────────────────────────────────────────────────────▲───────────────┘
                    │ 1. Demande utilisateur                             │ 9. Flux SSE
                    ▼                                                    │ & Livrables
┌────────────────────────────────────────────────────────────────────────┴───────────────┐
│                   PONT D'EXÉCUTION : NeoHarnessRuntimeBridge (ui/server.py)            │
│   • IntentEngine : détection d'intention (Coding, Research, DeepSearch, Data, GUI)     │
│   • Mode Dédié NeoDeepSearch : 5 axes déterministes + Google Search Grounding direct   │
│   • Orchestrator & AgentLoop : sélection de l'agent et boucle fermée                   │
│   • ToolGateway & PolicyEngine : évaluation du risque (SAFE à BLOCKED)                 │
│   • HITL proportionné : validation uniquement sur actions sensibles                    │
│   • Action Windows / Code AST / Dataset -> Verifier déterministe                       │
└────────────────────────────────────────────────────────────────────────────────────────┘

5. Cycle de vie complet d'une requête

1.  Saisie utilisateur : L'utilisateur saisit sa demande, sélectionne un skill
    via /, active le mode NeoDeepSearch, utilise la dictée vocale ou déclenche
    une action via la Sentinelle.
2.  Traitement direct NeoDeepSearch (si activé) :
      - Émission immédiate des 5 axes thématiques déterministes sur le flux SSE
        dès la milliseconde t = 0\text{s}.
      - Interrogation en direct de l'index officiel mondial de Google Search via
        le Grounding Gemini.
      - Streaming temps réel du rapport complet avec citations Markdown [Source
        N](url).
3.  Traitement Agentic Standard :
      - IntentEngine.decide() résout l'intention et sélectionne les outils
        natifs nécessaires.
      - Planner.plan() génère le plan minimaliste le plus court suffisant.
      - Les appels d'outils passent par ToolGateway et PolicyEngine.evaluate().
      - Exécution des outils (code_ast_map, edit_file avec linting AST,
        analyze_dataset, generate_excel, computer_inspect_ui Set-of-Mark...).
4.  Vérification déterministe & Canvas : Verifier.verify() contrôle les preuves
    physiques. L'artefact généré s'ouvre dans le panneau Canvas droit avec son
    comparateur de versions et ses options de retouche IA chirurgicale.

6. Fonctionnement détaillé du Model Router & Streaming

| ID Modèle           | Classe Provider                            | Modèle configuré (`config.yaml`)             | État de connexion                         | Capacités principales                                                                                          |
| :------------------ | :----------------------------------------- | :------------------------------------------- | :---------------------------------------- | :------------------------------------------------------------------------------------------------------------- |
| `gemini`            | `GeminiProvider` (`providers/gemini.py`)   | `gemini-3.8-flash` / `gemini-3.5-flash-lite` | **Connecté** (`GEMINI_API_KEY`)           | Vision multimodale, Long Context, Function Calling, **Google Search Grounding officiel**, Streaming temps réel |
| `gemini_flash_lite` | `GeminiProvider` (`providers/gemini.py`)   | `gemini-3.5-flash-lite`                      | **Connecté** (`GEMINI_API_KEY`)           | Vitesse ultra-rapide, Function Calling, Google Search Grounding                                                |
| `openai`            | `OpenAIProvider` (`providers/openai.py`)   | `gpt-5-mini`                                 | Actif si `OPENAI_API_KEY` présente        | Function Calling, Structured Output, Streaming                                                                 |
| `mistral`           | `MistralProvider` (`providers/mistral.py`) | `mistral-small-latest`                       | Actif si `MISTRAL_API_KEY` présente       | Function Calling, Structured Output                                                                            |
| `ollama`            | `OllamaProvider` (`providers/ollama.py`)   | `qwen3:1.7b`                                 | **Connecté en local** (`127.0.0.1:11434`) | Exécution 100% locale, Function Calling JSON                                                                   |
| `claude`            | `ClaudeProvider` (`providers/claude.py`)   | `claude-sonnet-4`                            | Squelette d'intégration                   | Déclaré pour routage                                                                                           |

Extensibilité : Ajout dynamique de modèles LLM personnalisés via l'interface
(POST /api/models/custom/add), persistés dans config/custom_models.json.

7. Architecture complète des 22 Skills

Les 22 Skills enregistrés dans SkillRegistry (skills/registry.py) respectent
l'ordre canonique strict :

1.  /analyze : Analyse de fichiers, documents ou extraits du workspace.
2.  /antitriche : Détection de plagiat et validation d'originalité.
3.  /auto : Exécution autonome complète d'une mission complexe.
4.  /bacblanc : Conception complète d'un sujet de Bac Blanc conforme aux
    programmes officiels et compilé en PDF Tectonic.
5.  /compare : Comparaison différentielle de fichiers ou solutions.
6.  /context : Inspection du contexte actif et des fichiers suivis.
7.  /correction : Barèmes détaillés et corrigés officiels.
8.  /debug : Diagnostic de bugs et auto-réparation de code.
9.  /diagnostic : Contrôle de santé des providers, compilateurs et outils.
10. /dm : Génération de Devoirs Maison de mathématiques en LaTeX.
11. /exercice : Conception d'exercices avec figures TikZ déterministes.
12. /export : Exportation documentaire (PDF, Word DOCX, HTML).
13. /memory : Consultation et gestion de la mémoire persistante.
14. /mode : Bascule des modes de gouvernance (AUTO, ACCEPT, EDIT, PLAN).
15. /model : Sélection et routage dynamique des modèles LLM.
16. /plan : Planification déterministe d'étapes de mission.
17. /refactor : Refactoring de code assisté par AST.
18. /research : Recherche Web, documentation et synthèse.
19. /review : Revue critique de code et audit de sécurité.
20. /route : Inspection du routage de modèles par agent.
21. /test : Exécution et validation des suites de tests unitaires.
22. /workflow : Orchestration de flux multi-étapes.

8. Architecture des Agents

1.  CodeAgent (coder) : Développement, édition chirurgicale (edit_file),
    cartographie de code (code_ast_map), diagnostic statique (diagnose_code) et
    pilotage de l'opérateur Windows Computer Use.
2.  ResearchAgent (researcher) : Recherche Web approfondie en essaim,
    interrogation de l'index Google Search officiel, vérification croisée et
    génération de livrables Word .docx.
3.  ReviewAgent (reviewer) & IndependentCritic : Revue de code impartiale sur
    contexte vierge et détection des failles de sécurité.
4.  TestAgent (tester) : Exécution et diagnostic déterministe des suites de
    tests sans altération possible du code de test.
5.  BacBlancAgent (bacblanc) : Conception complète de sujets et barèmes d'examen
    en LaTeX officiel.

9. Classification des risques et politique de gouvernance

| Niveau                         | Exemples d'outils et actions                                                                                                                                                                        | Comportement en mode standard (`AUTO` / `ACCEPT`)                                   |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------- |
| **`SAFE`** (`READ_ONLY`)       | `filesystem.read`, `code_ast_map`, `diagnose_code`, `analyze_dataset`, `web_search`, `deep_research`, `computer_screenshot`, `computer_inspect_ui`, `window_list`, `clipboard_get`, `terminal_read` | **Exécution directe immédiate (0 confirmation)**                                    |
| **`LOW`**                      | `copy_to_desktop`, `clipboard_set`, `window_focus`, `window_minimize`, `window_maximize`, `terminal_start`, `terminal_stop`, `filesystem.write`                                                     | **Exécution directe** pour les actions courantes sûres                              |
| **`MEDIUM`** (`MODERATE`)      | `generate_excel`, `process_start`, `terminal_send`, `computer_click`, `computer_click_element`, `computer_type`, `computer_hotkey`, `computer_action_verified`                                      | **HITL standard** : `[ Refuser ]`, `[ Autoriser ]`, `[ Autoriser pour la session ]` |
| **`HIGH`**                     | `delete_file`, `process_stop`, `window_close`, `git_create_branch`, `git_commit_staged`                                                                                                             | **HITL Sensible** : `[ Refuser ]` ou `[ Autoriser une fois ]` uniquement            |
| **`CRITICAL`** (`DESTRUCTIVE`) | `git_merge`, `system.shutdown`                                                                                                                                                                      | **HITL Critique systématique** : `[ Refuser ]` ou `[ Autoriser une fois ]`          |
| **`BLOCKED`**                  | Contournement UAC (`fodhelper`), arrêt Windows Defender, extraction LSASS/SAM                                                                                                                       | **Blocage inconditionnel immédiat** par le Policy Engine                            |

10. Dépendances et bibliothèques

  - Python (requirements.txt) : google-genai>=1.32.0, openai>=1.66.0,
    mistralai>=3.2.0, openpyxl>=3.1.0, duckduckgo-search>=8.1.0, primp>=0.15.0,
    Pillow>=10.0.0, pytesseract>=0.3.10, PyMuPDF>=1.24.0, pypdf>=4.0.0,
    PyYAML>=6.0, prompt-toolkit>=3.0.43,<4.0.
  - Navigateur dynamique : Playwright Chromium (tools/browser.py).
  - APIs Windows natives (ctypes) : user32, kernel32, shell32, accessibilité
    .NET System.Windows.Automation (zéro dépendance C++ fragile).
  - Compilateurs documentaires : Tectonic (tectonic.exe pour LaTeX \rightarrow
    PDF) et Pandoc (runtime/pandoc/pandoc.exe pour Markdown \rightarrow Word
    .docx).

11. Commandes de lancement et suites de tests

# 1. Lancer le serveur web opératoire NeoHarness AI
python -B main.py --ui --port 8765

# 2. Lancer la suite de validation de l'interface et du Canvas
python -B -m unittest tests/test_ui_environment.py -v

# 3. Lancer la suite de validation de l'agent opérateur Windows (Computer Use)
python -B -m unittest tests/test_windows_computer_use_agent.py -v

# 4. Lancer toutes les suites de validation du noyau et des skills
python -B -m unittest tests/test_runtime.py tests/test_skills.py tests/test_general_skills.py tests/test_multi_agent_runtime.py tests/test_ui_environment.py tests/test_windows_computer_use_agent.py -v

12. Journal des modifications architecturales

1.  Computer Use 2.0 (UI Automation & Set-of-Mark) : Inspection de l'arbre
    d'accessibilité Windows .NET et contrôles Win32, badges numérotés [1]..[N]
    et clic déterministe par element_id (tools/computer_use.py).
2.  Canvas Co-Éditable 2.0 & Comparateur Diff : Barre d'édition chirurgicale IA
    sur sélection, recompilation automatique (Tectonic/HTML), comparateur visuel
    de versions V1 \leftrightarrow V2 ligne par ligne (ui/server.py,
    ui/static/app.js, ui/static/styles.css).
3.  NeoDeepSearch & Google Search Grounding Officiel : Décomposition
    déterministe en 5 axes thématiques, intégration du moteur Google mondial
    officiel via le SDK google-genai (0 €), lecture intégrale en parallèle et
    citations cliquables [Source N](url) (tools/search.py, ui/server.py).
4.  Intelligence du Code AST & Diagnostics : Cartographie structurelle AST
    (code_ast_map), recherche de définitions et références de symboles dans tout
    le projet, diagnostic statique (diagnose_code) et isolation en Git Worktrees
    (tools/code_search.py, tools/editor.py, tools/git.py, agents/coder.py).
5.  Mémoire Hybride, Graphe de Connaissances & Compaction : Moteur de similarité
    hybride (racines lexicales + trigrammes), graphe dynamique reliant souvenirs
    et documents, et sanctuarisation des invariants lors de la compaction
    (core/memory.py, core/library.py, core/context_manager.py).
6.  Data Analyst Autonome & Excel Natif : Profilage statistique complet
    (analyze_dataset : CSV, XLSX, JSON, SQLite) avec détection d'anomalies
    (outliers) et corrélations de Pearson, ainsi que génération de vrais
    classeurs Excel (generate_excel) avec formules natives =SUM / =AVERAGE
    (tools/documents.py).
7.  Mode Voix Live & Sentinelle Proactive : Synthèse vocale fluide en français
    avec lecture naturelle des formules mathématiques, surveillance proactive du
    terminal et de la fenêtre active (GET /api/sentinel), et interface 100 %
    vectorielle SVG (ui/static/).
8.  Alignement et Stabilisation des Tests : Validation stricte des 22 Skills
    canoniques (avec antitriche et correction), protection de l'évaluation
    Node.js dans test_ui_environment.py et passage à 100 % de tests au vert.
