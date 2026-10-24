# Mode — commande globale du Harness

Cette commande règle le mode global du runtime. Le mode est appliqué par le
Gestionnaire de modes et la politique centrale de permissions; les autres Skills
ne peuvent ni choisir ni contourner le mode actif.

- `/mode` affiche les modes disponibles et le mode actif.
- `/mode edit` permet les modifications directes protégées par aperçu.
- `/mode plan` interdit les outils mutateurs.
- `/mode accept` demande confirmation pour les actions sensibles.
- `/mode auto` active le mécanisme autonome existant dans la politique globale;
  `--dry-run` et les garde-fous du Harness restent prioritaires.

`Shift+Tab` parcourt EDIT → PLAN → ACCEPT → AUTO → EDIT.
