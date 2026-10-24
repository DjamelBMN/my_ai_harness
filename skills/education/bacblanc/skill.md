# BacBlanc — Skill de conception d'épreuves

## Rôle

Ce Skill transforme une demande pédagogique en sujet de bac blanc cohérent,
adapté au niveau demandé et accompagné de ses éléments de correction. Il est
chargé seulement par la commande `/bacblanc`.

## Objectifs et règle de complétude

Pour toute demande de création d'un sujet ou d'un bac blanc, le livrable est
complet uniquement s'il comprend simultanément :

1. le sujet intégral et tous les exercices ;
2. un barème détaillé, couvrant chaque question, totalisant exactement 20 points ;
3. le corrigé complet de chaque question de chaque exercice ;
4. les vérifications mathématiques et le compte rendu de la relecture finale ;
5. les fichiers LaTeX produits à partir des gabarits quand l'écriture est autorisée.

Ne présente jamais seulement un exercice, le dernier exercice, un corrigé isolé,
une structure vide ou un texte annonçant la suite comme un livrable terminé. Si la
réponse est trop longue, continue avec l'état conservé par l'AgentLoop. Si un quota,
une limite du provider ou la limite d'itérations empêche finalement la complétion,
livre le meilleur contenu déjà produit avec un avertissement explicite : la livraison
complète a échoué et le contenu partiel peut être incomplet ou non vérifié.

## Analyse et hypothèses par défaut

Détermine le niveau, la spécialité, la durée, les thèmes, le nombre d'exercices,
la répartition des points, les contraintes pédagogiques et les livrables. Le
gabarit BacBlanc fixe par défaut Terminale spécialité mathématiques, 4 heures,
quatre exercices et une répartition 4 + 5 + 6 + 5 = 20 points. Si la demande ne
précise pas ces éléments, annonce ces hypothèses et avance sans question inutile.
Demande une précision seulement si le choix changerait substantiellement le sujet.

## Règles pédagogiques

- Par défaut, viser le niveau scolaire explicitement demandé; ne pas supposer un
  programme ou une année scolaire qui n'est pas précisé.
- Répartir la difficulté entre questions d'entrée, questions intermédiaires et
  questions de synthèse.
- Énoncer les données, notations et conventions nécessaires sans ambiguïté.
- Ne pas inventer une conformité à un programme officiel. Si elle est demandée,
  déléguer la vérification au ResearchAgent et citer uniquement les sources
  effectivement consultées.
- Contrôler les calculs, résultats et unités. Faire relire par ReviewAgent la
  version intégrale du sujet, du barème et du corrigé après la dernière modification.
- Utiliser `write_file` avec confirmation pour produire les fichiers LaTeX dans le
  workspace; ne jamais écraser un fichier existant. En cas de refus, livrer les deux
  sources complètes dans la réponse plutôt qu'un résultat partiel.

## Structure de sortie obligatoire pour un sujet complet

1. Paramètres retenus et hypothèses éventuelles.
2. Sujet intégral : quatre exercices, toutes les consignes et toutes les questions.
3. Barème question par question et total exact de 20.
4. Corrigé détaillé des quatre exercices, aligné question par question.
5. Vérifications mathématiques, limites, sources RAG réellement consultées et
   résultat de la relecture ReviewAgent.

Pour respecter les gabarits, produire `bacblanc_sujet.tex` et
`bacblanc_bareme.tex`. Ce dernier contient le corrigé détaillé et le barème. Relire
les fichiers après écriture. Si l'écriture est refusée ou indisponible, retourner
les deux sources complètes dans des blocs LaTeX nommés.

Les règles détaillées supplémentaires sont dans `rules.md`. Les ressources RAG
propres à ce Skill se trouvent dans `rag/`; aucun document n'est fourni par défaut.
Les deux gabarits LaTeX déclarés sont présents et leur contenu est chargé par le
SkillLoader avant l'exécution. Un contenu affiché comme lu dans le prompt a été
réellement lu; un nom ou un fichier illisible ne constitue jamais une preuve.
Une remise partielle après épuisement d'une limite garde le statut incomplet et ne
doit jamais être présentée comme complète ni vérifiée.
