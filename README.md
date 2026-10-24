# NeoHarness AI — Agent Operating Environment

> **Créé et développé par Djamel BENMAKHLOUF**
> Un environnement agentique multi-modèles de production (Gemini, Ollama, OpenAI, Mistral), orchestrant agents autonomes, 18 skills canoniques, outils réels, RAG, Tectonic LaTeX et vérification déterministe — Zéro simulation.

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
`agent.py`. Il n'est plus découvert comme agent générique dans `agents/`. Le
SkillLoader lit réellement les deux gabarits LaTeX, et extrait les ressources RAG
compatibles lorsqu'elles existent. Le RAG actuel est vide; aucune source n'est
inventée.

Pour créer un sujet complet, BacBlancAgent contrôle la présence des quatre
exercices, du barème à 20 points, du corrigé complet, des gabarits remplis et de
la relecture complète par ReviewAgent. Il peut écrire les fichiers LaTeX dans le
workspace avec confirmation. Si un quota, une limite du provider ou des itérations
empêche la fin, le runtime remet le meilleur contenu conservé avec un avertissement
explicite et un statut incomplet; il ne le présente jamais comme un livrable terminé.

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

### Skills généralistes

Les Skills généralistes sont découverts dans `skills/<nom>/skill.md`. Les commandes
qui exécutent une mission utilisent les agents, le Planner, le ModelRouter et
l'AgentLoop déjà présents; les commandes de supervision disposent d'un
`command.py` dédié chargé par `SkillLoader`.
Les Skills explicites gardent la priorité; si aucun Skill ne porte le nom demandé,
`/coder`, `/tester`, `/reviewer` et `/researcher` sont résolus vers l'agent enregistré.

| Commande | Rôle |
| --- | --- |
| `/model status`, `/model gemini`, `/model mistral`, `/model openai`, `/model ollama`, `/model auto` | Affiche l'état des providers, épingle un provider déjà disponible dans la session, ou réactive le routage configuré. Un modèle peut être précisé après le provider lorsqu'il a été validé par celui-ci. |
| `/auto <mission>` | Classe la mission, choisit un agent enregistré puis un provider par le routeur. Les tools sont limités à ceux requis par la décision d'intention et autorisés par le Skill. |
| `/compare <mission>` | Interroge jusqu'à quatre providers chargés, garde les réponses en cas d'échec partiel, puis demande une synthèse au ReviewAgent. Les appels distants peuvent être facturés. |
| `/route <mission>` | Affiche la sélection réelle de l'AgentSelector et du ModelRouter puis exécute avec l'AgentLoop. |
| `/workflow <mission>` | Réutilise le cycle AgentLoop, ses outils, sa vérification et la délégation lorsqu'elle est demandée par l'agent. |
| `/plan <mission>` | Affiche une prévisualisation du Planner sans appel de modèle ni modification. |
| `/diagnostic` | Vérifie localement Skills, agents, tools, workspace, configuration, ressources et statut Git. Il compte les fichiers de tests, mais ne lance pas les tests et ne fait pas d'appel API de diagnostic. |
| `/research <mission>`, `/analyze <mission>`, `/debug <mission>`, `/review <mission>`, `/test <mission>`, `/refactor <mission>` | Réutilise respectivement ResearchAgent, ResearchAgent, CodeAgent, ReviewAgent, TestAgent et CodeAgent avec les règles et permissions de chaque Skill. Gemini Search grounding n'est disponible que si la mission l'exige et que Gemini est le provider utilisé. |
| `/context` | Compte l'historique, les fichiers et ressources suivis sans afficher le contenu de l'historique. |
| `/memory status` ou `/memory remember ...` | Gère les notes temporaires, décisions et préférences de session. Une note de projet ne persiste que si elle est explicitement demandée et que l'écriture est autorisée. Les secrets détectés sont refusés. |
| `/export markdown`, `/export latex`, `/export pdf`, `/export docx` | Convertit le dernier résultat en fichier dans `workspace/exports/`; l'écriture passe par la politique de permission. |
| `/mode`, `/mode edit`, `/mode plan`, `/mode accept`, `/mode auto` | Affiche ou change le mode global, appliqué à tous les Skills, agents, tools et délégations. `Shift+Tab` parcourt EDIT → PLAN → ACCEPT → AUTO. |

