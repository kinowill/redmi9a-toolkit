# Roadmap

- [x] Relire le chantier réel et vérifier le root actuel sans modifier le téléphone.
- [x] Définir le périmètre communautaire et les contrôles avant développement.
- [x] Fournir diagnostic, audit/extraction d'images et manifestes de bundles.
- [x] Implémenter plan et installation à partir d'un bundle audité (tests simulés).
- [x] Ajouter le déverrouillage MediaTek borné demandé, et tester les garde-fous sans écrire.
- [x] Vérifier les refus, l'arrêt sur erreur et la confidentialité par tests.
- [x] Exécuter le diagnostic sur le Redmi déjà sous Lineage, sans nouvelle écriture.
- [x] Auditer les fichiers puis publier sur GitHub après connexion du propriétaire.
- [x] Retirer WSL/Ubuntu, usbipd et UsbDk ; conserver ce dépôt communautaire.
- [x] Exporter la trace sur le téléphone et retirer l'ancien chantier du Bureau vers la corbeille.
- [ ] Purge définitive de l'ancien chantier : refusée par le contrôle automatique, non effectuée.

## Extensions nécessitant leurs propres validations

- Automatisation de la préparation ext4 et du boot Magisk, avec comparaison du noyau.
- Validation matérielle de l'adaptateur MediaTek sur une matrice de versions/pilotes.
- Recettes pour d'autres firmwares, modèles et GSI plus récents.
- Linux natif seulement après identification et validation d'un portage matériel.
- Installation automatisée sur matériel de test dédié (non exécutée ici).
