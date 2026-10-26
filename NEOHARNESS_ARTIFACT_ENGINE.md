# NEOHARNESS UNIVERSAL ARTIFACT ENGINE

> **Architecture, Runtimes, Auto-Réparation & Rendu Visuel Temps Réel de NeoHarness AI**  
> *Auteur : Djamel BENMAKHLOUF — NeoHarness AI Core Engineering*  
> *Règle absolue du système : Zéro simulation, zéro mock, exécution et vérification réelles.*

---

## 1. Philosophie & Objectifs

Le **Universal Artifact Engine** de NeoHarness AI transforme l'agent conversationnel en un véritable atelier de production et de livraison logicielle et documentaire.

Contrairement aux interfaces classiques qui se contentent d'afficher des blocs de texte Markdown ou des extraits de code statiques, NeoHarness applique le cycle de vie complet :

$$\text{Générer} \longrightarrow \text{Écrire} \longrightarrow \text{Compiler / Exécuter réellement} \longrightarrow \text{Vérifier} \longrightarrow \text{Auto-réparer si nécessaire} \longrightarrow \text{Afficher en direct} \longrightarrow \text{Livrer}$$

### Principes directeurs :
1. **Zéro simulation** : chaque script est exécuté par un runtime réel (Python, Node.js, Tectonic) ; chaque fichier binaire ou vectoriel est validé par des parsers stricts.
2. **Intelligence de production : `Chat ≠ Artefact`** : répondre dans le chat ne produit jamais d'artefact documentaire parasite. Les salutations, questions d'analyse, explications conceptuelles et modifications de code n'engendrent aucun fichier PDF, LaTeX ou Word. Un artefact n'est forgé que si l'utilisateur le demande explicitement ou si un skill de livrable est engagé.
3. **Auto-réparation déterministe & cognitive** : en cas d'erreur de syntaxe (balise XML non fermée, préambule LaTeX incomplet, virgule JSON résiduelle), le système tente une réparation déterministe immédiate, puis peut solliciter le LLM pour correction autonome avant livraison.
4. **Expérience unifiée à la Claude** : génération en direct dans le chat $\rightarrow$ détection immédiate de l'artefact $\rightarrow$ ouverture automatique du panneau latéral droit avec le rendu réel opérationnel.
5. **Contrôle total par l'utilisateur** : 4 vues contextuelles (**Aperçu**, **Code source**, **Fichiers générés**, **Console & Logs**) avec édition en place et ré-exécution instantanée.
6. **Synchronisation avec la Bibliothèque Intelligente** : tout artefact validé ou produit est instantanément catalogué dans la Bibliothèque (`workspace/.harness/library.json`), avec métadonnées, résumé, tags et lien mémoire persistant.

---

## 2. Architecture Globale

```
                             ┌──────────────────────────────────────┐
                             │    Assistant IA (Modèle & Skills)    │
                             └──────────────────┬───────────────────┘
                                                │ Blocs ```lang ou fichiers
                                                ▼
                             ┌──────────────────────────────────────┐
                             │      UniversalArtifactEngine         │
                             │ (Extraction, Routage, Événements)    │
                             └──────┬────────────────────────┬──────┘
                                    │                        │
               ┌────────────────────┴──────────┐             │ Versioning & Rollback
               ▼                               ▼             ▼
   ┌───────────────────────┐       ┌───────────────────────┐ ┌───────────────────────┐
   │ WorkspaceFilesystem   │       │ NormalizedEventBus    │ │  Historique Versions  │
   │ (Frontière sécurisée) │       │ (SSE temps réel)      │ │  (Snapshots & Diff)   │
   └───────────────────────┘       └───────────────────────┘ └───────────────────────┘
               │                               │
               ▼                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                Handlers Spécialisés Réels              │
   │  • HtmlArtifactHandler     • LatexArtifactHandler      │
   │  • PythonArtifactHandler   • SvgArtifactHandler        │
   │  • MermaidArtifactHandler  • JsonArtifactHandler       │
   │  • CsvArtifactHandler      • MarkdownArtifactHandler   │
   │  • ImageArtifactHandler    • PdfArtifactHandler        │
   └───────────────────────────────────┬────────────────────┘
                                       │ Rendu visuel & Métadonnées
                                       ▼
   ┌────────────────────────────────────────────────────────┐
   │             Panneau Droit Unifié (UI NeoHarness)       │
   │  [Aperçu]        [Code Source]    [Fichiers] [Console] │
   │  • PDF.js        • Éditeur live   • Liste    • Stdout  │
   │  • Sandbox Web   • Validation     • Liens    • Stderr  │
   │  • Mermaid / SVG • Sauvegarde     • Export   • Timing  │
   │  • Table / JSON  • Diff versions  • Téléch.  • Retcode │
   └────────────────────────────────────────────────────────┘