### Modes de travail

Le mode initial est **ACCEPT**. Il est distinct du choix LOCAL/API du provider.

- **EDIT** : autorise directement `write_file` et `patch_file` après affichage
  dans le terminal du chemin et de l'action. Les outils plus risqués restent
  soumis aux permissions habituelles.
- **PLAN** : bloque au niveau central les tools mutateurs, y compris ceux que le
  modèle demanderait malgré leur absence des schémas. Le workspace reste lisible.
- **ACCEPT** : comportement normal; les opérations sensibles demandent
  confirmation via la politique existante.
- **AUTO** : active le mécanisme `autonomous` déjà présent dans la politique de
  permissions pour permettre l'enchaînement des actions autorisées. `--dry-run`
  reste prioritaire.

L'option CLI historique `--autonomous` reste un forçage explicite conservé pour
compatibilité. Le panneau des modes apparaît au démarrage et le mode courant reste
visible dans l'invite. `Shift+Tab` est intercepté dans `PromptSession` avec une
liaison clavier `BackTab`, indépendamment du Skill actif; `msvcrt` reste le fallback
Windows. Les événements de mode sont traduits en français par le même observateur
générique que les outils et les providers.

`/model status` ne révèle jamais la valeur d'une clé. Il vérifie réellement Ollama
et le modèle local; pour les providers distants, il indique si l'instance et les
credentials sont chargées, sans prétendre que l'API a été sondée. La sélection à
chaud ne concerne que les providers chargés au démarrage (sauf détection locale
d'Ollama demandée explicitement). `/model auto` rétablit les routes configurées.

`/auto` utilise le classifieur d'intention et les routes configurées; il ne calcule
pas un coût financier et ne mesure pas automatiquement les performances des modèles.
`/workflow` donne les consignes de séquencement au même AgentLoop : le plan est
adaptatif, et un agent secondaire n'est exécuté que si une délégation réelle est
demandée et autorisée. Les événements de l'AgentLoop (`provider.started`,
`tool.completed`, `delegation.*`, `verification.*`, `delivery.*`) sont traduits
en messages français génériques dans le terminal; ils peuvent aussi alimenter une
future interface sans logique propre à BacBlanc.

## Providers et sélection du modèle

### LOCAL — Ollama

Le provider vérifie `ollama.exe`, le serveur local `127.0.0.1:11434` et le modèle
configuré dans `config/config.yaml`. Il ne télécharge aucun modèle et n'appelle pas
Internet. La configuration actuelle sélectionne `qwen3.5:4b-q4_K_M`.

### API DISTANTE — OpenAI, Gemini et Mistral

OpenAI utilise `gpt-5-mini` configuré dans `config/config.yaml` et la variable
d'environnement `OPENAI_API_KEY`. Gemini utilise le SDK officiel `google-genai` et
`GEMINI_API_KEY`. Mistral utilise le SDK officiel `mistralai` et `MISTRAL_API_KEY`.
Claude reste une interface non connectée et n'est jamais annoncé comme disponible.

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

