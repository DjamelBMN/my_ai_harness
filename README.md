Voici le fichier README.md complet et intégralement mis à jour, prêt à être
copié-collé pour remplacer README.md à la racine de ton dépôt :

# NeoHarness AI — AI Agent Operating Environment & Windows Computer Use

> **Créé et développé par Djamel BENMAKHLOUF**
> Un environnement opératoire agentique multi-modèles de production (Gemini, Ollama, OpenAI, Mistral + LLM personnalisés), orchestrant agents autonomes, 20 skills canoniques et éducatifs, **Computer Use Windows en boucle fermée**, **Tool Gateway**, **Policy Engine**, **Human-In-The-Loop proportionné**, **Terminal PowerShell/CMD persistant**, RAG, Tectonic LaTeX, Pandoc Word (`.docx`) et vérification déterministe — **Zéro simulation**.

```text
Utilisateur (Interface Web --ui ou CLI interactif)
    ↓
Orchestrator → IntentEngine → Planner (plan minimal suffisant) → TaskState
    ↓
AgentLoop : PERCEIVE → PLAN → ACT → OBSERVE → VERIFY → CORRECT → DELIVER
    ↓
CodeAgent / TestAgent / ReviewAgent / ResearchAgent / BacBlancAgent
    ↓
ModelRouter (intention + complexité + RateLimitManager + repli automatique)
    ↓
GeminiProvider / OpenAIProvider / MistralProvider / OllamaProvider / Custom LLM
    ↓
ToolGateway (core/tool_gateway.py) → PolicyEngine (SAFE | LOW | MEDIUM | HIGH | CRITICAL | BLOCKED)
    ↓
PermissionPolicy & HITL proportionné (Exécution directe si SAFE/LOW · Validation humaine si sensible)
    ├── filesystem      (lecture, écriture, patch, édition, copie directe vers le Bureau Windows)
    ├── computer_use    (screenshot, diff visuel avant/après, OCR localisé, souris, clavier, boucle fermée)
    ├── windows         (lister, identifier la fenêtre active, chercher, focus, minimiser, maximiser, fermer)
    ├── terminal        (sessions PowerShell/CMD persistantes, stdin/stdout/stderr temps réel, tests)
    ├── process         (lister les processus Windows, démarrer une app, surveiller, arrêter)
    ├── clipboard       (lecture/écriture native Win32 Unicode du presse-papiers)
    ├── browser         (recherche Web réelle, navigation Chromium Playwright, téléchargement avec provenance)
    ├── documents       (compilation PDF Tectonic auto-réparatrice, génération Word .docx Pandoc, TikZ, OCR)
    ├── git             (status, branch, commit staged, merge)
    └── mcp             (adaptateur client MCP JSON-RPC stdio externe sous contrôle du PolicyEngine)

1. LLM, Agent, Opérateur Windows et Harness

  - Un LLM génère du texte ou des appels d'outils : GPT, Gemini, Mistral ou
    Qwen.
  - Un Agent est un programme spécialisé construit dans le harness avec un rôle,
    des capacités et un prompt structuré :
      - CodeAgent programme, débogue et pilote l'environnement de développement
        et le système Windows (computer_use) ;
      - TestAgent exécute et analyse les suites de tests ;
      - ReviewAgent (assisté d'IndependentCritic sur contexte vierge) relit et
        audite ;
      - ResearchAgent analyse les sources locales/Web et récupère des documents
        authentifiés.
  - Un Provider transporte les demandes entre un Agent et un LLM. Le Provider
    n'est pas un Agent.
  - Le ModelRouter choisit un Provider selon l'Agent, l'intention et la
    complexité, avec gestion de débit (RateLimitManager), circuit breaker et
    repli automatique (failover).
  - L'Orchestrator choisit l'Agent (AgentSelector), lui attribue le Provider
    puis coordonne la mission.
  - Le ToolGateway (core/tool_gateway.py) centralise l'accès à toutes les
    capacités locales et Windows, évalue chaque appel via le PolicyEngine
    (core/policy_engine.py), applique le Human-In-The-Loop (HITL) et trace
    chaque action horodatée dans workspace/.harness/operator_audit.jsonl.
  - Le Harness réunit l'orchestrateur, les agents, les providers, le Tool
    Gateway, le Policy Engine, la mémoire persistante, la bibliothèque et le
    vérificateur déterministe (Verifier).

2. Lancer NeoHarness AI (Interface Web & CLI)

2.1 Lancer l'Interface Web Opératoire (--ui)

Dans PowerShell :

cd "$HOME\Desktop\my_ai_harness"
python -B main.py --ui --port 8765

Puis ouvre http://127.0.0.1:8765 dans ton navigateur. L'interface Web propose :

  - Mode Clair pierre chaude par défaut et bascule Mode Sombre instantanée ;
  - 3 modes d'exécution :
      - NeoHarness Agent (mono) : agent autonome avec outils, Computer Use,
        terminal et vérification ;
      - NeoHarness Swift (chat) : discussion directe ultra-rapide sans surcoût
        de tokens d'orchestration ;
      - NeoHarness Deep (multi) : réflexion approfondie et délégation
        multi-agents / graphe DAG ;
  - Palette immédiate des Slash Commands (/) dès la saisie de / ;
  - Bannière Human-In-The-Loop proportionnée pour valider en un clic ([ Refuser
    ], [ Autoriser ], [ Autoriser pour cette session ]) toute action sensible ;
  - Panneau latéral droit unifié : Aperçu de document en direct (PDF compilé via
    Tectonic, Word .docx via Pandoc, HTML interactif sandboxé, graphiques
    Python) et Inspecteur Technique (Modèle, Skills, Activité temps réel,
    Fichiers & Diff, Outils, Mémoire, Bibliothèque, RAG, Contexte) ;
  - Dictée vocale style GPT avec visualisation d'onde audio temps réel
    (AnalyserNode).

2.2 Lancer le CLI interactif

cd "$HOME\Desktop\my_ai_harness"
python -B main.py

Choisis d'abord [1] LOCAL ou [2] API DISTANTE, puis un provider/modèle
réellement détecté. Ensuite saisis une mission libre ou préfixée :

Prends une capture d'écran de cet écran actuel et mets-la sur le bureau
Ouvre l'application Notepad (notepad.exe) et vérifie que la fenêtre est ouverte
researcher: explique ce qu'est un Transformer
coder: analyse le projet, corrige le bug décrit puis lance les tests

Les préfixes coder:, tester:, reviewer: et researcher: fixent l'Agent. Une
demande libre est classée automatiquement par IntentEngine et Planner. Tape exit
pour arrêter.

Le lancement CLI peut aussi recevoir directement une mission ou des options :

python main.py "Analyse les documents du workspace" --workspace "C:\chemin\vers\mon-projet"

Options CLI disponibles : --ui, --port, --replay <run_id>, --agent, --model,
--workspace, --max-iterations, --max-output-tokens, --verbose, --dry-run et
--autonomous.

3. Computer Use Windows, Policy Engine & Human-In-The-Loop

3.1 Boucle fermée Perception → Action → Observation → Vérification

NeoHarness AI ne fonctionne jamais comme une macro aveugle :

1.  Observation (tools/computer_use.py & tools/windows.py) :
      - computer_screenshot : capture l'écran actif (ou une région), identifie
        la fenêtre au premier plan, calcule le hash SHA-256 et peut enregistrer
        l'image directement sur le Bureau Windows réel (save_to_desktop=True,
        compatible Bureau local et OneDrive Bureau).
      - computer_ocr : extrait par OCR (pytesseract) le texte visible à l'écran
        avec les coordonnées exactes (x, y) de chaque élément pour savoir où
        cliquer.
      - computer_compare_screens : compare deux captures avant/après une action
        (PIL.ImageChops.difference) et mesure le ratio de pixels modifiés
        (diff_percent) ainsi que la boîte englobante du changement.
      - window_list, window_active, window_find : inspectent en temps réel
        toutes les fenêtres Windows ouvertes (titre, HWND, PID, dimensions, état
        minimisé/maximisé/actif).
2.  Actions Souris, Clavier & Fenêtres :
      - Souris : computer_mouse_move, computer_click (gauche, droit, milieu,
        double-clic), computer_drag, computer_scroll — avec Fail-Safe d'urgence
        au coin (0, 0).
      - Clavier : computer_type (frappe de texte), computer_press (touche
        individuelle), computer_hotkey (Ctrl+C, Ctrl+V, Ctrl+A, Alt+Tab, Win,
        Enter, Escape...).
      - Fenêtres : window_focus, window_minimize, window_maximize,
        window_restore, window_close.
      - Boucle fermée atomique : computer_action_verified capture l'écran avant,
        exécute l'action, attend la stabilisation, capture l'écran après et
        vérifie mathématiquement si l'écran ou la fenêtre cible a réagi. Si un
        clic n'a eu aucun effet (click_or_action_had_no_effect), l'agent en est
        immédiatement informé pour corriger sa cible.

3.2 Principe de proportionnalité UX & Policy Engine (core/policy_engine.py)

Le niveau de friction est strictement proportionnel au niveau de risque évalué
par le PolicyEngine (qui inspecte à la fois le nom de l'outil et ses arguments)
:

| Niveau de risque               | Actions typiques                                                                                                                                                      | Comportement HITL                                                                                          |
| :----------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------- |
| **`SAFE`** (`READ_ONLY`)       | `read_file`, `list_files`, `computer_screenshot`, `computer_ocr`, `window_list`, `window_active`, `process_list`, `clipboard_get`, `terminal_read`                    | **Exécution directe immédiate** (aucune confirmation inutile)                                              |
| **`LOW`**                      | `copy_to_desktop`, `clipboard_set`, `window_focus`, `window_minimize`, `window_maximize`, `window_restore`, `terminal_start`, `terminal_stop`, `write_file`           | **Exécution directe** pour les outils opérateur simples ; aperçu en mode `EDIT`                            |
| **`MEDIUM`** (`MODERATE`)      | `process_start` (ex: ouvrir VS Code ou Notepad), `package.install`, `terminal_send`, `computer_click`, `computer_type`, `computer_hotkey`, `computer_action_verified` | **Autorisation standard** : `[ Refuser ]`, `[ Autoriser ]`, `[ Autoriser pour cette session ]`             |
| **`HIGH`**                     | `delete_file`, `filesystem.delete_many`, `process_stop`, `window_close`, `registry.modify`                                                                            | **Action à risque** : uniquement `[ Refuser ]` ou `[ Autoriser une fois ]` (pas d'autorisation de session) |
| **`CRITICAL`** (`DESTRUCTIVE`) | `system.shutdown` (`shutdown /s`, `Stop-Computer`, `Restart-Computer`, formatage)                                                                                     | **Confirmation critique systématique** : uniquement `[ Refuser ]` ou `[ Autoriser une fois ]`              |
| **`BLOCKED`**                  | Contournement UAC (`fodhelper`, `eventvwr`), désactivation d'antivirus (`Set-MpPreference`), extraction LSASS/SAM                                                     | **Refus immédiat** par le Policy Engine                                                                    |

3.3 Terminal Interactif Persistant Windows, Processus & Presse-papiers

  - Terminal Persistant (tools/terminal_session.py) : terminal_start,
    terminal_send, terminal_read, terminal_stop, terminal_list maintiennent des
    sessions PowerShell ou CMD vivantes d'un tour à l'autre, détectent
    instantanément la fin d'une commande (sans attente fixe inutile), gèrent les
    prompts interactifs ([Y/n], Confirm) et laissent tourner les serveurs de
    développement (npm run dev) en arrière-plan.
  - Process Manager (tools/process_manager.py) : process_list, process_start,
    process_status, process_stop.
  - Presse-papiers (tools/clipboard.py) : clipboard_get, clipboard_set.

4. Skills et commandes slash (/)

Une commande commençant par / est résolue par SkillRouter et SkillLoader.

4.1 Skills éducatifs (skills/education/)

  - /bacblanc <mission> : génère un sujet complet de Bac Blanc et son barème
    détaillé sur 20 points à partir des gabarits LaTeX officiels et des
    programmes de mathématiques en RAG, compilés automatiquement en PDF via
    Tectonic.
  - /dm <mission> : génère un Devoir Maison structuré en LaTeX/PDF à partir du
    gabarit officiel template_dm.tex.
  - /exercice <mission> : génère une fiche d'exercice ciblée en LaTeX/PDF à
    partir du gabarit officiel template_exercice.tex.

4.2 Skills généralistes et de supervision

| Commande                                                 | Rôle                                                                                                 |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `/analyze <mission>`                                     | Analyse approfondie de documents, d'architecture ou de données avec `ResearchAgent`.                 |
| `/auto <mission>`                                        | Classe la mission, choisit l'agent et le provider optimal via `AgentSelector` et `ModelRouter`.      |
| `/compare <mission>`                                     | Interroge plusieurs providers chargés et produit une synthèse comparative via `ReviewAgent`.         |
| `/context`                                               | Inspecte l'historique, les fichiers suivis et le budget de contexte actif.                           |
| `/debug <mission>`                                       | Reproduit un bug, identifie la cause racine, applique le correctif minimal et relance les tests.     |
| `/diagnostic`                                            | Vérifie localement Skills, agents, tools, workspace, configuration, ressources et statut Git.        |
| `/export markdown\|latex\|pdf\|docx`                     | Exporte le dernier résultat dans `workspace/exports/`.                                               |
| `/memory status` ou `/memory remember ...`               | Gère la mémoire de session, les notes projet et la mémoire persistante cross-session.                |
| `/mode [edit\|plan\|accept\|auto]`                       | Affiche ou change le mode global (`Shift+Tab` en CLI parcourt `EDIT → PLAN → ACCEPT → AUTO`).        |
| `/model [status\|gemini\|openai\|mistral\|ollama\|auto]` | Affiche l'état des providers ou épingle dynamiquement un modèle pour la session.                     |
| `/plan <mission>`                                        | Affiche la prévisualisation du plan d'exécution sans appel modèle ni modification.                   |
| `/refactor <mission>`                                    | Refactorise du code avec `CodeAgent` en vérifiant l'absence de régression par les tests.             |
| `/research <mission>`                                    | Recherche documentaire et Web vérifiée avec distinction `FACT` / `SOURCE` / `INFERENCE` / `UNKNOWN`. |
| `/review <mission>`                                      | Audit critique de code ou de document par `ReviewAgent`.                                             |
| `/route <mission>`                                       | Affiche la décision de routage (`AgentSelector` + `ModelRouter`) puis exécute la mission.            |
| `/test <mission>`                                        | Exécute et analyse la suite de tests avec `TestAgent`.                                               |
| `/workflow <mission>`                                    | Orchestre un workflow multi-étapes ou multi-agents (délégation séquentielle ou graphe DAG).          |

5. Providers et configuration des clés API

5.1 LOCAL — Ollama

Vérifie ollama.exe, le serveur local 127.0.0.1:11434 et le modèle configuré dans
config/config.yaml (qwen3:1.7b par défaut).

5.2 API DISTANTE — Gemini, OpenAI, Mistral & Modèles Personnalisés

Tu peux configurer tes clés API :

  - directement depuis l'interface Web via le bouton Paramètres (⚙) de la barre
    supérieure (POST /api/credentials),
  - dans un fichier .env local (ignoré par Git),
  - ou en variable d'environnement PowerShell :

$env:GEMINI_API_KEY = "votre_cle_gemini"
$env:OPENAI_API_KEY = "votre_cle_openai"
$env:MISTRAL_API_KEY = "votre_cle_mistral"

6. Mémoire Persistante, Bibliothèque & Observabilité

  - Mémoire Persistante (workspace/.harness/persistent_memory.json) : retient
    les règles permanentes, préférences et décisions d'une session à l'autre
    (compréhension naturelle des demandes comme « Mémorise cette règle pour les
    prochaines fois »).
  - Mémoire Réflexive (ReflectiveMemory) : enregistre automatiquement les leçons
    expérientielles lorsque l'agent surmonte un échec d'outil ou de
    vérification.
  - Bibliothèque Intelligente (workspace/.harness/library.json) : indexe et
    organise les documents, notes et ressources produits avec recherche, tags et
    épinglage.
  - Observabilité Opérateur (workspace/.harness/operator_audit.jsonl) :
    journalise chaque action passant par le ToolGateway avec horodatage précis
    (AGENT_CALL, POLICY, HITL, VERIFICATION).
  - Télémétrie & Auto-Audit (workspace/.harness/telemetry.jsonl) : suit la
    latence, les tokens, les erreurs 429 et le taux de réussite des missions.

7. Installation et exécution des tests

7.1 Installation des dépendances

python -m pip install --upgrade -r requirements.txt

7.2 Exécution des suites de tests

Tester spécifiquement l'architecture Opérateur Windows (Computer Use, Policy
Engine, HITL, Tool Gateway, Terminal persistant, Process, Fenêtres,
Presse-papiers) :

python -B -m unittest tests/test_windows_computer_use_agent.py -v

Lancer les suites de validation du noyau, des skills, du multi-agents et de
l'environnement UI :

python -B -m unittest tests/test_runtime.py tests/test_skills.py tests/test_general_skills.py tests/test_multi_agent_runtime.py tests/test_ui_environment.py tests/test_windows_computer_use_agent.py -v

Compiler et vérifier la syntaxe de l'ensemble du dépôt :

python -m compileall -q .