```

---

## 3. Modèles de Données Centraux (`core/artifacts/models.py`)

### `ArtifactType`
Énumération des types reconnus :
- `HTML` : Applications et widgets web interactifs (HTML5 + CSS3 + JS ES2022).
- `PDF` : Documents compilés haute fidélité (LaTeX $\rightarrow$ Tectonic).
- `LATEX` : Sources typographiques LaTeX (`.tex`).
- `PYTHON` : Scripts, simulations scientifiques, tracés de données.
- `SVG` : Graphismes et diagrammes vectoriels XML scalables.
- `MERMAID` : Diagrammes relationnels, organigrammes, séquences, diagrammes d'état.
- `JSON` : Jeux de données structurés, configurations, schémas.
- `CSV` : Tableaux de données délimités (virgule, point-virgule, tabulation).
- `MARKDOWN` : Documentation enrichie avec formules mathématiques KaTeX.
- `IMAGE` : Images matricielles HD (`PNG`, `JPEG`, `WebP`, `GIF`, `BMP`).

### `ArtifactStatus`
Cycle d'états d'un artefact :
`PENDING` $\rightarrow$ `COMPILING` / `EXECUTING` $\rightarrow$ `VERIFYING` $\rightarrow$ `READY` (ou `REPAIRED` si auto-corrigé, `ERROR` si échec).

### `ArtifactExecution`
Capture réelle de l'exécution :
- `command` : Commande shell exécutée dans le workspace (ex: `python script.py`).
- `exit_code` : Code de retour processus (`0` pour succès).
- `stdout` : Sortie standard capturée.
- `stderr` : Sortie d'erreur capturée.
- `duration_ms` : Durée précise d'exécution en millisecondes.
- `log` : Journal combiné horodaté.

### `ArtifactVersion` & Rollback
Chaque mise à jour d'un artefact capture :
- `version_id` incrémental (1, 2, ...).
- `timestamp` ISO 8601.
- `source_hash` SHA-256 du contenu source.
- `source_content_snippet` extrait pour audit rapide.
- `summary` raison du changement (modification utilisateur, compilation, auto-réparation).

---

## 4. Runtimes & Handlers Réels (`core/artifacts/handlers.py`)

| Format | Runtime / Moteur Réel | Validation & Vérification Réelle | Auto-Réparation Intelligente |
| :--- | :--- | :--- | :--- |
| **HTML** | Node.js `node --check` + Iframe Sandbox | Analyse syntaxique JS/HTML, structure DOM, injection d'intercepteur d'erreurs runtime | Injection de `<!DOCTYPE html>`, `<html>`, `<body>`, fermeture des balises orphelines, réparation par LLM si activée |
| **LaTeX** | Tectonic CLI (`tectonic -X compile`) | Compilation réelle en PDF, vérification de l'en-tête `%PDF-` et de la remorque `%%EOF` | Détection et ajout automatique des packages manquants (`inputenc`, `amsmath`, `geometry`), fermeture de `\begin{document}` |
| **Python** | Interpréteur Python 3 (`subprocess`) | Exécution réelle dans le dossier racine du workspace, vérification de la syntaxe via `ast.parse()`, timeout paramétrable | Détection des dépendances manquantes, capture stdout/stderr, découverte automatique des graphiques générés (`matplotlib.pyplot.savefig`) |
| **SVG** | Python `xml.etree.ElementTree` | Parsing strict du document XML, vérification de la balise racine `<svg>`, détection des attributs `viewBox`, `width`, `height` | Injection automatique du namespace `xmlns="http://www.w3.org/2000/svg"`, auto-fermeture des balises graphiques (`circle`, `rect`, `path`) et balise fermante `</svg>` |
| **Mermaid** | Moteur syntaxique + Mermaid.js 10 | Détection du type de diagramme canonique (`graph`, `flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram`, etc.) | Rééquilibrage automatique des parenthèses `()`, crochets `[]` et accolades `{}` sur chaque déclaration de nœud |
| **JSON** | Moteur natif Python `json.loads` | Parsing strict, extraction du nombre de clés/éléments, typage de la racine (`object` vs `array`) | Suppression déterministe des virgules traînantes résiduelles (trailing commas), normalisation des guillemets simples en doubles |
| **CSV** | Moteur `csv.Sniffer` / parser sécurisé | Détection automatique du délimiteur (`,`, `;`, `\t`), comptage certifié des colonnes et des lignes, vérification d'homogénéité | Détection et signalement des lignes asymétriques |
| **Markdown** | Parser lexical + KaTeX | Comptage des niveaux de titres (`#` à `####`), détection des équations inline `$...$` et display `$$...$$`, détection des tableaux | Normalisation des blocs de code et des sauts de ligne |
| **Image** | PIL / Pillow (ou inspection binaire) | Détection du format réel, extraction des dimensions (largeur $\times$ hauteur en pixels) et du poids octets | Vérification de l'intégrité de l'en-tête graphique |
| **PDF** | PDF.js v3 + Tectonic | Comptage réel des pages, extraction du fichier `.tex` source associé, zoom dynamique | Recompilation automatique depuis le code source LaTeX associé |

