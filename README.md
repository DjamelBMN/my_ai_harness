# My AI Harness

Un runtime agentique local qui conserve les anciens agents et contrats, et ajoute
une boucle bornée pour planifier, appeler des outils, observer leurs résultats et
vérifier les critères déterministes avant de conclure.

```text
Utilisateur
    ↓
Orchestrator → Planner → TaskState
    ↓
AgentLoop : PERCEIVE → PLAN → ACT → OBSERVE → VERIFY → CORRECT → DELIVER
    ↓
CodeAgent / TestAgent / ReviewAgent / ResearchAgent
    ↓
ModelRouter (intention + complexité, avec repli sur le modèle de session)
    ↓
OpenAIProvider / GeminiProvider / OllamaProvider
    ↓
ToolRegistry → WorkspaceFilesystem / Documents / Python tests / Git
    ↑                 ↓
Agent ← résultats d'outils ← PermissionPolicy
```

## LLM, Agent et Harness

- Un **LLM** génère du texte ou des appels d'outils : GPT, Gemini ou Qwen.
- Un **Agent** est un programme que nous construisons avec un rôle et un prompt.
  CodeAgent programme, TestAgent teste, ReviewAgent relit et ResearchAgent analyse.
- Un **Provider** transporte les demandes entre un Agent et un LLM. Le Provider
  n'est pas un Agent.
- Le **ModelRouter** choisit un Provider selon l'Agent, l'intention et la complexité.
- L'**Orchestrator** choisit l'Agent, lui attribue le Provider puis coordonne la mission.
- Un **Tool** permet de lire ou modifier le workspace, exécuter les tests ou interroger
  Git. Le registre valide le nom et les arguments avant l'exécution.
- Le **Harness** réunit l'orchestrateur, les agents, les providers, les outils, le
  contexte et les contrôles de sécurité.

Un LLM n'est donc pas un agent. La réponse finale est rédigée par l'Agent après
réception des observations du modèle et des outils.

## Lancer le programme

Dans PowerShell :

```powershell
cd "$HOME\Desktop\my_ai_harness"
python main.py
```

Choisis d'abord LOCAL ou API DISTANTE, puis un provider/modèle réellement détecté.
Ensuite saisis une mission, par exemple :

```text
researcher: explique ce qu'est un Transformer
coder: analyse le projet, corrige le bug décrit puis lance les tests
```

Les commandes `coder:`, `tester:`, `reviewer:` et `researcher:` fixent l'Agent.
Une demande libre est classée par le Planner. Le mot isolé `code` demande une
clarification, car il ne précise pas s'il s'agit de programmation ou d'une recherche.
Tape `exit` pour arrêter.

### Skills et commandes slash

Une commande commençant par `/` est résolue avant les agents explicites et le
Planner. Par exemple :

```text
/bacblanc suite fonction espace
```

Le Harness découvre les dossiers de `skills/` contenant un `skill.md`. Le
`SkillRegistry` les indexe, le `SkillRouter` sépare la commande de la mission,
et le `SkillLoader` charge le manifeste, les règles, le YAML et l'agent éventuel.
Une commande inconnue affiche la liste des Skills disponibles et n'est jamais
envoyée silencieusement à `ResearchAgent`.

Le Skill `bacblanc` porte les règles métier dans `skills/bacblanc/skill.md` et
`rules.md`, sa configuration dans `config.yaml`, et son `BacBlancAgent` dans
`agent.py`. Il n'est plus découvert comme agent générique dans `agents/`.
`rag/` et `templates/` sont des espaces vides prévus pour de vraies ressources;
le Harness n'invente ni documents RAG ni templates. Les règles du Skill
restreignent ses tools et les agents secondaires autorisés.

Pour ajouter un Skill, crée un dossier `skills/mon_skill/` avec un `skill.md`.
Ajoute `agent.py` si le Skill nécessite un agent spécialisé et un `config.yaml`
si tu veux déclarer son nom affiché, ses tools, capacités ou règles de délégation.
Il sera découvert au prochain démarrage sans modifier `main.py` ni le routeur
générique. Un Skill sans agent est détectable, mais le lancement d'une mission
échoue clairement jusqu'à ce qu'un agent compatible soit fourni.
Le fichier Python `agent.py` est exécuté au chargement du Skill : n'ajoute que du
code de confiance dans ce dossier.

Le lancement peut aussi recevoir une mission :

```powershell
python main.py "Analyse les documents du workspace"
```

Le menu du mode et du LLM reste présenté avant l'exécution de cette mission.

## Providers et sélection du modèle

### LOCAL — Ollama

Le provider vérifie `ollama.exe`, le serveur local `127.0.0.1:11434` et le modèle
configuré dans `config/config.yaml`. Il ne télécharge aucun modèle et n'appelle pas
Internet. La configuration actuelle sélectionne `qwen3.5:4b-q4_K_M`.

### API DISTANTE — OpenAI et Gemini

