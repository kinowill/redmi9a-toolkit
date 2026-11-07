# Contribuer

L'objectif est d'éviter aux autres les essais inutiles, avec une compatibilité
qui repose sur des lectures et des résultats reproductibles.

Pour un nouveau profil : préciser modèle, révision matérielle connue, SoC,
firmware/région du vendor, ABI Android, configuration noyau/binder, GPT nettoyée,
tailles des partitions, sources et versions exactes. Un appareil partageant le
nom dandelion n'est pas automatiquement compatible. Ajouter les tests de refus
avant d'activer une écriture et documenter une vraie validation matérielle.

Un autre OS exige son propre parcours, ses pilotes/portages et sa validation.
Ne pas étiqueter un système Linux natif comme une GSI pour passer les contrôles.
Ne pas remplacer les contrôles manquants par des valeurs par défaut permissives.

```text
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python -m ruff check redmi9a tests
python -m ruff format --check redmi9a tests
python -m mypy redmi9a
python -m bandit -r redmi9a -ll
```

Les tests utilisent de faux téléphones. Les dépendances MediaTek ne sont pas
nécessaires pour tester le code, y compris les hooks du DA simulé.
Bandit signale à faible niveau les imports/appels subprocess intentionnels ;
aucun shell hôte n'est utilisé et aucune alerte n'est masquée dans le code.

Avant publication : lire le diff, vérifier tous les liens et manifestes,
exécuter les contrôles, et rechercher secrets/identifiants. Ne jamais joindre
hwparam.json, `.state`, journaux MTK bruts, clés ADB, IMEI, numéros USB, adresses
personnelles, captures privées, sauvegardes seccfg ou images de téléphone.
Donner uniquement les propriétés autorisées par le diagnostic et les étapes
réellement effectuées. Ne pas republier de firmware ou d'APK tiers.

Sources de vérité : DOCUMENT_MAITRE.md, ROADMAP.md, VALIDATION_LOG.md et le code.
Chaque contribution doit distinguer code modifié, code publié et validation
réelle sur appareil. Ne pas flasher un téléphone principal pour tester une PR.