---

## 5. Expérience Utilisateur & Panneau Droit Unifié

Le panneau droit unifié de NeoHarness (`#right-inspector`) s'adapte dynamiquement à la nature de l'artefact actif :

### Boutons d'Action & En-tête Redesignés
- **« Compiler avec Tectonic » (`.btn-doc-primary`)** : bouton d'action principale surélevé en bleu profond (`#0969da`), pictogramme vectoriel `play`, micro-transition active `scale(0.98)` et état `disabled` propre.
- **« Fermer » (`.btn-doc-secondary-close`)** : bouton d'action secondaire neutre avec icône vectorielle `close`, parfaitement intégré au design system.
- **Bandeau Document Word** : en-tête bleu Word pleine largeur (*edge-to-edge*), titre du document centré avec suppression des actions redondantes.
- **Bouton Copier** : icône vectorielle SVG dédiée (`ICONS.copy`), éliminant tout affichage `undefined`.

### Les 4 Onglets Contextuels
1. **Aperçu (`#btn-doc-view-render`)** :
   - **HTML** : Iframe sandboxed isolée (`sandbox="allow-scripts"`), sans fuite d'environnement hôte, avec écoute des erreurs JS en temps réel.
   - **LaTeX / PDF** : Rendu haute fidélité multi-pages via canvas PDF.js avec contrôle de zoom continu (50 % à 250 %, molette `Ctrl + Wheel`).
   - **Python** : Si le script a généré une image ou un graphique (ex: `matplotlib`), l'image est immédiatement présentée en grand ; sinon la console s'affiche par défaut.
   - **SVG** : Rendu vectoriel SVG pur directement inséré avec anti-aliasing et ombrage subtil.
   - **Mermaid** : Rendu dynamique SVG via Mermaid.js avec support automatique des thèmes sombre et clair.
   - **JSON** : Arborescence interactive repliable (nœuds pliables/dépliables en un clic, colorisation syntaxique des clés et valeurs).
   - **CSV** : Table de données interactive avec recherche temps réel et tri de colonnes instantané.
   - **Markdown** : Rendu typographique élégant avec équations mathématiques LaTeX rendues par KaTeX.
   - **Image** : Visualiseur HD centré avec indication de la résolution.

2. **Code Source (`#btn-doc-view-source`)** :
   - Éditeur de code pleine hauteur avec police monospace.
   - Bouton **"Enregistrer le code"** : valide, sauvegarde et recompile l'artefact en temps réel.

3. **Fichiers Générés (`#btn-doc-view-files`)** :
   - Liste tous les fichiers produits par l'exécution (par exemple, le script Python `simulation.py` et son graphique produit `courbe.png`).
   - Actions directes : **Ouvrir dans l'aperçu** et **Télécharger**.

4. **Console (`#btn-doc-view-console`)** :
   - Présente le statut de sortie (`✓ Succès` ou `⚠️ Code d'erreur`), la durée exacte en millisecondes, la ligne de commande exécutée, `STDOUT` et `STDERR`.
   - Bouton **"⚡ Relancer l'exécution"** permettant de ré-exécuter le script à la demande.