Lorsque Mistral est configuré et que `MISTRAL_API_KEY` est présente, le menu appelle
l'API officielle de liste des modèles et propose tous les modèles accessibles qui
prennent en charge le chat. Tu peux choisir leur ID exact au démarrage ou avec
`--model`. `providers.mistral.model` dans la configuration ne sert que de préférence
de tri. Le provider prend aussi en charge les tool calls natifs lorsque le modèle les
déclare; les modèles sans cette capacité restent utilisables pour les réponses texte.
Le décodeur Brotli du transport HTTP doit être en version `1.2.0` ou plus récente.
Cette dépendance est déclarée dans `requirements.txt`; pour corriger notamment
`process() takes no keyword arguments`, mets à jour avec
`python -m pip install --upgrade -r requirements.txt`.
Références officielles : [démarrage API Mistral](https://docs.mistral.ai/getting-started/quickstarts/developer/first-api-request),
[API de liste des modèles](https://docs.mistral.ai/api/endpoint/models) et
[catalogue des modèles](https://docs.mistral.ai/models).

Configure les clés dans la session PowerShell. La valeur n'est ni demandée par le
programme, ni affichée, ni écrite dans le projet :

```powershell
$secureKey = Read-Host "Clé API OpenAI" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
Remove-Variable secureKey

$secureGeminiKey = Read-Host "Clé API Gemini" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $secureGeminiKey).Password
Remove-Variable secureGeminiKey

$secureMistralKey = Read-Host "Clé API Mistral" -AsSecureString
$env:MISTRAL_API_KEY = [System.Net.NetworkCredential]::new("", $secureMistralKey).Password
Remove-Variable secureMistralKey

python main.py
```

Pour mettre à niveau le SDK Mistral et installer les dépendances, lance
`python -m pip install --upgrade -r requirements.txt`.

Une souscription ChatGPT n'est pas une clé API OpenAI. Le provider OpenAI utilise
l'API OpenAI et sa facturation distincte.

## Boucle agentique et vérification

Pour chaque mission, le Planner classe l'intention, assigne un Agent et crée des
étapes de départ. `TaskState` conserve l'objectif, les contraintes, le plan, les
observations, les résultats d'outils, les fichiers, les erreurs et les vérifications.
L'AgentLoop limite le nombre d'itérations, de relances et d'appels d'outils.

OpenAI Responses, Gemini function calling, Mistral Chat Completions et Ollama `/api/chat` conservent leur
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

En mode ACCEPT, écriture, suppression, Git mutateur, `run_tests` et `run_python`
demandent une confirmation. En EDIT, `write_file` et `patch_file` sont précédés
d'un aperçu et peuvent être appliqués directement; les autres actions sensibles
gardent leur confirmation. PLAN bloque toutes les actions mutatrices. `--dry-run`
reste un verrou absolu. `--autonomous` est un consentement CLI distinct qui supprime
les confirmations mutatrices et ne doit être utilisé que si tu l'autorises. Le mode
AUTO active le même mécanisme de permissions pour la session et le désactive en
quittant AUTO, sauf si le forçage CLI explicite est actif.
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
- **Mémoire projet** : uniquement les notes explicitement ajoutées par `/memory remember project ...`, après permission; le fichier est `.harness/project_memory.json` dans le workspace. L'historique des conversations n'est pas persisté.
- Les actions et résultats sont visibles dans le terminal et dans les observations
  structurées renvoyées par l'AgentLoop. Il n'y a pas de journal persistant des prompts.

Le contrôle de coût s'appuie sur `--max-iterations`, `--max-output-tokens`, les
timeouts et un nombre borné de retries. Le SDK OpenAI et Gemini ont des reprises
bornées; Ollama est limité par le timeout du provider. Aucun budget monétaire ne peut
être calculé à partir de ces limites.

## Dépendances et tests

Par défaut, l'AgentLoop autorise 20 tours. BacBlanc configure un budget de sortie
de 16 384 tokens par tour et 20 tours afin de laisser terminer ses documents longs;
ce budget est temporaire et ne s'applique pas aux autres agents. Les options de
ligne de commande restent disponibles. Le terminal indique la taille de la réponse,
les appels d'outils et les continuations partielles de chaque tour.

Installe les dépendances listées si elles ne sont pas déjà disponibles :

```powershell
python -m pip install --upgrade -r requirements.txt
```

La suite locale n'a besoin d'aucune clé et ne fait pas d'appel réseau :

```powershell
python -m unittest discover -s tests -t . -v
```

Les tests provider utilisent des clients de test; ils ne valident pas l'accès aux
comptes OpenAI, Gemini ou Mistral. Un vrai test distant nécessite une clé configurée.

## Architecture actuelle et limites

- `main.py` : CLI, choix du mode/modèle, configuration workspace et autorisations.
- `core/orchestrator.py` : garde aussi l'ancienne méthode `run(Task) -> str` et expose
  `run_agentic(Task, AgentLoop) -> AgentResult`.
- `core/agent_loop.py`, `planner.py`, `task_state.py`, `verifier.py` : cycle, plan,
  état structuré et vérifications.
- `core/router.py` : parse la configuration simple et route par intention/complexité.
- `agents/` : CodeAgent, TestAgent, ReviewAgent et ResearchAgent.
- `skills/` : registre, chargeur, routeur slash et Skill métier BacBlanc.
- `providers/` : Ollama, OpenAI, Gemini et Mistral; Claude et LocalProvider restent non connectés.
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
