# POLITIQUE DE SÉCURITÉ : NEOHARNESS AI

## 1. Principes de Défense en Profondeur

NeoHarness AI est configuré selon le principe du moindre privilège et de l'étanchéité des frontières d'exécution.

---

## 2. Protection contre les Injections Indirectes (Prompt Injection)

Tout contenu provenant d'une source non souveraine (Internet, documents distants, sorties d'exécution système, leçons mémorisées) est systématiquement encapsulé dans un bloc non privilégié :

```xml
<donnees_non_fiables source="web_search">
Contenu brut récupéré depuis la source externe...
</donnees_non_fiables>
```

Le métaprompt de l'agent stipule expressément que ces données ne constituent en aucun cas des instructions exécutives, mais de simples observations passives.

---

## 3. Immuabilité des Tests & Prévention des Faux Succès

- **Hachage cryptographique :** Les fichiers de tests créés ou existants sont scellés par SHA-256 via `core/tdd_engine.py`.
- **Interdiction de modification :** Toute écriture ou tentative de contournement par un agent déclenche une exception bloquante `TestTamperingError`.
- **Chaîne de provenance obligatoire :**
  `SOURCE WEB -> URL -> TÉLÉCHARGEMENT -> FICHIER PHYSIQUE -> HASH -> MAGIC BYTES -> VÉRIFICATION`.
  Aucun artefact ne peut être certifié sans vérification physique de ses magic bytes (%PDF-1., etc.).

---

## 4. Politique de Conformité Réseau & Robots.txt

- Avant toute requête Web par le navigateur `tools/browser.py`, l'outil interroge le fichier `robots.txt` du domaine via `urllib.robotparser`.
- En cas de directive `Disallow`, l'accès est bloqué immédiatement avec un code `status="blocked"`.
- Tout forçage exceptionnel requiert un flag explicite `override_robots=True` associé à une justification écrite impérativement tracée dans l'audit trail.

---

## 5. Gestion des Données Sensibles & Secrets

- Les fichiers `.env`, clés d'API et tokens d'authentification sont filtrés par expressions régulières au niveau de `core/memory.py` et `tools/filesystem.py`.
- L'écriture de secrets dans la mémoire persistante du projet ou dans les journaux d'événements est strictement rejetée.
