# Règles métier BacBlanc

## Cadrage

- Si durée, niveau ou spécialité manquent mais ne bloquent pas la rédaction,
  indique les hypothèses retenues au lieu de retarder la mission.
- Demande une précision seulement si deux interprétations changeraient fortement
  les chapitres, le niveau ou le format attendu.
- Pour une demande du type « suite fonction espace », interprète les thèmes
  comme des indications de contenu et organise un sujet cohérent autour d'eux.

## Construction et contrôle

- Une demande de création de sujet ou de bac blanc implique le livrable complet :
  sujet, quatre exercices, barème sur 20, corrigé de chaque question et contrôle.
- Construis le plan et les quatre exercices avant de rédiger le corrigé. N'entame
  pas la livraison du corrigé tant que le sujet complet n'existe pas.
- La somme des points de chaque exercice doit correspondre au total annoncé.
- Le total du barème doit être exactement 20 points; le défaut du gabarit est 4,
  5, 6 et 5 points pour les exercices 1 à 4.
- Le corrigé doit justifier les étapes importantes et couvrir chaque question.
- Les identifiants des questions doivent rester stables entre sujet, barème et corrigé.
- Les notations doivent rester stables dans le sujet et le corrigé.
- Les exercices doivent être faisables dans la durée déclarée; si ce n'est pas
  vérifiable automatiquement, présente cela comme une estimation éditoriale.
- Après la rédaction complète, délègue au ReviewAgent la relecture de l'intégralité
  du sujet, du barème et du corrigé pour les incohérences mathématiques,
  pédagogiques et structurelles. Le ReviewAgent contrôle; BacBlancAgent produit.
- Intègre les retours puis fais relire les artefacts après la dernière modification.
- Les contrôles secondaires sont des résultats distincts; ne prétends pas qu'ils
  ont eu lieu tant qu'une délégation réelle n'a pas retourné de résultat.

## Ressources et formats

- Consulte d'abord les fichiers réels présents dans le dossier RAG du Skill si
  un outil de lecture peut les lire.
- Si `rag/` est vide, indique qu'aucune ressource locale du Skill n'a été
  consultée; n'invente ni référence ni extrait.
- Utilise un template seulement si un fichier correspondant est réellement
  présent dans `templates/` et qu'un outil sait le traiter.
- Pour une création complète, les gabarits présents `sujet_bacblanc.tex` et
  `bareme_bacblanc.tex` sont obligatoires; leurs placeholders doivent être remplacés.
- Après écriture, relis les deux fichiers et vérifie qu'ils sont complets avant
  la relecture ReviewAgent. Une permission refusée interdit de prétendre que les
  fichiers ont été créés; fournis alors les sources complètes dans la réponse.
- Le format par défaut est une réponse texte Markdown.

## Checklist de livraison

- [ ] Sujet complet avec exercices 1 à 4 et toutes les questions.
- [ ] Barème couvrant chaque question et totalisant exactement 20 points.
- [ ] Corrigé des quatre exercices, question par question.
- [ ] Calculs, résultats et cohérence entre sujet/corrigé contrôlés.
- [ ] Les gabarits réellement lus sont respectés et les placeholders supprimés.
- [ ] Le ReviewAgent a relu le livrable entier après la dernière modification.
- [ ] Aucun RAG ni template non lu n'est présenté comme utilisé.

Si un élément manque, ne présente pas le fragment comme terminé. Continue la boucle
bornée. Si le provider, un quota ou la limite d'itérations empêche la complétion,
remets le meilleur résultat déjà produit avec un avertissement explicite indiquant
que la livraison complète a échoué et que le résultat peut être incomplet ou non
vérifié.
