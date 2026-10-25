# VISION INDUSTRIELLE : NEOHARNESS AI

## 1. Ambition & Philosophie Fondatrice

NeoHarness AI est un environnement agentique d'exécution industrielle conçu pour combler le fossé entre les démonstrateurs d'IA conversationnelle et les exigences critiques de la production :
- **Intégrité absolue des artefacts :** Zéro hallucination tolérée, interdiction de falsifier des livrables ou des documents pour feindre le succès.
- **Vérification déterministe en boucle fermée :** Oracles physiques, compilateurs, linters syntaxiques AST et suites de tests automatisées constituent les seuls arbitres valides de la réussite.
- **Réversibilité totale (Backtracking) :** Capacité d'explorer des hypothèses alternatives et de revenir physiquement en arrière sans jamais impacter le workspace de l'utilisateur.
- **Apprentissage réflexif continu :** Capitalisation persistante d'expériences et de règles d'action déduites des échecs et succès passés.
- **Gouvernance hiérarchique :** Séparation des rôles entre Manager (stratégie/découpage), Workers (spécialisation isolée) et Critic (veto impartial en contexte vierge).

---

## 2. Les Cinq Piliers Architecturaux

```
+---------------------------------------------------------------------------------+
|                                NEOHARNESS AI                                   |
+---------------------------------------------------------------------------------+
|  1. Backtracking Shadow Git     |  2. Navigation Dynamique Playwright           |
|  (Snapshots & Rollbacks)        |  (DOM structuré & respect robots.txt)         |
+---------------------------------+-----------------------------------------------+
|  3. Mémoire Réflexive SQLite    |  4. TDD Fermé & Critic Indépendant            |
|  (FTS5 & Décroissance decay)    |  (Hachage immuable des tests & veto objectif) |
+---------------------------------+-----------------------------------------------+
|  5. Hiérarchie Multi-Agents     |  Observabilité & Déterminisme                 |
|  (Manager / Workers / Critic)   |  (Puits JSONL, replay run_id, audit trail)    |
+---------------------------------------------------------------------------------+
```

---

## 3. Engagement Qualité & Déterminisme

1. **Aucun contournement des permissions :** Toute modification de fichier ou exécution de code passe par le registre centralisé `ToolRegistry` et respecte le niveau de risque associé.
2. **Cloisonnement des données externes :** Tout contenu en provenance d'Internet, de fichiers modifiés ou de sorties d'outils est injecté sous balises non fiables `<donnees_non_fiables>` pour prémunir le modèle contre les attaques par injection indirecte (Prompt Injection).
3. **Protection inviolable des oracles de test :** Le scellement SHA-256 interdit formellement à un agent d'affaiblir ou de supprimer un test pour faire valider un code défectueux.