---

## 6. Référence des Routes API REST

### `POST /api/artifacts/process`
Traite, valide, compile ou exécute un fichier dans le workspace et enregistre un snapshot dans l'historique des versions.
- **Corps de la requête** :
  ```json
  {
    "path": "visualisation.py",
    "content": "import matplotlib.pyplot as plt\nplt.plot([1,2],[3,4])\nplt.savefig('test.png')",
    "auto_repair": true
  }
  ```
- **Réponse** :
  ```json
  {
    "status": "ready",
    "artifact": {
      "id": "art-9f12ab34",
      "type": "python",
      "status": "ready",
      "primary_path": "visualisation.py",
      "output_paths": ["test.png"],
      "execution": {
        "command": "python visualisation.py",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "duration_ms": 420
      },
      "metadata": {
        "visual_output": "test.png"
      }
    }
  }
  ```

### `POST /api/artifacts/execute`
Exécute explicitement un script (par ex. Python) et met à jour ses sorties dans le cache d'artefacts.
- **Corps de la requête** : `{"path": "script.py", "timeout_seconds": 60}`
- **Réponse** : Artefact enrichi avec le nouvel objet `execution` et la liste `output_paths`.

### `GET /api/artifacts/history?path=script.py`
Retourne la liste chronologique des versions de l'artefact avec leurs horodatages, résumés et empreintes SHA-256.

### `POST /api/artifacts/rollback`
Restaure immédiatement le contenu d'une version antérieure dans le workspace et re-vérifie l'artefact.
- **Corps de la requête** : `{"path": "script.py", "version_id": 1}`
- **Réponse** : Artefact restauré et prêt.

---

## 7. Sécurité & Confinement Workspace

1. **Isolation stricte du système de fichiers** :
   - `WorkspaceFilesystem` interdit toute traversée de chemin (`../`, chemins absolus, liens symboliques malveillants).
   - Les lectures et écritures sont confinées au dossier `workspace/`.

2. **Iframe Sandboxing pour HTML/JS** :
   - La prévisualisation HTML utilise l'attribut `sandbox="allow-scripts"`.
   - L'accès aux cookies de session, au localStorage hôte ou à la navigation parente (`allow-top-navigation`, `allow-same-origin`) est formellement bloqué.

3. **Timeouts stricts des sous-processus** :
   - Les compilations Tectonic et exécutions Python sont bornées par un `timeout` (par défaut 60 secondes). En cas de boucle infinie, le sous-processus est interrompu proprement (`subprocess.TimeoutExpired`).

---

## 8. Procédure pour Ajouter un Nouveau Format

L'architecture est entièrement ouverte à l'extension sans modifier le cœur de NeoHarness :

1. Définir le nouveau type dans `core/artifacts/models.py` (`ArtifactType.VOTRE_FORMAT`).
2. Créer une sous-classe de `BaseArtifactHandler` dans `core/artifacts/handlers.py` :
   - Implémenter `handles(path, content) -> bool`.
   - Implémenter `process(artifact, filesystem, ...) -> Artifact`.
   - Implémenter `get_preview_config(artifact) -> dict`.
3. Enregistrer le handler dans `UniversalArtifactEngine.__init__` (`core/artifacts/engine.py`).
4. Ajouter le container dans `ui/static/index.html` et le rendu dans `ui/static/app.js` (`renderDocumentPreviewPanel`).
5. Ajouter les tests unitaires réels dans `tests/test_universal_artifact_engine.py`.

---

## 9. Validation & Bilan des Tests

NeoHarness AI est validé par une suite complète de **143 tests automatisés** exécutés sans échec :
- `tests/test_universal_artifact_engine.py` (11 tests complets) : Validation, compilation, exécution, extraction et auto-réparation des formats HTML, LaTeX, Python, SVG, Mermaid, JSON, CSV et Markdown.
- `tests/test_ui_environment.py` (32 tests complets) : Intégrité UI, contrats de style épuré, palette de commandes canonique, 17 outils de production.
- `tests/test_general_skills.py` (18 tests complets) : Routage et gouvernance de l'ensemble des skills.
- Tests d'intégration multi-providers et mémoire vectorielle RAG.

Le moteur d'artefacts universel est en production, branché sur le serveur actif (`http://127.0.0.1:8765`), prêt à l'emploi.