OpenAI utilise `gpt-5-mini` configuré dans `config/config.yaml` et la variable
d'environnement `OPENAI_API_KEY`. Gemini utilise le SDK officiel `google-genai` et
`GEMINI_API_KEY`. Claude reste une interface non connectée et n'est jamais annoncé
comme disponible.

Quand Gemini est choisi, le menu récupère auprès de l'API les modèles accessibles
qui prennent en charge `generateContent`, puis te laisse sélectionner leur ID exact.
La liste inclut `gemini-3.5-flash-lite` lorsqu'il est exposé pour la clé utilisée.
Google le documente comme modèle stable avec function calling et Search grounding :
[modèles Gemini](https://ai.google.dev/gemini-api/docs/models),
[Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

Dans `config/config.yaml`, le champ `providers.gemini.model` est la préférence du
routeur lorsqu'aucun choix Gemini direct n'a été fait. Le routeur peut utiliser
`gemini_flash_lite` pour les demandes simples si ce modèle est disponible, et
`gemini` pour les demandes plus complexes. Les routes sont des préférences : si un
provider n'est pas disponible, le routeur revient au provider de session choisi.

Configure les clés dans la session PowerShell. La valeur n'est ni demandée par le
programme, ni affichée, ni écrite dans le projet :

```powershell
$secureKey = Read-Host "Clé API OpenAI" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
Remove-Variable secureKey

$secureGeminiKey = Read-Host "Clé API Gemini" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $secureGeminiKey).Password
Remove-Variable secureGeminiKey

python main.py
```

Une souscription ChatGPT n'est pas une clé API OpenAI. Le provider OpenAI utilise
l'API OpenAI et sa facturation distincte.

## Boucle agentique et vérification

Pour chaque mission, le Planner classe l'intention, assigne un Agent et crée des
étapes de départ. `TaskState` conserve l'objectif, les contraintes, le plan, les
observations, les résultats d'outils, les fichiers, les erreurs et les vérifications.
L'AgentLoop limite le nombre d'itérations, de relances et d'appels d'outils.

OpenAI Responses, Gemini function calling et Ollama `/api/chat` conservent leur
historique natif pour les tool calls. Gemini renvoie les objets `Content` et `Part`
complets au tour suivant afin de préserver les `thought_signature`; les pensées ne
sont pas affichées comme texte. Les appels d'outils Gemini sont limités à une boucle
contrôlée par le harness, et non exécutés automatiquement par le SDK. Google décrit
le format et la conservation des signatures dans sa
[documentation function calling](https://ai.google.dev/gemini-api/docs/function-calling)
et sa [documentation des thought signatures](https://ai.google.dev/gemini-api/docs/thought-signatures).

Les vérifications s'appuient sur des observations concrètes :

- analyse de fichier : un `read_file` ou `read_document` a réellement réussi ;
- modification : le fichier est relu et son hash correspond à l'écriture, puis une
  suite non vide doit se terminer avec un code nul ;
- correction de bug : une suite non vide doit aussi échouer avant la première
  modification ;
- tests : `unittest` doit avoir exécuté au moins un test ; zéro test n'est pas un succès ;
- recherche Web : Gemini doit retourner des sources HTTPS de son grounding.

Le programme affiche `answered` quand il a répondu sans vérification déterministe,
`verified` quand les contrôles demandés ont réussi sans test, et `success` seulement
quand une suite de tests non vide a réussi. Une réponse linguistique ou une lecture
de document n'est pas présentée comme un test logiciel.

Les échecs d'outil et de vérification sont renvoyés au modèle pour une tentative de
correction bornée. Une modification n'est déclarée vérifiée qu'après relecture et
tests. Les tâches simples de réponse peuvent ne pas appeler d'outil.

## Outils, workspace et autorisations

Outils enregistrés :

- Fichiers : `list_files`, `find_file`, `search_files`, `read_file`, `read_document`,
  `write_file`, `patch_file`, `delete_file`, `move_file`.
- Exécution : `run_tests` et `run_python` (scripts Python présents dans le workspace).
- Git : statut, branche courante, création de branche, commit des fichiers staged et merge.
- Web : Gemini Google Search grounding quand la mission demande des sources. Il n'y a
  pas de navigateur Web générique configuré; une recherche sans source ne sera pas
  présentée comme vérifiée.

Par défaut, l'accès se limite au dossier `my_ai_harness`. Les chemins `..`, liens
symboliques, `.env*`, `.git`, dossiers de secrets et caches d'exécution sont refusés
ou masqués. Les textes extraits sont bornés et les motifs courants de clés sont
masqués. Les formats pris en charge sont TXT, MD, JSON, YAML, CSV, PDF, DOCX, XLSX,
PPTX, HTML, CSS, JS, TS et PY. Les PDF scannés nécessitent PyMuPDF, Pillow, pytesseract
et le programme Tesseract installé ; sans OCR utilisable, la lecture échoue clairement.

Écriture, suppression, Git mutateur, `run_tests` et `run_python` demandent une
confirmation. `--dry-run` bloque toutes ces actions. `--autonomous` supprime ces
confirmations et ne doit être utilisé que si tu veux réellement autoriser les actions.
Les scripts et tests s'exécutent avec les droits Windows de l'utilisateur : le harness
retire les variables d'environnement de secrets usuelles, mais ne constitue pas un
sandbox système pour du code hostile.

Dans la CLI, Git passe par `GitWorkspace` et est exécuté réellement après confirmation.
Les anciennes fonctions directes `tools.git.status()`/`branch()` restent des stubs de
compatibilité et ne sont pas utilisées par le runtime.

Pour travailler sur un autre projet, donne explicitement son chemin comme workspace :

```powershell
python main.py --workspace "C:\chemin\vers\mon-projet"
```

Le dossier doit déjà exister. Sans cette option, le harness ne parcourt pas les autres
projets du PC.

Options disponibles : `--agent`, `--model`, `--workspace`, `--max-iterations`,
`--max-output-tokens`, `--verbose`, `--dry-run` et `--autonomous`.

## Mémoire et observabilité

- **Task memory** : `TaskState`, en RAM pendant une mission.
- **Session memory** : contexte compacté à cinq entrées et environ 6 000 caractères.
- **Long-term memory** : désactivée; aucun historique n'est persisté dans un fichier.
- Les actions et résultats sont visibles dans le terminal et dans les observations
  structurées renvoyées par l'AgentLoop. Il n'y a pas de journal persistant des prompts.

Le contrôle de coût s'appuie sur `--max-iterations`, `--max-output-tokens`, les
timeouts et un nombre borné de retries. Le SDK OpenAI et Gemini ont des reprises
bornées; Ollama est limité par le timeout du provider. Aucun budget monétaire ne peut
être calculé à partir de ces limites.

## Dépendances et tests

Installe les dépendances listées si elles ne sont pas déjà disponibles :

```powershell
python -m pip install -r requirements.txt
```

La suite locale n'a besoin d'aucune clé et ne fait pas d'appel réseau :

```powershell
python -m unittest discover -s tests -t . -v
```

Les tests provider utilisent des clients simulés de test; ils ne valident pas l'accès
au compte OpenAI ou Gemini. Un vrai test distant nécessite une clé configurée.

## Architecture actuelle et limites

- `main.py` : CLI, choix du mode/modèle, configuration workspace et autorisations.
- `core/orchestrator.py` : garde aussi l'ancienne méthode `run(Task) -> str` et expose
  `run_agentic(Task, AgentLoop) -> AgentResult`.
- `core/agent_loop.py`, `planner.py`, `task_state.py`, `verifier.py` : cycle, plan,
  état structuré et vérifications.
- `core/router.py` : parse la configuration simple et route par intention/complexité.
- `agents/` : CodeAgent, TestAgent, ReviewAgent et ResearchAgent.
- `skills/` : registre, chargeur, routeur slash et Skill métier BacBlanc.
- `providers/` : Ollama, OpenAI, Gemini; Claude et LocalProvider restent non connectés.
- `tools/` : filesystem, extraction documentaire, exécution Python/tests, Git, recherche.

Le runtime prend en charge la délégation séquentielle demandée par un agent via le
tool virtuel `delegate_to_agent`; il ne lance pas encore automatiquement toute
combinaison secondaire sans instruction du Planner ou de l'agent. La classification
d'intention est une estimation heuristique explicable, pas un classifieur sémantique
universel. Les tools Web disponibles dépendent du provider (Gemini Search grounding
est distinct d'un navigateur générique); le runtime ne garantit pas l'ouverture de
toute page citée. La mémoire longue reste désactivée, Claude n'est pas connecté, et
les programmes s'exécutent avec les droits Windows du compte : le workspace borné et
le nettoyage de variables secrètes ne constituent pas une sandbox OS.

### Ajouter un agent

Crée un module `agents/mon_agent.py` et une classe qui hérite de `BaseAgent` ou
`Agent`. Déclare `name`, `description`, `capabilities` et, si utile,
`supported_intents`/`allowed_tools`. Un constructeur sans argument est découvert par
`AgentRegistry`; si aucun `routing_key` n'est déclaré, il est construit depuis le nom
de la classe. Les providers et le ModelRouter ne doivent pas être importés dans
l'agent. Pour une capacité spécifique, exprime-la dans les métadonnées : le registre
et le sélecteur l'exposeront sans modification de `core/router.py`.

### Tests du runtime multi-agents

```powershell
python -m compileall -q .
python -m unittest discover -v
```

Le test E2E utilise des providers de test pour rendre les choix de délégation
déterministes, mais exécute réellement le registre, l'orchestrateur, la boucle,
`read_document`, `run_tests`, le workspace et le vérificateur. Il ne valide pas un
appel réseau OpenAI/Gemini ni le comportement spontané d'un LLM réel en délégation.
